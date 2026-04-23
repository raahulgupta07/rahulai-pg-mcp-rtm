#!/usr/bin/env python3
"""
FastAPI backend for RTM Outlet Classification.
Wraps the existing classification pipeline, AI service, and job management.
"""

import sys
import os
import io
import json

# Add project root so we can import from src/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Load .env file
from pathlib import Path
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())

from fastapi import FastAPI, UploadFile, File, Query, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import pandas as pd
import numpy as np

from src.rtm_classifier import RTMClassifier
from src.database import get_database
from src.job_manager import get_job_manager
from src.ai_service import get_ai_service
from backend.auth import authenticate_user, create_token, get_current_user, verify_token, list_users, create_user, delete_user, update_user_password

app = FastAPI(title="RTM Classification API")

# CORS for SvelteKit dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def sanitize_for_json(obj):
    """Replace NaN/Infinity values with None so JSON serialization works."""
    if isinstance(obj, float):
        if np.isnan(obj) or np.isinf(obj):
            return None
    return obj


def df_to_records(df: pd.DataFrame) -> list[dict]:
    """Convert DataFrame to list of dicts with NaN/Inf safely replaced."""
    clean = df.replace({np.nan: None, np.inf: None, -np.inf: None})
    # Convert Timestamp columns to ISO strings
    for col in clean.columns:
        if pd.api.types.is_datetime64_any_dtype(clean[col]):
            clean[col] = clean[col].apply(lambda x: x.isoformat() if pd.notna(x) else None)
    records = clean.to_dict(orient="records")
    return records


# ── Auth dependency ──
async def require_auth(authorization: str = Header(None)):
    user = get_current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="AUTHENTICATION_REQUIRED")
    return user

async def require_admin(user: dict = Depends(require_auth)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_REQUIRED")
    return user


# ── Auth routes ──
@app.post("/api/auth/login")
async def login(body: dict):
    username = body.get("username", "")
    password = body.get("password", "")
    user = authenticate_user(username, password)
    if not user:
        raise HTTPException(status_code=401, detail="INVALID_CREDENTIALS")
    token = create_token(user)
    db = get_database()
    db.log_action(username, "LOGIN", "Logged in successfully")
    return {"access_token": token, "token_type": "bearer", "user": user}

@app.get("/api/auth/me")
async def get_me(user: dict = Depends(require_auth)):
    return user

@app.get("/api/users")
async def get_users(user: dict = Depends(require_admin)):
    return list_users()

@app.post("/api/users")
async def add_user(body: dict, user: dict = Depends(require_admin)):
    try:
        new_user = create_user(body["username"], body["password"], body.get("role", "user"), body.get("display_name", ""))
        db = get_database()
        db.log_action(user["username"], "CREATE_USER", f"Created user: {body['username']}")
        return new_user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/users/{user_id}")
async def remove_user(user_id: int, user: dict = Depends(require_admin)):
    delete_user(user_id)
    db = get_database()
    db.log_action(user["username"], "DELETE_USER", f"Deleted user ID: {user_id}")
    return {"ok": True}


# ──────────────────────────────────────────────
# POST /api/classify
# ──────────────────────────────────────────────
@app.post("/api/classify")
async def classify(
    file: UploadFile = File(...),
    threshold_a: int = Query(80, ge=50, le=95),
    threshold_b: int = Query(95, ge=55, le=99),
    user: dict = Depends(require_auth),
):
    """
    Upload a CSV file and run the full RTM classification pipeline.
    Returns all data needed for the frontend in one response.
    """
    log: list[str] = []

    # 1. Read the uploaded CSV with encoding fallbacks
    log.append("$ mcp-agent upload --parse-csv")
    raw_bytes = await file.read()
    sales_df = None
    for encoding in ("utf-8", "latin-1", "cp1252"):
        try:
            sales_df = pd.read_csv(io.BytesIO(raw_bytes), encoding=encoding, low_memory=False)
            log.append(f"[OK] CSV parsed ({encoding}): {len(sales_df):,} rows, {len(sales_df.columns)} columns")
            break
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue

    if sales_df is None:
        raise HTTPException(status_code=400, detail="Could not parse CSV with any supported encoding (utf-8, latin-1, cp1252)")

    # Validate required columns
    log.append("$ mcp-agent validate --check-schema")
    required_cols = ["Cus.Code", "Cus.Name", "TotalAmount", "TotalPcs", "BranchName", "Item Class", "NumInBuy"]
    missing = [c for c in required_cols if c not in sales_df.columns]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing required columns: {', '.join(missing)}")

    for col in required_cols:
        log.append(f"[SCAN] Required: {col} {'.' * (25 - len(col))} FOUND")

    # Validate data is not empty
    if len(sales_df) == 0:
        raise HTTPException(status_code=400, detail="CSV file is empty — no data rows found")

    # Validate key columns have data
    null_checks = {
        "Cus.Code": sales_df["Cus.Code"].isnull().sum(),
        "TotalAmount": sales_df["TotalAmount"].isnull().sum(),
        "BranchName": sales_df["BranchName"].isnull().sum(),
    }
    warnings = [f"{col}: {count} null values" for col, count in null_checks.items() if count > 0]
    if warnings:
        for w in warnings:
            log.append(f"[WARN] {w}")
    log.append("[OK] Schema validation passed")

    # 2. Start a job
    job_manager = get_job_manager()
    job_id = job_manager.start_job(
        sales_filename=file.filename or "upload.csv",
        customer_filename="",
        item_filename="",
        threshold_a=threshold_a,
        threshold_b=threshold_b,
    )
    log.append(f"[INFO] Job ID: {job_id[:8]}...")

    try:
        # 3. Run classification pipeline
        log.append("$ mcp-agent classify --method pareto --partition branch")
        classifier = RTMClassifier(sales_df)
        results_df = classifier.process()

        n_branches = int(results_df["BranchName"].nunique()) if "BranchName" in results_df.columns else 0
        log.append(f"[OK] {len(results_df):,} outlets classified across {n_branches} branches")
        if "Classification" in results_df.columns:
            for cls_name, cnt in results_df["Classification"].value_counts().items():
                log.append(f"[RESULT] {cls_name}: {cnt:,}")
        if classifier.min_date and classifier.max_date:
            log.append(f"[INFO] Date range: {classifier.min_date.date()} to {classifier.max_date.date()}")
        ws_col_count = int(results_df["Is_Wholesaler"].sum()) if "Is_Wholesaler" in results_df.columns else 0
        log.append(f"[INFO] Wholesalers detected: {ws_col_count}")

        # 4. AI enrichment (per-outlet columns)
        log.append("$ mcp-agent enrich --ai-rules")
        ai_service = get_ai_service()
        results_df = ai_service.enrich_outlets(results_df)
        if "AI_Growth_Signal" in results_df.columns:
            for signal, cnt in results_df["AI_Growth_Signal"].value_counts().items():
                log.append(f"[AI] {signal}: {cnt:,} outlets")
        log.append("[OK] AI enrichment complete")

        # 5. AI insights (step by step)
        insights = {}

        log.append("$ mcp-agent insights --step executive-summary")
        insights["executive_summary"] = ai_service.generate_executive_summary(results_df)
        log.append("[OK] Executive summary generated")

        log.append("$ mcp-agent insights --step recommendations")
        recs = ai_service.generate_recommendations(results_df)
        insights.update(recs)
        log.append("[OK] Class A/B/C recommendations generated")

        log.append("$ mcp-agent insights --step growth-analysis")
        insights["growth_analysis"] = ai_service.generate_growth_analysis(results_df)
        log.append("[OK] Growth analysis generated")

        # 5b. Workload data
        workload = []
        if hasattr(classifier, 'route_workload') and classifier.route_workload is not None:
            workload = df_to_records(classifier.route_workload)

        # 6. Build branch summary
        branch_summary_df = classifier.get_branch_summary()
        branch_summary = df_to_records(branch_summary_df) if branch_summary_df is not None else []

        # 7. Save to database via job manager
        date_from = str(classifier.min_date.date()) if classifier.min_date else None
        date_to = str(classifier.max_date.date()) if classifier.max_date else None
        wl_df = classifier.route_workload if hasattr(classifier, 'route_workload') else None
        job_manager.complete_job(results_df, date_from=date_from, date_to=date_to, workload_df=wl_df)
        log.append("[OK] Job saved to database")

        # Audit log
        db = get_database()
        db.log_action(user["username"], "CLASSIFY", f"Job {job_id}: {len(results_df)} outlets, {n_branches} branches")

        # 8. Compute summary counts
        class_counts = results_df["Classification"].value_counts().to_dict()
        class_a = class_counts.get("Class A", 0) + class_counts.get("Class A Local (F4)", 0)
        class_a += sum(v for k, v in class_counts.items() if k.startswith("Class A") and k not in ("Class A", "Class A Local (F4)"))
        class_b = class_counts.get("Class B", 0)
        class_c = class_counts.get("Class C", 0)
        total_revenue = float(results_df["TotalSales_2Yr"].sum()) if "TotalSales_2Yr" in results_df.columns else 0.0
        branches = int(results_df["BranchName"].nunique()) if "BranchName" in results_df.columns else 0

        # 9. Data quality checks
        data_quality = []
        ws_count = int(results_df["Is_Wholesaler"].sum()) if "Is_Wholesaler" in results_df.columns else 0

        # Check Item Type
        if "Item Type" in sales_df.columns:
            item_types = sales_df["Item Type"].unique().tolist()
            if "Local" not in item_types:
                data_quality.append({
                    "field": "Item Type",
                    "status": "warning",
                    "message": "No 'Local' products found — all items are Import. Wholesaler detection (F4) could not run.",
                    "impact": "Wholesaler classification skipped"
                })
        else:
            data_quality.append({
                "field": "Item Type",
                "status": "missing",
                "message": "Item Type column not found in dataset.",
                "impact": "Wholesaler detection and Local/Import breakdown unavailable"
            })

        # Check Outlet Channel
        if "Outlet Channel" in sales_df.columns:
            oc_vals = sales_df["Outlet Channel"].astype(str).unique().tolist()
            if set(oc_vals) <= {"0", "0.0", "", "nan"}:
                data_quality.append({
                    "field": "Outlet Channel",
                    "status": "warning",
                    "message": "Outlet Channel is empty (all zeros). Used 'Channel' column as fallback.",
                    "impact": "Channel-based wholesaler override not applied"
                })
        else:
            data_quality.append({
                "field": "Outlet Channel",
                "status": "missing",
                "message": "Outlet Channel column not found.",
                "impact": "Channel classification unavailable"
            })

        # Check DocDate range
        if classifier.months_count and classifier.months_count < 12:
            data_quality.append({
                "field": "DocDate",
                "status": "info",
                "message": f"Data spans only {classifier.months_count:.1f} months. 2-year metrics may be incomplete.",
                "impact": "Period comparisons (2Yr) based on available data only"
            })

        # Check AI
        if not ai_service.is_configured():
            data_quality.append({
                "field": "LLM API",
                "status": "info",
                "message": "No LLM API key configured. Using rule-based fallback insights.",
                "impact": "Executive summary and recommendations are template-based"
            })

        # Wholesaler result
        if ws_count == 0:
            data_quality.append({
                "field": "Wholesalers",
                "status": "info",
                "message": f"0 wholesalers detected. Requires Local products with ≥3 cartons/brand/month.",
                "impact": "No F4 (Class A Local) classifications assigned"
            })

        # Check seller workload
        if hasattr(classifier, 'route_workload') and classifier.route_workload is not None:
            wl = classifier.route_workload
            below = len(wl[wl["Workload_Status"] == "BELOW_MIN"])
            above = len(wl[wl["Workload_Status"] == "ABOVE_MAX"])
            ok_count = len(wl[wl["Workload_Status"] == "OK"])
            if below > 0:
                data_quality.append({
                    "field": "Seller Workload",
                    "status": "warning",
                    "message": f"{below} routes have fewer outlets than minimum target (YGN: 25, Regional: 30)",
                    "impact": f"These sellers may need additional outlet assignments"
                })
            if above > 0:
                data_quality.append({
                    "field": "Seller Workload",
                    "status": "info",
                    "message": f"{above} routes exceed maximum target (YGN: 30, Regional: 35)",
                    "impact": f"Consider splitting these routes for better coverage"
                })

        # All good checks
        good_checks = []
        if "BranchName" in sales_df.columns and sales_df["BranchName"].nunique() > 1:
            good_checks.append(f"BranchName: {sales_df['BranchName'].nunique()} branches detected — per-branch Pareto applied")
        if "Cus.Code" in sales_df.columns:
            good_checks.append(f"Cus.Code: {sales_df['Cus.Code'].nunique()} unique customers found")
        if "DocDate" in sales_df.columns:
            good_checks.append(f"DocDate: {classifier.min_date.date()} to {classifier.max_date.date()}")
        if hasattr(classifier, 'route_workload') and classifier.route_workload is not None:
            wl = classifier.route_workload
            ok_count = len(wl[wl["Workload_Status"] == "OK"])
            good_checks.append(f"RouteCode: {len(wl)} routes analyzed — {ok_count} within target range")

        # 9b. Save AI insights to database
        db = get_database()
        db.save_job_insights(job_id, insights, data_quality)

        # 10. Build response
        results_records = df_to_records(results_df)

        return JSONResponse(content={
            "job_id": job_id,
            "total_outlets": len(results_df),
            "branches": branches,
            "class_a": class_a,
            "class_b": class_b,
            "class_c": class_c,
            "wholesalers": ws_count,
            "revenue": total_revenue,
            "results": results_records,
            "workload": workload,
            "branch_summary": branch_summary,
            "insights": insights,
            "log": log,
            "data_quality": data_quality,
            "data_quality_ok": good_checks,
        })

    except Exception as e:
        job_manager.fail_job(str(e))
        raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")


# ──────────────────────────────────────────────
# GET /api/jobs
# ──────────────────────────────────────────────
@app.get("/api/jobs")
async def list_jobs(user: dict = Depends(require_auth)):
    """Return list of all jobs from the database."""
    db = get_database()
    jobs = db.get_all_jobs(limit=50)
    # Ensure all values are JSON serializable
    clean_jobs = []
    for job in jobs:
        clean_job = {}
        for key, value in job.items():
            if value is None:
                clean_job[key] = None
            elif isinstance(value, (int, float, bool, str)):
                clean_job[key] = value
            else:
                clean_job[key] = str(value)
        clean_jobs.append(clean_job)
    return JSONResponse(content=clean_jobs)


# ──────────────────────────────────────────────
# GET /api/jobs/{job_id}
# ──────────────────────────────────────────────
@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str, user: dict = Depends(require_auth)):
    """Return single job details with full results."""
    db = get_database()
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    # Ensure job values are JSON serializable
    clean_job = {}
    for key, value in job.items():
        if value is None:
            clean_job[key] = None
        elif isinstance(value, (int, float, bool, str)):
            clean_job[key] = value
        else:
            clean_job[key] = str(value)

    results_df = db.get_job_results(job_id)
    results = df_to_records(results_df) if not results_df.empty else []

    # Load saved insights
    insights = db.get_job_insights(job_id)
    data_quality = insights.pop("data_quality", []) if insights else []

    return JSONResponse(content={
        "job": clean_job,
        "results": results,
        "insights": insights,
        "data_quality": data_quality,
    })


# ──────────────────────────────────────────────
# GET /api/jobs/{job_id}/export
# ──────────────────────────────────────────────
@app.get("/api/jobs/{job_id}/export")
async def export_job(job_id: str, user: dict = Depends(require_auth)):
    """Generate and return an Excel report for the given job."""
    job_manager = get_job_manager()

    # Try to read an existing Excel file first
    excel_bytes = job_manager.read_excel_file(job_id)

    if excel_bytes is None:
        # Generate from database results
        db = get_database()
        job = db.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        results_df = db.get_job_results(job_id)
        if results_df.empty:
            raise HTTPException(status_code=404, detail=f"No results found for job {job_id}")

        # Reverse the column mapping so DataFrame has original column names for the report
        reverse_mapping = {
            "Cus_Code": "Cus.Code",
            "Cus_Name": "Cus.Name",
        }
        results_df = results_df.rename(columns=reverse_mapping)

        excel_bytes = job_manager.create_excel_report(results_df)

    db = get_database()
    db.log_action(user["username"], "EXPORT", f"Downloaded Excel for {job_id}")

    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={job_id}.xlsx"},
    )


# ──────────────────────────────────────────────
# GET /api/health
# ──────────────────────────────────────────────
@app.get("/api/health")
async def health():
    """Health check endpoint."""
    ai_service = get_ai_service()
    db = get_database()
    jobs = db.get_all_jobs(limit=1)
    total_jobs = len(db.get_all_jobs(limit=1000))
    last_run = jobs[0]["created_at"] if jobs else None
    latest_outlets = jobs[0].get("total_outlets", 0) if jobs else 0
    return JSONResponse(content={
        "status": "ok",
        "pipeline": "idle",
        "model": ai_service.model if ai_service.is_configured() else "not configured",
        "jobs": total_jobs,
        "last_run": str(last_run) if last_run else None,
        "outlets": latest_outlets,
    })


# ──────────────────────────────────────────────
# GET /api/settings
# ──────────────────────────────────────────────
@app.get("/api/settings")
async def get_settings(user: dict = Depends(require_auth)):
    ai_service = get_ai_service()
    db = get_database()
    jobs = db.get_all_jobs(limit=1000)

    settings_file = Path(__file__).parent.parent / "data" / "settings.json"
    saved = {}
    if settings_file.exists():
        saved = json.loads(settings_file.read_text())

    return JSONResponse(content={
        "model": ai_service.model,
        "api_configured": ai_service.is_configured(),
        "base_url": ai_service.base_url,
        "total_jobs": len(jobs),
        "default_threshold_a": saved.get("threshold_a", 80),
        "default_threshold_b": saved.get("threshold_b", 95),
        "version": "1.0",
        "team": "City AI Team",
        "org": "City Holdings Myanmar",
    })


@app.post("/api/settings")
async def update_settings(body: dict, user: dict = Depends(require_admin)):
    """Save default thresholds."""
    settings_file = Path(__file__).parent.parent / "data" / "settings.json"
    settings_file.parent.mkdir(parents=True, exist_ok=True)

    current = {}
    if settings_file.exists():
        current = json.loads(settings_file.read_text())

    if "threshold_a" in body:
        current["threshold_a"] = int(body["threshold_a"])
    if "threshold_b" in body:
        current["threshold_b"] = int(body["threshold_b"])

    settings_file.write_text(json.dumps(current, indent=2))

    db = get_database()
    db.log_action(user["username"], "SETTINGS", f"Updated thresholds: A={body.get('threshold_a')}, B={body.get('threshold_b')}")

    return {"ok": True, "threshold_a": current.get("threshold_a", 80), "threshold_b": current.get("threshold_b", 95)}


# ──────────────────────────────────────────────
# GET /api/rtm-data
# ──────────────────────────────────────────────
@app.get("/api/rtm-data")
async def get_rtm_data(
    job_id: str = Query(None),
    user: dict = Depends(require_auth),
):
    """Return all outlet results, optionally filtered by job_id."""
    db = get_database()

    if job_id:
        results_df = db.get_job_results(job_id)
    else:
        # Get latest completed job
        jobs = db.get_all_jobs(limit=1)
        if not jobs:
            return JSONResponse(content={"results": [], "job_id": None, "jobs": []})
        latest = jobs[0]
        results_df = db.get_job_results(latest["job_id"])
        job_id = latest["job_id"]

    records = df_to_records(results_df) if not results_df.empty else []

    # Get all job IDs for the job filter dropdown
    all_jobs = db.get_all_jobs(limit=50)
    job_list = [{"job_id": j["job_id"], "created_at": str(j.get("created_at", "")), "total_outlets": j.get("total_outlets", 0)} for j in all_jobs]

    return JSONResponse(content={
        "results": records,
        "job_id": job_id,
        "jobs": job_list,
    })


# ──────────────────────────────────────────────
# GET /api/compare
# ──────────────────────────────────────────────
@app.get("/api/compare")
async def compare_jobs(
    job1: str = Query(...),
    job2: str = Query(...),
    user: dict = Depends(require_auth),
):
    """Compare two classification jobs side by side."""
    db = get_database()

    r1 = db.get_job_results(job1)
    r2 = db.get_job_results(job2)
    j1 = db.get_job(job1)
    j2 = db.get_job(job2)

    if r1.empty or r2.empty:
        raise HTTPException(status_code=404, detail="One or both jobs not found")

    # Compute comparison
    # Use Cus_Code as the key
    code_col = 'Cus_Code' if 'Cus_Code' in r1.columns else 'Cus.Code'

    set1 = set(r1[code_col].astype(str))
    set2 = set(r2[code_col].astype(str))

    new_outlets = set2 - set1
    lost_outlets = set1 - set2
    common = set1 & set2

    # Track classification changes
    movements = []
    cls1_map = dict(zip(r1[code_col].astype(str), r1['Classification']))
    cls2_map = dict(zip(r2[code_col].astype(str), r2['Classification']))
    name_map = dict(zip(r2[code_col].astype(str), r2.get('Cus_Name', r2.get('Cus.Name', ''))))
    branch_map = dict(zip(r2[code_col].astype(str), r2.get('BranchName', '')))

    upgraded = 0
    downgraded = 0
    unchanged = 0

    class_rank = {'Class A': 1, 'Class A Local (F4)': 1, 'Class B': 2, 'Class C': 3}

    for code in common:
        old_cls = str(cls1_map.get(code, ''))
        new_cls = str(cls2_map.get(code, ''))
        if old_cls != new_cls:
            old_rank = class_rank.get(old_cls, 99)
            new_rank = class_rank.get(new_cls, 99)
            status = 'UPGRADED' if new_rank < old_rank else 'DOWNGRADED'
            if status == 'UPGRADED':
                upgraded += 1
            else:
                downgraded += 1
            movements.append({
                'code': code,
                'name': str(name_map.get(code, '')),
                'branch': str(branch_map.get(code, '')),
                'from': old_cls,
                'to': new_cls,
                'status': status,
            })
        else:
            unchanged += 1

    # Summary stats for each job
    def job_stats(df):
        total = len(df)
        a = len(df[df['Classification'].str.startswith('Class A')])
        b = len(df[df['Classification'] == 'Class B'])
        c = len(df[df['Classification'] == 'Class C'])
        rev = float(df['TotalSales_2Yr'].sum()) if 'TotalSales_2Yr' in df.columns else 0
        return {'total': total, 'class_a': a, 'class_b': b, 'class_c': c, 'revenue': rev}

    return JSONResponse(content={
        'job1': {'id': job1, 'stats': job_stats(r1), 'created': str(j1.get('created_at', '')) if j1 else ''},
        'job2': {'id': job2, 'stats': job_stats(r2), 'created': str(j2.get('created_at', '')) if j2 else ''},
        'movements': movements[:500],
        'summary': {
            'upgraded': upgraded,
            'downgraded': downgraded,
            'unchanged': unchanged,
            'new_outlets': len(new_outlets),
            'lost_outlets': len(lost_outlets),
            'total_changes': upgraded + downgraded + len(new_outlets) + len(lost_outlets),
        },
    })


# ──────────────────────────────────────────────
# GET /api/coverage
# ──────────────────────────────────────────────
@app.get("/api/coverage")
async def get_coverage(
    job_id: str = Query(None),
    user: dict = Depends(require_auth),
):
    """Return outlet locations with classification for map visualization."""
    import glob
    db = get_database()

    if not job_id:
        jobs = db.get_all_jobs(limit=1)
        if not jobs:
            return JSONResponse(content={"outlets": [], "summary": {}})
        job_id = jobs[0]["job_id"]

    results_df = db.get_job_results(job_id)
    if results_df.empty:
        return JSONResponse(content={"outlets": [], "summary": {}})

    geo_data = None
    for pattern in [
        "/Users/rahulgupta/Downloads/Coverage Planning (MCP) 2/Customer_Master.csv",
        os.path.join(os.path.dirname(__file__), "..", "data", "sample_customers.csv"),
    ]:
        for f in glob.glob(pattern):
            try:
                for enc in ("utf-8", "latin-1", "cp1252"):
                    try:
                        geo_data = pd.read_csv(f, encoding=enc)
                        break
                    except Exception:
                        continue
                if geo_data is not None:
                    break
            except Exception:
                continue

    outlets = []
    code_col = 'Cus_Code' if 'Cus_Code' in results_df.columns else 'Cus.Code'
    name_col = 'Cus_Name' if 'Cus_Name' in results_df.columns else 'Cus.Name'

    if geo_data is not None and 'Latitude' in geo_data.columns and 'Longitude' in geo_data.columns:
        geo_key = 'CardCode_New' if 'CardCode_New' in geo_data.columns else 'CardCode' if 'CardCode' in geo_data.columns else 'Cus.Code'
        geo_data[geo_key] = geo_data[geo_key].astype(str)
        results_df[code_col] = results_df[code_col].astype(str)

        merge_cols = [geo_key, 'Latitude', 'Longitude']
        if 'Township' in geo_data.columns:
            merge_cols.append('Township')

        merged = results_df.merge(
            geo_data[merge_cols].drop_duplicates(subset=geo_key),
            left_on=code_col, right_on=geo_key, how='left'
        )

        for _, r in merged.iterrows():
            lat = r.get('Latitude')
            lng = r.get('Longitude')
            if pd.notna(lat) and pd.notna(lng) and lat != 0 and lng != 0:
                outlets.append({
                    'code': str(r.get(code_col, '')),
                    'name': str(r.get(name_col, '')),
                    'branch': str(r.get('BranchName', '')),
                    'classification': str(r.get('Classification', '')),
                    'township': str(r.get('Township', '')) if 'Township' in r.index else '',
                    'lat': float(lat),
                    'lng': float(lng),
                    'revenue': float(r.get('TotalSales_2Yr', 0) or 0),
                })
    else:
        for _, r in results_df.head(1000).iterrows():
            outlets.append({
                'code': str(r.get(code_col, '')),
                'name': str(r.get(name_col, '')),
                'branch': str(r.get('BranchName', '')),
                'classification': str(r.get('Classification', '')),
                'township': '',
                'lat': None,
                'lng': None,
                'revenue': float(r.get('TotalSales_2Yr', 0) or 0),
            })

    township_summary: dict = {}
    for o in outlets:
        t = o.get('township') or 'Unknown'
        if t not in township_summary:
            township_summary[t] = {'total': 0, 'a': 0, 'b': 0, 'c': 0}
        township_summary[t]['total'] += 1
        cls = o.get('classification', '')
        if 'Class A' in cls:
            township_summary[t]['a'] += 1
        elif 'Class B' in cls:
            township_summary[t]['b'] += 1
        elif 'Class C' in cls:
            township_summary[t]['c'] += 1

    return JSONResponse(content={
        'outlets': outlets[:5000],
        'summary': township_summary,
        'total_with_geo': len([o for o in outlets if o['lat'] is not None]),
        'total_without_geo': len([o for o in outlets if o['lat'] is None]),
    })


# ──────────────────────────────────────────────
# GET /api/audit
# ──────────────────────────────────────────────
@app.get("/api/audit")
async def get_audit(user: dict = Depends(require_admin)):
    db = get_database()
    logs = db.get_audit_log(limit=200)
    # Ensure serializable
    clean = []
    for entry in logs:
        clean.append({k: str(v) if v is not None else None for k, v in entry.items()})
    return JSONResponse(content=clean)


# ============================================================
# SERVE SVELTEKIT STATIC BUILD (single port)
# ============================================================
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "build")

if os.path.isdir(STATIC_DIR):
    # Serve static assets (_app, js, css, etc.)
    app.mount("/_app", StaticFiles(directory=os.path.join(STATIC_DIR, "_app")), name="static_app")

    # SPA fallback: serve index.html for all non-API routes (client-side routing)
    @app.get("/{path:path}")
    async def spa_fallback(path: str):
        # Serve actual files if they exist
        file_path = os.path.join(STATIC_DIR, path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        # Otherwise serve index.html for SPA routing
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))
