#!/usr/bin/env python3
"""
FastAPI backend for RTM Outlet Classification.
Wraps the existing classification pipeline, AI service, and job management.
"""

import sys
import os
import io
import json
import asyncio

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
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import pandas as pd
import numpy as np

import uuid
import re
from pathlib import Path
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "/app/uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

from src.rtm_classifier import RTMClassifier
from src.database import get_database
from src.job_manager import get_job_manager
from src.ai_service import get_ai_service, summarize_usage
from backend.auth import authenticate_user, create_token, get_current_user, verify_token, list_users, create_user, delete_user, update_user_password, change_password, get_user_prefs, set_user_prefs, load_ldap_config, save_ldap_config, ldap_test, update_user_identity, set_user_disabled, list_groups, create_group, update_group, delete_group, set_user_groups, effective_permissions, PERMISSION_CATALOG

# Disable auto API docs (Swagger/ReDoc/OpenAPI) — backend not browsable by users.
# The frontend's own /docs page is served via the SPA fallback below.
app = FastAPI(
    title="RTM Classification API",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# CORS for SvelteKit dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _boost_threadpool():
    """Enlarge the worker-thread pool — sync `def` endpoints and offloaded
    heavy work (classify, Excel) run here; default is 40, too few for ~100 users."""
    import anyio
    try:
        anyio.to_thread.current_default_thread_limiter().total_tokens = 64
    except Exception:
        pass


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
    if user["role"] not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="ADMIN_REQUIRED")
    return user

async def require_super_admin(user: dict = Depends(require_auth)):
    if user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="SUPER_ADMIN_REQUIRED")
    return user

def require_perm(perm: str):
    """Dependency factory — allow if the user's effective permissions
    (role base ∪ group grants) include `perm`."""
    async def _dep(user: dict = Depends(require_auth)):
        if user["role"] == "super_admin" or perm in effective_permissions(user["user_id"]):
            return user
        raise HTTPException(status_code=403, detail="PERMISSION_DENIED")
    return _dep


# ── Auth routes ──
@app.post("/api/auth/login")
async def login(body: dict):
    username = body.get("username", "")
    password = body.get("password", "")
    user = authenticate_user(username, password)
    if not user:
        get_database().log_action(username or "(blank)", "LOGIN_FAILED", "Invalid credentials or disabled account")
        raise HTTPException(status_code=401, detail="INVALID_CREDENTIALS")
    token = create_token(user)
    db = get_database()
    db.log_action(username, "LOGIN", "Logged in successfully")
    user = {**user, "permissions": effective_permissions(user["id"])}
    return {"access_token": token, "token_type": "bearer", "user": user}

@app.get("/api/auth/me")
async def get_me(user: dict = Depends(require_auth)):
    return {**user, "prefs": get_user_prefs(user["user_id"]),
            "permissions": effective_permissions(user["user_id"])}

@app.post("/api/auth/change-password")
async def change_password_ep(body: dict, user: dict = Depends(require_auth)):
    """Logged-in user changes their own password (verifies the current one)."""
    old = body.get("old_password", "")
    new = body.get("new_password", "")
    if len(new) < 4:
        raise HTTPException(status_code=400, detail="New password must be at least 4 characters")
    try:
        change_password(user["user_id"], old, new)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    get_database().log_action(user["username"], "SETTINGS", "Changed own password")
    return {"ok": True}

@app.put("/api/users/{user_id}/password")
async def reset_password_ep(user_id: int, body: dict, user: dict = Depends(require_super_admin)):
    """Super-admin resets another user's password (no old password needed)."""
    new = body.get("new_password", "")
    if len(new) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters")
    if not update_user_password(user_id, new):
        raise HTTPException(status_code=404, detail="User not found")
    get_database().log_action(user["username"], "SETTINGS", f"Reset password for user #{user_id}")
    return {"ok": True}

@app.get("/api/preferences")
async def get_preferences(user: dict = Depends(require_auth)):
    """Return the current user's saved UI preferences."""
    return get_user_prefs(user["user_id"])

@app.post("/api/preferences")
async def save_preferences(body: dict, user: dict = Depends(require_auth)):
    """Persist the current user's UI preferences (theme/appearance)."""
    set_user_prefs(user["user_id"], body)
    return {"ok": True}

@app.get("/api/users")
async def get_users(user: dict = Depends(require_super_admin)):
    return list_users()

@app.get("/api/users/basic")
async def get_users_basic(user: dict = Depends(require_auth)):
    """Minimal user list (id + name) for share pickers — any authenticated user."""
    return [{"id": u["id"], "username": u["username"], "display_name": u["display_name"]}
            for u in list_users()]

@app.post("/api/users")
async def add_user(body: dict, user: dict = Depends(require_super_admin)):
    try:
        new_user = create_user(body["username"], body["password"], body.get("role", "user"),
                               body.get("display_name", ""), body.get("email", ""), body.get("groups", []))
        db = get_database()
        db.log_action(user["username"], "CREATE_USER", f"Created user: {body['username']}")
        return new_user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/users/{user_id}")
async def remove_user(user_id: int, user: dict = Depends(require_super_admin)):
    delete_user(user_id)
    db = get_database()
    db.log_action(user["username"], "DELETE_USER", f"Deleted user ID: {user_id}")
    return {"ok": True}

@app.put("/api/users/{user_id}/disabled")
async def set_user_disabled_ep(user_id: int, body: dict, user: dict = Depends(require_super_admin)):
    """Disable or enable a user account (super_admin cannot be disabled)."""
    disabled = bool(body.get("disabled"))
    if not set_user_disabled(user_id, disabled):
        raise HTTPException(status_code=400, detail="Cannot change this account")
    get_database().log_action(user["username"], "SETTINGS",
                              f"{'Disabled' if disabled else 'Enabled'} user #{user_id}")
    return {"ok": True}

@app.put("/api/users/{user_id}/ldap-link")
async def link_user_ldap(user_id: int, body: dict, user: dict = Depends(require_super_admin)):
    """Update a local account's email and/or LDAP-username alias — the controls
    that drive account merging."""
    email = body.get("email")
    ldap_username = body.get("ldap_username")
    if not update_user_identity(user_id, email=email, ldap_username=ldap_username):
        raise HTTPException(status_code=404, detail="User not found")
    get_database().log_action(user["username"], "SETTINGS",
                              f"Updated identity for user #{user_id}")
    return {"ok": True}


# ──────────────────────────────────────────────
# Groups & permissions (super_admin)
# ──────────────────────────────────────────────
@app.get("/api/groups")
async def get_groups(user: dict = Depends(require_super_admin)):
    """List all groups + the permission catalog groups can grant."""
    return JSONResponse(content={"groups": list_groups(), "catalog": PERMISSION_CATALOG})

@app.post("/api/groups")
async def add_group(body: dict, user: dict = Depends(require_super_admin)):
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Group name is required")
    g = create_group(name, body.get("description", ""),
                     body.get("permissions", []), body.get("ldap_group", ""))
    get_database().log_action(user["username"], "SETTINGS", f"Created group '{name}'")
    return {"ok": True, "group": g}

@app.put("/api/groups/{group_id}")
async def edit_group(group_id: str, body: dict, user: dict = Depends(require_super_admin)):
    if not update_group(group_id, body.get("name"), body.get("description"),
                        body.get("permissions"), body.get("ldap_group")):
        raise HTTPException(status_code=404, detail="Group not found")
    get_database().log_action(user["username"], "SETTINGS", f"Updated group {group_id}")
    return {"ok": True}

@app.delete("/api/groups/{group_id}")
async def remove_group(group_id: str, user: dict = Depends(require_super_admin)):
    delete_group(group_id)
    get_database().log_action(user["username"], "SETTINGS", f"Deleted group {group_id}")
    return {"ok": True}

@app.put("/api/users/{user_id}/groups")
async def set_user_groups_ep(user_id: int, body: dict, user: dict = Depends(require_super_admin)):
    """Assign a user's group membership."""
    if not set_user_groups(user_id, body.get("groups", [])):
        raise HTTPException(status_code=404, detail="User not found")
    get_database().log_action(user["username"], "SETTINGS", f"Updated groups for user #{user_id}")
    return {"ok": True}


# ──────────────────────────────────────────────
# POST /api/upload — stream a CSV to local disk, return an upload_id.
# Decouples slow upload from classification. Cleanup happens after /classify
# completes (or via explicit DELETE).
# ──────────────────────────────────────────────
def _safe_filename(name: str) -> str:
    name = (name or "upload.csv").split("/")[-1].split("\\")[-1]
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    return name[:200] or "upload.csv"


def _find_upload(upload_id: str) -> Path | None:
    if not re.fullmatch(r"[a-f0-9]{32}", upload_id):
        return None
    matches = list(UPLOAD_DIR.glob(f"{upload_id}_*"))
    return matches[0] if matches else None


@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    user: dict = Depends(require_auth),
):
    """Stream the file to /app/uploads/{id}_{name}. Never holds full file in RAM."""
    upload_id = uuid.uuid4().hex
    safe_name = _safe_filename(file.filename or "upload.csv")
    dest = UPLOAD_DIR / f"{upload_id}_{safe_name}"
    size = 0
    try:
        with dest.open("wb") as out:
            while True:
                chunk = await file.read(8 * 1024 * 1024)  # 8 MB
                if not chunk:
                    break
                out.write(chunk)
                size += len(chunk)
    except Exception as e:
        if dest.exists():
            dest.unlink()
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")
    return {
        "upload_id": upload_id,
        "filename": safe_name,
        "size_bytes": size,
        "size_mb": round(size / (1024 * 1024), 2),
    }


@app.delete("/api/upload/{upload_id}")
async def delete_upload(upload_id: str, user: dict = Depends(require_auth)):
    path = _find_upload(upload_id)
    if path and path.exists():
        path.unlink()
    return {"ok": True}


# Internal: shared pipeline used by both sync /api/classify and async
# /api/classify-async. If job_id_override is supplied, the existing job
# row is used (caller already reserved it). If db_progress=True, progress
# updates are written to jobs.progress_step/total/message/log as we go,
# so the async status endpoint can poll live state.
# ──────────────────────────────────────────────
async def _run_classify_pipeline(
    upload_id: str | None,
    file: UploadFile | None,
    threshold_a: int,
    threshold_b: int,
    user: dict,
    job_id_override: str | None = None,
    db_progress: bool = False,
) -> dict:
    db_singleton = get_database() if db_progress else None
    current_step = {"n": 0}
    total_steps = 10

    # Auto-flushing log list: every append also pushes to jobs.progress_log
    # so frontend polling sees live updates. Existing log.append(...) calls
    # throughout the pipeline are unchanged — they just stream now.
    class _StreamingLog(list):
        def append(self, item):
            super().append(item)
            if db_progress and db_singleton is not None and job_id_override is not None:
                try:
                    db_singleton.update_job_progress(job_id_override, log_append=str(item))
                except Exception:
                    pass

    log: list = _StreamingLog()

    def report(step: int | None = None, msg: str | None = None, log_line: str | None = None):
        if log_line is not None:
            log.append(log_line)
        if not db_progress or db_singleton is None or job_id_override is None:
            return
        if step is not None:
            current_step["n"] = step
        try:
            db_singleton.update_job_progress(
                job_id_override,
                step=current_step["n"],
                total=total_steps,
                message=msg,
            )
        except Exception:
            pass

    # 1. Resolve input — either staged upload (preferred) or legacy direct file
    upload_path: Path | None = None
    if upload_id:
        upload_path = _find_upload(upload_id)
        if not upload_path:
            raise HTTPException(status_code=404, detail=f"upload_id {upload_id} not found")
        source_name = upload_path.name.split("_", 1)[1] if "_" in upload_path.name else upload_path.name
        log.append(f"$ rtm-agent classify --from-upload {upload_id[:8]}")
        log.append(f"[INFO] Source: {source_name} ({upload_path.stat().st_size / (1024*1024):.1f} MB on disk)")
    elif file:
        source_name = file.filename or "upload.csv"
        log.append("$ rtm-agent upload --parse-csv (legacy direct upload)")
    else:
        raise HTTPException(status_code=400, detail="Provide upload_id or file")

    log.append("$ rtm-agent upload --parse-csv")
    sales_df = None
    for encoding in ("utf-8", "latin-1", "cp1252"):
        try:
            if upload_path:
                sales_df = pd.read_csv(upload_path, encoding=encoding, low_memory=False)
            else:
                raw_bytes = await file.read()
                sales_df = pd.read_csv(io.BytesIO(raw_bytes), encoding=encoding, low_memory=False)
            log.append(f"[OK] CSV parsed ({encoding}): {len(sales_df):,} rows, {len(sales_df.columns)} columns")
            break
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue

    if sales_df is None:
        # cleanup staged file on parse failure
        if upload_path and upload_path.exists():
            upload_path.unlink()
        raise HTTPException(status_code=400, detail="Could not parse CSV with any supported encoding (utf-8, latin-1, cp1252)")

    # Validate required columns
    log.append("$ rtm-agent validate --check-schema")
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

    # 2. Start a job (reuse pre-reserved id if caller supplied one)
    job_manager = get_job_manager()
    if job_id_override:
        job_id = job_id_override
    else:
        job_id = job_manager.start_job(
            sales_filename=source_name,
            customer_filename="",
            item_filename="",
            threshold_a=threshold_a,
            threshold_b=threshold_b,
        )
    log.append(f"[INFO] Job ID: {job_id[:8]}...")
    report(step=1, msg="Validating + parsing CSV", log_line=None)

    try:
        # 3. Run classification pipeline (with the active rule config)
        report(step=2, msg="Running Pareto classification per branch")
        rule_cfg = load_rule_config()
        log.append("$ rtm-agent classify --method pareto --partition branch")
        log.append(f"[INFO] Rule config: Pareto {rule_cfg['pareto']['class_a_cutoff']}/{rule_cfg['pareto']['class_b_cutoff']}, "
                   f"wholesaler >={rule_cfg['wholesaler']['cartons_per_brand_month']} cartons")
        classifier = RTMClassifier(sales_df, config=rule_cfg)
        results_df = await run_in_threadpool(classifier.process)

        n_branches = int(results_df["BranchName"].nunique()) if "BranchName" in results_df.columns else 0
        log.append(f"[OK] {len(results_df):,} outlets classified across {n_branches} branches")
        if "Classification" in results_df.columns:
            for cls_name, cnt in results_df["Classification"].value_counts().items():
                log.append(f"[RESULT] {cls_name}: {cnt:,}")
        if classifier.min_date and classifier.max_date:
            log.append(f"[INFO] Date range: {classifier.min_date.date()} to {classifier.max_date.date()}")
        ws_col_count = int(results_df["Is_Wholesaler"].sum()) if "Is_Wholesaler" in results_df.columns else 0
        log.append(f"[INFO] Wholesalers detected: {ws_col_count}")

        # 4. AI enrichment + insights — parallelized
        # ──────────────────────────────────────────
        # Strategy: fan out independent LLM calls concurrently.
        #   - 3 macro insight calls (exec / recs / growth) run in parallel
        #   - per-outlet enrichment splits top-N into chunks, fired in parallel
        #     (gated by ai.max_concurrent semaphore)
        #   - both batches gathered together so total elapsed ≈ max() not sum()
        report(step=4, msg="AI enrichment + insights (parallel + chunked)")
        import time as _time
        ai_t0 = _time.time()
        log.append("$ rtm-agent enrich --parallel --chunked")
        ai_service = get_ai_service()
        ai_service.apply_config(rule_cfg)
        usage_sink: list = []

        enrich_task = ai_service.enrich_outlets_chunked(results_df, rule_cfg, usage_sink)
        insights_task = ai_service.generate_all_insights_parallel(results_df, usage_sink)
        results_df, insights = await asyncio.gather(enrich_task, insights_task)
        ai_elapsed = _time.time() - ai_t0

        if "AI_Growth_Signal" in results_df.columns:
            for signal, cnt in results_df["AI_Growth_Signal"].value_counts().items():
                log.append(f"[AI] {signal}: {cnt:,} outlets")
        n_chunks = (max(1, ai_service.enrich_top_n) + ai_service.chunk_size - 1) // ai_service.chunk_size
        log.append(f"[OK] AI complete — 3 macro calls + {n_chunks} outlet chunks (max {ai_service.max_concurrent} concurrent) in {ai_elapsed:.1f}s")

        report(step=5, msg="Calculating purchase frequency + workload")
        # 5b. Workload data
        workload = []
        if hasattr(classifier, 'route_workload') and classifier.route_workload is not None:
            workload = df_to_records(classifier.route_workload)

        # 6. Build branch summary
        report(step=6, msg="Building per-branch summary matrix")
        branch_summary_df = classifier.get_branch_summary()
        branch_summary = df_to_records(branch_summary_df) if branch_summary_df is not None else []

        # 7. Save to database via job manager (bulk COPY)
        report(step=7, msg="Bulk COPY classification results to Postgres")
        date_from = str(classifier.min_date.date()) if classifier.min_date else None
        date_to = str(classifier.max_date.date()) if classifier.max_date else None
        wl_df = classifier.route_workload if hasattr(classifier, 'route_workload') else None
        await run_in_threadpool(job_manager.complete_job, job_id, results_df,
                                date_from, date_to, None, wl_df)
        get_database().save_job_rule_config(job_id, rule_cfg)
        # Run metadata: who ran it + which rule-config version was active
        _lv = get_database().latest_rule_config_version()
        get_database().save_job_meta(job_id, user["username"], user["user_id"], _lv["id"] if _lv else 0)
        # LLM token usage + real OpenRouter cost for this run
        llm_usage = summarize_usage(usage_sink)
        get_database().save_job_usage(job_id, llm_usage["prompt_tokens"],
                                      llm_usage["completion_tokens"], llm_usage["cost"])
        log.append(f"[COST] LLM: {llm_usage['total_tokens']:,} tokens across "
                   f"{llm_usage['calls']} calls — ${llm_usage['cost']:.4f}")
        log.append("[OK] Job saved to database")

        # Audit log
        db = get_database()
        db.log_action(user["username"], "CLASSIFY", f"Job {job_id}: {len(results_df)} outlets, {n_branches} branches")

        # 8. Compute summary counts — F4 broken out as first-class metric.
        # Class A breakdown:
        #   - class_a_pure : exactly "Class A" (Pareto-ranked, no special rule)
        #   - class_a_f4   : "Class A Local (F4)" — forced-A wholesaler/distributor
        #   - class_a_cat  : "Class A {Nutrition/Food/Non Food}" — category override
        #   - class_a      : sum of all above (legacy field kept for back-compat)
        class_counts = results_df["Classification"].value_counts().to_dict()
        rev_by_cls: dict = {}
        if "TotalSales_2Yr" in results_df.columns:
            rev_by_cls = results_df.groupby("Classification")["TotalSales_2Yr"].sum().to_dict()

        def _r(label: str) -> float:
            v = rev_by_cls.get(label, 0)
            try:
                return float(v) if v is not None else 0.0
            except Exception:
                return 0.0

        class_a_pure = int(class_counts.get("Class A", 0))
        class_a_f4 = int(class_counts.get("Class A Local (F4)", 0))
        class_a_cat = int(sum(v for k, v in class_counts.items()
                              if k.startswith("Class A") and k not in ("Class A", "Class A Local (F4)")))
        class_a = class_a_pure + class_a_f4 + class_a_cat
        class_b = int(class_counts.get("Class B", 0))
        class_c = int(class_counts.get("Class C", 0))

        rev_a_pure = _r("Class A")
        rev_a_f4 = _r("Class A Local (F4)")
        rev_a_cat = sum(_r(k) for k in class_counts if k.startswith("Class A") and k not in ("Class A", "Class A Local (F4)"))
        rev_a = rev_a_pure + rev_a_f4 + rev_a_cat
        rev_b = _r("Class B")
        rev_c = _r("Class C")

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
        report(step=8, msg="Saving AI insights + data quality")
        db = get_database()
        db.save_job_insights(job_id, insights, data_quality)

        # 10. Build response
        report(step=9, msg="Computing run-vs-previous comparison")
        results_records = df_to_records(results_df)
        comparison = await run_in_threadpool(compute_run_comparison, job_id)
        report(step=10, msg="Building response payload")

        return {
            "job_id": job_id,
            "total_outlets": len(results_df),
            "branches": branches,
            "class_a": class_a,
            "class_a_pure": class_a_pure,
            "class_a_f4": class_a_f4,
            "class_a_cat": class_a_cat,
            "class_b": class_b,
            "class_c": class_c,
            "f4_count": class_a_f4,
            "wholesalers": ws_count,
            "revenue": total_revenue,
            "rev_a": rev_a,
            "rev_a_pure": rev_a_pure,
            "rev_a_f4": rev_a_f4,
            "rev_a_cat": rev_a_cat,
            "rev_b": rev_b,
            "rev_c": rev_c,
            "results": results_records,
            "workload": workload,
            "branch_summary": branch_summary,
            "insights": insights,
            "log": log,
            "data_quality": data_quality,
            "data_quality_ok": good_checks,
            "comparison": comparison,
            "llm_usage": llm_usage,
        }

    except HTTPException:
        raise
    except Exception as e:
        try:
            job_manager.fail_job(job_id, str(e))
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")
    finally:
        # Clean up staged upload after processing (success or failure)
        if upload_path and upload_path.exists():
            try:
                upload_path.unlink()
            except Exception:
                pass


# POST /api/classify — sync wrapper (back-compat). Blocks for full run.
@app.post("/api/classify")
async def classify(
    upload_id: str = Query(None, description="Use prior /api/upload result"),
    file: UploadFile = File(None),
    threshold_a: int = Query(80, ge=50, le=95),
    threshold_b: int = Query(95, ge=55, le=99),
    user: dict = Depends(require_auth),
):
    result = await _run_classify_pipeline(upload_id, file, threshold_a, threshold_b, user)
    return JSONResponse(content=result)


# POST /api/classify-async — returns instantly. Production-safe behind any LB.
@app.post("/api/classify-async")
async def classify_async(
    upload_id: str = Query(None),
    threshold_a: int = Query(80, ge=50, le=95),
    threshold_b: int = Query(95, ge=55, le=99),
    user: dict = Depends(require_auth),
):
    if not upload_id:
        raise HTTPException(status_code=400, detail="upload_id required for async classify")
    if not _find_upload(upload_id):
        raise HTTPException(status_code=404, detail=f"upload_id {upload_id} not found")

    job_manager = get_job_manager()
    job_id = job_manager.start_job(
        sales_filename=upload_id,
        customer_filename="",
        item_filename="",
        threshold_a=threshold_a,
        threshold_b=threshold_b,
    )
    get_database().update_job_progress(job_id, step=0, total=10,
                                       message="queued",
                                       log_append="$ rtm-agent classify --async (queued)")

    async def _bg():
        try:
            payload = await _run_classify_pipeline(
                upload_id=upload_id, file=None,
                threshold_a=threshold_a, threshold_b=threshold_b,
                user=user, job_id_override=job_id, db_progress=True,
            )
            get_database().save_job_result_payload(job_id, json.dumps(payload, default=str))
            get_database().update_job_progress(job_id, step=10, total=10,
                                               message="done",
                                               log_append="[OK] ✓ Classification complete")
        except HTTPException as he:
            try:
                get_job_manager().fail_job(job_id, str(he.detail))
                get_database().update_job_progress(job_id, message=f"failed: {he.detail}",
                                                   log_append=f"[ERROR] {he.detail}")
            except Exception:
                pass
        except Exception as e:
            try:
                get_job_manager().fail_job(job_id, str(e))
                get_database().update_job_progress(job_id, message=f"failed: {e}",
                                                   log_append=f"[ERROR] {e}")
            except Exception:
                pass

    asyncio.create_task(_bg())
    return JSONResponse(content={
        "job_id": job_id,
        "status": "queued",
        "status_url": f"/api/jobs/{job_id}/status",
        "result_url": f"/api/jobs/{job_id}/result",
    })


# GET /api/jobs/{id}/status — poller endpoint
@app.get("/api/jobs/{job_id}/status")
async def job_status(job_id: str, user: dict = Depends(require_auth)):
    prog = get_database().get_job_progress(job_id)
    if not prog:
        raise HTTPException(status_code=404, detail="job not found")
    status = prog.get("status", "unknown")
    log_lines = (prog.get("progress_log") or "").splitlines()
    return JSONResponse(content={
        "job_id": job_id,
        "status": status,
        "step": prog.get("progress_step") or 0,
        "total": prog.get("progress_total") or 10,
        "message": prog.get("progress_message") or "",
        "log": log_lines[-200:],
        "ready": bool(prog.get("has_payload")) and status == "completed",
        "error": prog.get("error_message"),
    })


# GET /api/jobs/{id}/result — fetch saved full response payload
@app.get("/api/jobs/{job_id}/result")
async def job_result(job_id: str, user: dict = Depends(require_auth)):
    payload = get_database().get_job_result_payload(job_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="result not ready or job not found")
    try:
        return JSONResponse(content=json.loads(payload))
    except Exception:
        raise HTTPException(status_code=500, detail="stored payload corrupt")


# ──────────────────────────────────────────────
# GET /api/jobs
# ──────────────────────────────────────────────
def _can_see_all_jobs(user: dict) -> bool:
    return user["role"] in ("admin", "super_admin")

def _job_visible(user: dict, job: dict, shared_ids: set) -> bool:
    """A user sees a job if they're admin+, ran it, or it was shared with them."""
    if _can_see_all_jobs(user):
        return True
    return job.get("run_by") == user["username"] or job.get("job_id") in shared_ids


@app.get("/api/jobs")
async def list_jobs(user: dict = Depends(require_auth)):
    """Jobs the user may see — own + shared, or all for admin+."""
    db = get_database()
    jobs = db.get_all_jobs(limit=200)
    if not _can_see_all_jobs(user):
        shared = set(db.get_shared_job_ids(user["user_id"]))
        jobs = [j for j in jobs if _job_visible(user, j, shared)]
    jobs = jobs[:50]
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
def get_job(job_id: str, user: dict = Depends(require_auth)):
    """Return single job details with full results."""
    db = get_database()
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    if not _job_visible(user, job, set(db.get_shared_job_ids(user["user_id"]))):
        raise HTTPException(status_code=403, detail="You do not have access to this job")

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
    """Generate and return an Excel report for the given job (always rebuilt
    fresh so it carries the run-info stamp and the vs-previous comparison)."""
    job_manager = get_job_manager()
    db = get_database()

    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    results_df = db.get_job_results(job_id)
    if results_df.empty:
        raise HTTPException(status_code=404, detail=f"No results found for job {job_id}")

    # Reverse the column mapping so DataFrame has original column names for the report
    results_df = results_df.rename(columns={"Cus_Code": "Cus.Code", "Cus_Name": "Cus.Name"})

    meta = build_job_meta(job)
    comparison = await run_in_threadpool(compute_run_comparison, job_id)
    # Excel build is heavy — run off the event loop
    excel_bytes = await run_in_threadpool(
        job_manager.create_excel_report, results_df, None, meta, comparison
    )

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
async def get_settings(user: dict = Depends(require_super_admin)):
    ai_service = get_ai_service()
    db = get_database()
    jobs = db.get_all_jobs(limit=1000)

    settings_file = Path(__file__).parent.parent / "data" / "settings.json"
    saved = {}
    if settings_file.exists():
        saved = json.loads(settings_file.read_text())

    return JSONResponse(content={
        "model": ai_service.model,                       # effective model (override or env)
        "base_url": ai_service.base_url,                 # effective base URL
        "api_configured": bool(ai_service.api_key),
        "llm_model": saved.get("llm_model", ""),         # saved override ("" = use env)
        "llm_base_url": saved.get("llm_base_url", ""),
        "env_model": ai_service.env_model,
        "env_base_url": ai_service.env_base_url,
        "total_jobs": len(jobs),
        "default_threshold_a": saved.get("threshold_a", 80),
        "default_threshold_b": saved.get("threshold_b", 95),
        "version": "1.0",
        "team": "City AI Team",
        "org": "City Holdings Myanmar",
    })


@app.post("/api/llm-test")
async def llm_test(body: dict, user: dict = Depends(require_super_admin)):
    """Test the LLM connection with an optional model/base-URL override."""
    ai_service = get_ai_service()
    result = ai_service.test_connection(
        model=(body.get("model") or None),
        base_url=(body.get("base_url") or None),
    )
    return JSONResponse(content=result)


# ──────────────────────────────────────────────
# LDAP / Active Directory configuration (super-admin)
# ──────────────────────────────────────────────
@app.get("/api/ldap-config")
async def get_ldap_config(user: dict = Depends(require_super_admin)):
    """Return all LDAP servers — service-account passwords are never exposed."""
    cfg = load_ldap_config()
    for s in cfg["servers"]:
        s["app_password_set"] = bool(s.get("app_password"))
        s["app_password"] = ""
    return JSONResponse(content=cfg)


@app.post("/api/ldap-config")
async def save_ldap_config_ep(body: dict, user: dict = Depends(require_super_admin)):
    """Persist the LDAP server list. A blank app_password keeps the stored one
    (matched by server id)."""
    existing = {s["id"]: s for s in load_ldap_config()["servers"]}
    servers = body.get("servers") or []
    for s in servers:
        if not s.get("app_password") and s.get("id") in existing:
            s["app_password"] = existing[s["id"]].get("app_password", "")
    merged = save_ldap_config({"merge_by_email": bool(body.get("merge_by_email", True)), "servers": servers})
    get_database().log_action(user["username"], "SETTINGS",
                              f"Updated LDAP config ({len(merged['servers'])} server(s))")
    for s in merged["servers"]:
        s["app_password_set"] = bool(s.get("app_password"))
        s["app_password"] = ""
    return {"ok": True, "config": merged}


@app.post("/api/ldap-test")
async def ldap_test_ep(body: dict, user: dict = Depends(require_super_admin)):
    """Test one LDAP server's service-account bind. Blank password uses the saved one."""
    s = dict(body)
    if not s.get("app_password") and s.get("id"):
        existing = {x["id"]: x for x in load_ldap_config()["servers"]}
        if s["id"] in existing:
            s["app_password"] = existing[s["id"]].get("app_password", "")
    return JSONResponse(content=ldap_test(s))


@app.post("/api/settings")
async def update_settings(body: dict, user: dict = Depends(require_super_admin)):
    """Save system settings — thresholds and LLM model/provider (super-admin only)."""
    settings_file = Path(__file__).parent.parent / "data" / "settings.json"
    settings_file.parent.mkdir(parents=True, exist_ok=True)

    current = {}
    if settings_file.exists():
        current = json.loads(settings_file.read_text())

    if "threshold_a" in body:
        current["threshold_a"] = int(body["threshold_a"])
    if "threshold_b" in body:
        current["threshold_b"] = int(body["threshold_b"])
    if "llm_model" in body:
        current["llm_model"] = str(body["llm_model"]).strip()
    if "llm_base_url" in body:
        current["llm_base_url"] = str(body["llm_base_url"]).strip()

    settings_file.write_text(json.dumps(current, indent=2))

    db = get_database()
    db.log_action(user["username"], "SETTINGS", "Updated system settings")

    return {"ok": True, **current}


# ──────────────────────────────────────────────
# GET /api/f4-analysis
# ──────────────────────────────────────────────
@app.get("/api/f4-analysis")
def f4_analysis(
    job_id: str = Query(None),
    user: dict = Depends(require_auth),
):
    """F4 distributor deep-dive — health, churn risk, leaderboard, per-branch breakdown."""
    db = get_database()
    if not job_id:
        jobs = db.get_all_jobs(limit=1)
        if not jobs:
            return JSONResponse(content={"job_id": None, "f4_count": 0, "f4_outlets": [],
                                         "by_branch": [], "top10": [], "churn_risk": []})
        job_id = jobs[0]["job_id"]

    df = db.get_job_results(job_id)
    if df.empty:
        raise HTTPException(status_code=404, detail="job not found")

    # Detect F4 — Classification contains F4 OR Is_Wholesaler flag
    cls_col = "Classification"
    is_f4 = df[cls_col].astype(str).str.contains("F4", case=False, na=False)
    if "Is_Wholesaler" in df.columns:
        is_f4 = is_f4 | df["Is_Wholesaler"].fillna(False).astype(bool)
    f4_df = df[is_f4].copy()

    code_col = "Cus.Code" if "Cus.Code" in df.columns else "Cus_Code"
    name_col = "Cus.Name" if "Cus.Name" in df.columns else "Cus_Name"
    branch_col = "BranchName" if "BranchName" in df.columns else "Branch"

    def _f(v):
        try:
            v = float(v) if v is not None else 0.0
            return v if not (pd.isna(v) or pd.isinf(v)) else 0.0
        except Exception:
            return 0.0

    # Per-branch breakdown
    by_branch = []
    if branch_col in df.columns:
        for branch in sorted(df[branch_col].dropna().unique()):
            b_all = df[df[branch_col] == branch]
            b_f4 = f4_df[f4_df[branch_col] == branch]
            by_branch.append({
                "branch": str(branch),
                "total_outlets": int(len(b_all)),
                "f4_count": int(len(b_f4)),
                "f4_pct": round(len(b_f4) / max(1, len(b_all)) * 100, 1),
                "f4_revenue": _f(b_f4["TotalSales_2Yr"].sum()) if "TotalSales_2Yr" in b_f4.columns else 0.0,
                "branch_revenue": _f(b_all["TotalSales_2Yr"].sum()) if "TotalSales_2Yr" in b_all.columns else 0.0,
            })
        for b in by_branch:
            b["revenue_share"] = round((b["f4_revenue"] / b["branch_revenue"] * 100) if b["branch_revenue"] else 0.0, 1)

    # Top-10 by revenue
    top10 = []
    if not f4_df.empty and "TotalSales_2Yr" in f4_df.columns:
        for _, r in f4_df.nlargest(10, "TotalSales_2Yr").iterrows():
            top10.append({
                "code": str(r.get(code_col, "")),
                "name": str(r.get(name_col, "")),
                "branch": str(r.get(branch_col, "")),
                "revenue_2yr": _f(r.get("TotalSales_2Yr", 0)),
                "revenue_6m": _f(r.get("TotalSales_6M", 0)),
                "revenue_3m": _f(r.get("TotalSales_3M", 0)),
                "growth": str(r.get("AI_Growth_Signal", "")),
                "risk": str(r.get("AI_Risk_Level", "")),
            })

    # Churn-risk F4 — Declining growth OR High risk
    churn = []
    if not f4_df.empty:
        risk_df = f4_df.copy()
        risk_mask = (
            risk_df.get("AI_Growth_Signal", pd.Series([""] * len(risk_df))).astype(str).eq("Declining") |
            risk_df.get("AI_Risk_Level", pd.Series([""] * len(risk_df))).astype(str).eq("High")
        )
        risk_df = risk_df[risk_mask]
        if "TotalSales_2Yr" in risk_df.columns:
            risk_df = risk_df.sort_values("TotalSales_2Yr", ascending=False).head(20)
        for _, r in risk_df.iterrows():
            churn.append({
                "code": str(r.get(code_col, "")),
                "name": str(r.get(name_col, "")),
                "branch": str(r.get(branch_col, "")),
                "revenue_2yr": _f(r.get("TotalSales_2Yr", 0)),
                "revenue_6m": _f(r.get("TotalSales_6M", 0)),
                "growth": str(r.get("AI_Growth_Signal", "")),
                "risk": str(r.get("AI_Risk_Level", "")),
                "lifecycle": str(r.get("Lifecycle_Stage", "")),
            })

    # Overall health metrics
    total_f4 = int(len(f4_df))
    declining = int((f4_df.get("AI_Growth_Signal", pd.Series(dtype=str)) == "Declining").sum()) if not f4_df.empty else 0
    growing = int((f4_df.get("AI_Growth_Signal", pd.Series(dtype=str)) == "Growing").sum()) if not f4_df.empty else 0
    high_risk = int((f4_df.get("AI_Risk_Level", pd.Series(dtype=str)) == "High").sum()) if not f4_df.empty else 0
    f4_revenue = _f(f4_df["TotalSales_2Yr"].sum()) if not f4_df.empty and "TotalSales_2Yr" in f4_df.columns else 0.0
    total_revenue = _f(df["TotalSales_2Yr"].sum()) if "TotalSales_2Yr" in df.columns else 0.0
    health_score = max(0, 100 - (declining / max(1, total_f4) * 50) - (high_risk / max(1, total_f4) * 30))

    return JSONResponse(content={
        "job_id": job_id,
        "f4_count": total_f4,
        "f4_revenue": f4_revenue,
        "total_revenue": total_revenue,
        "revenue_share_pct": round((f4_revenue / total_revenue * 100) if total_revenue else 0, 1),
        "growing": growing,
        "declining": declining,
        "high_risk": high_risk,
        "health_score": round(health_score, 1),
        "by_branch": by_branch,
        "top10": top10,
        "churn_risk": churn,
    })


# ──────────────────────────────────────────────
# GET /api/rtm-data
# ──────────────────────────────────────────────
@app.get("/api/rtm-data")
def get_rtm_data(
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
def compare_jobs(
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
def get_coverage(
    job_id: str = Query(None),
    user: dict = Depends(require_auth),
):
    """Return outlet locations (lat/long from the classified data) for the map."""
    db = get_database()

    if not job_id:
        jobs = db.get_all_jobs(limit=1)
        if not jobs:
            return JSONResponse(content={"outlets": [], "summary": {}})
        job_id = jobs[0]["job_id"]

    results_df = db.get_job_results(job_id)
    if results_df.empty:
        return JSONResponse(content={"outlets": [], "summary": {}})

    code_col = 'Cus_Code' if 'Cus_Code' in results_df.columns else 'Cus.Code'
    name_col = 'Cus_Name' if 'Cus_Name' in results_df.columns else 'Cus.Name'
    has_geo = 'Latitude' in results_df.columns and 'Longitude' in results_df.columns

    outlets = []
    for _, r in results_df.iterrows():
        lat = r.get('Latitude') if has_geo else None
        lng = r.get('Longitude') if has_geo else None
        valid = has_geo and pd.notna(lat) and pd.notna(lng) and lat not in (0, 0.0) and lng not in (0, 0.0)
        outlets.append({
            'code': str(r.get(code_col, '')),
            'name': str(r.get(name_col, '')),
            'branch': str(r.get('BranchName', '')),
            'classification': str(r.get('Classification', '')),
            'township': str(r.get('Township', '') or '') if 'Township' in results_df.columns else '',
            'lat': float(lat) if valid else None,
            'lng': float(lng) if valid else None,
            'revenue': float(r.get('TotalSales_2Yr', 0) or 0),
            'contact': str(r.get('CntctPrsn', '') or '') if 'CntctPrsn' in results_df.columns else '',
            'phone': str(r.get('Phone1', '') or '') if 'Phone1' in results_df.columns else '',
            'address': str(r.get('Address', '') or '') if 'Address' in results_df.columns else '',
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
        'outlets': outlets[:20000],
        'summary': township_summary,
        'total_with_geo': len([o for o in outlets if o['lat'] is not None]),
        'total_without_geo': len([o for o in outlets if o['lat'] is None]),
    })


# ──────────────────────────────────────────────
# Classification rule config (editable by admin)
# ──────────────────────────────────────────────
RULE_CONFIG_FILE = Path(__file__).parent.parent / "data" / "rule_config.json"

def load_rule_config() -> dict:
    """Load saved rule parameters merged over defaults (missing keys safe)."""
    from backend.rule_defaults import merge_rules
    if RULE_CONFIG_FILE.exists():
        try:
            return merge_rules(json.loads(RULE_CONFIG_FILE.read_text()))
        except Exception:
            pass
    return merge_rules({})

@app.get("/api/rule-config")
async def get_rule_config(user: dict = Depends(require_auth)):
    """Return the active classification rule parameters."""
    return JSONResponse(content=load_rule_config())

@app.post("/api/rule-config")
async def save_rule_config(body: dict, user: dict = Depends(require_perm("rules"))):
    """Persist edited classification rule parameters + append a history version."""
    from backend.rule_defaults import merge_rules
    merged = merge_rules(body)
    RULE_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    RULE_CONFIG_FILE.write_text(json.dumps(merged, indent=2))
    db = get_database()
    version_id = db.add_rule_config_version(merged, user["user_id"], user["username"], "Updated rule config")
    db.log_action(user["username"], "SETTINGS", f"Updated rule config (v{version_id})")
    return {"ok": True, "config": merged, "version": version_id}


@app.get("/api/rule-config/history")
async def rule_config_history(user: dict = Depends(require_perm("rules"))):
    """Return the rule-config change history (newest first)."""
    db = get_database()
    rows = db.get_rule_config_history(limit=100)
    for r in rows:
        try:
            r["config"] = json.loads(r.pop("config_json"))
        except Exception:
            r["config"] = {}
    return JSONResponse(content=rows)


@app.post("/api/rule-config/rollback/{version_id}")
async def rule_config_rollback(version_id: int, user: dict = Depends(require_perm("rules"))):
    """Restore a previous rule-config version (logged as a new version)."""
    from backend.rule_defaults import merge_rules
    db = get_database()
    ver = db.get_rule_config_version(version_id)
    if not ver:
        raise HTTPException(status_code=404, detail=f"Version {version_id} not found")
    cfg = merge_rules(json.loads(ver["config_json"]))
    RULE_CONFIG_FILE.write_text(json.dumps(cfg, indent=2))
    new_id = db.add_rule_config_version(cfg, user["user_id"], user["username"], f"Rolled back to v{version_id}")
    db.log_action(user["username"], "SETTINGS", f"Rolled back rule config to v{version_id}")
    return {"ok": True, "config": cfg, "version": new_id}


# ──────────────────────────────────────────────
# Run-vs-run comparison
# ──────────────────────────────────────────────
def build_job_meta(job: dict) -> dict:
    """Build the run-info metadata block for a job (used in the Excel report)."""
    db = get_database()
    rule_ver = job.get("rule_version")
    modified_at = modified_by = "—"
    if rule_ver:
        v = db.get_rule_config_version(rule_ver)
        if v:
            modified_at = v["timestamp"]
            modified_by = f"{v['username']} (user #{v['user_id']})"
    tokens = int((job.get("llm_prompt_tokens") or 0) + (job.get("llm_completion_tokens") or 0))
    return {
        "job_id": job.get("job_id", ""),
        "run_date": str(job.get("created_at", "")),
        "run_by": job.get("run_by") or "—",
        "run_by_id": job.get("run_by_id") or "—",
        "rule_version": f"v{rule_ver}" if rule_ver else "default (unmodified)",
        "rule_modified_at": modified_at,
        "rule_modified_by": modified_by,
        "llm_tokens": f"{tokens:,}",
        "llm_cost": f"${float(job.get('llm_cost') or 0):.4f}",
    }


def compute_run_comparison(job_id: str) -> dict:
    """Compare a job against the immediately previous job with results."""
    db = get_database()
    jobs = db.get_all_jobs(limit=200)  # newest first
    idx = next((i for i, j in enumerate(jobs) if j["job_id"] == job_id), None)
    if idx is None:
        return {"has_previous": False}
    curr = jobs[idx]
    curr_df = db.get_job_results(job_id)
    if curr_df.empty:
        return {"has_previous": False}

    prev = prev_df = None
    for j in jobs[idx + 1:]:
        pdf = db.get_job_results(j["job_id"])
        if not pdf.empty:
            prev, prev_df = j, pdf
            break
    if prev is None:
        return {"has_previous": False}

    def cls_counts(df):
        c = df["Classification"].astype(str)
        return {
            "total": len(df),
            "a": int(c.str.startswith("Class A").sum()),
            "b": int((c == "Class B").sum()),
            "c": int((c == "Class C").sum()),
            "ws": int(df["Is_Wholesaler"].sum()) if "Is_Wholesaler" in df.columns else 0,
            "rev": float(df["TotalSales_2Yr"].sum()) if "TotalSales_2Yr" in df.columns else 0.0,
        }

    cc, pc = cls_counts(curr_df), cls_counts(prev_df)

    def mkrow(metric, cur, prv):
        change = cur - prv
        pct = (change / prv * 100) if prv else 0.0
        if not prv:
            remark, alert = "New", True
        else:
            direction = "Up" if change > 0 else "Down" if change < 0 else "No change"
            remark = f"{direction} {pct:+.1f}%" if change else direction
            alert = abs(pct) >= 15  # swing alert — large shift vs previous run
            if alert:
                remark += " — large shift"
        return {"metric": metric, "current": cur, "previous": prv,
                "change": change, "pct": round(pct, 1), "remark": remark, "alert": alert}

    summary = [
        mkrow("Total Outlets", cc["total"], pc["total"]),
        mkrow("Class A", cc["a"], pc["a"]),
        mkrow("Class B", cc["b"], pc["b"]),
        mkrow("Class C", cc["c"], pc["c"]),
        mkrow("Wholesalers (F4)", cc["ws"], pc["ws"]),
        mkrow("Revenue (2Yr)", round(cc["rev"]), round(pc["rev"])),
    ]

    def group_compare(col):
        if col not in curr_df.columns or col not in prev_df.columns:
            return []
        cur_g = curr_df.groupby(col).size().to_dict()
        prv_g = prev_df.groupby(col).size().to_dict()
        keys = sorted(set(cur_g) | set(prv_g), key=lambda k: -cur_g.get(k, 0))
        return [mkrow(str(k), int(cur_g.get(k, 0)), int(prv_g.get(k, 0))) for k in keys]

    by_channel = group_compare("OutletChannel")
    by_branch = group_compare("BranchName")

    # Outlet movement (matched by customer code)
    code = "Cus_Code" if "Cus_Code" in curr_df.columns else "Cus.Code"
    rank = {"Class A": 1, "Class A Local (F4)": 1, "Class B": 2, "Class C": 3}
    cur_map = dict(zip(curr_df[code].astype(str), curr_df["Classification"].astype(str)))
    prv_map = dict(zip(prev_df[code].astype(str), prev_df["Classification"].astype(str)))
    cur_set, prv_set = set(cur_map), set(prv_map)
    upgraded = downgraded = unchanged = 0
    for c in cur_set & prv_set:
        ro = rank.get(prv_map[c], 9)
        rn = rank.get(cur_map[c], 9)
        if rn < ro:
            upgraded += 1
        elif rn > ro:
            downgraded += 1
        else:
            unchanged += 1
    movement = {
        "upgraded": upgraded, "downgraded": downgraded, "unchanged": unchanged,
        "new": len(cur_set - prv_set), "lost": len(prv_set - cur_set),
    }

    return {
        "has_previous": True,
        "current": {"job_id": curr["job_id"], "created_at": str(curr.get("created_at", ""))},
        "previous": {"job_id": prev["job_id"], "created_at": str(prev.get("created_at", ""))},
        "summary": summary,
        "by_channel": by_channel,
        "by_branch": by_branch,
        "movement": movement,
    }


@app.get("/api/jobs/{job_id}/comparison")
def job_comparison(job_id: str, user: dict = Depends(require_auth)):
    """Compare a job's results against the immediately previous run."""
    return JSONResponse(content=compute_run_comparison(job_id))


# ──────────────────────────────────────────────
# Job sharing (one-to-one)
# ──────────────────────────────────────────────
@app.get("/api/jobs/{job_id}/shares")
async def get_job_shares_ep(job_id: str, user: dict = Depends(require_auth)):
    """Return the user ids a job is currently shared with."""
    db = get_database()
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"user_ids": db.get_job_share_user_ids(job_id)}

@app.post("/api/jobs/{job_id}/share")
async def share_job_ep(job_id: str, body: dict, user: dict = Depends(require_auth)):
    """Set the users a job is shared with. Only the job owner or an admin can share."""
    db = get_database()
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    is_owner = job.get("run_by") == user["username"]
    if not (is_owner or user["role"] in ("admin", "super_admin")):
        raise HTTPException(status_code=403, detail="Only the job owner or an admin can share this job")
    user_ids = [int(u) for u in (body.get("user_ids") or [])]
    db.set_job_shares(job_id, user_ids, user["username"])
    db.log_action(user["username"], "SETTINGS", f"Shared job {job_id} with {len(user_ids)} user(s)")
    return {"ok": True}


# ──────────────────────────────────────────────
# Documentation content (editable by admin)
# ──────────────────────────────────────────────
DOCS_FILE = Path(__file__).parent.parent / "data" / "docs_content.json"

@app.get("/api/docs-content")
async def get_docs_content(user: dict = Depends(require_auth)):
    """Return documentation tabs (read-only — built-in reference content)."""
    from backend.docs_seed import DEFAULT_DOCS
    if DOCS_FILE.exists():
        try:
            return JSONResponse(content=json.loads(DOCS_FILE.read_text()))
        except Exception:
            pass
    return JSONResponse(content={"tabs": DEFAULT_DOCS})


# ──────────────────────────────────────────────
# GET /api/audit  — filterable audit-log explorer
# ──────────────────────────────────────────────
@app.get("/api/audit")
def get_audit(
    user: dict = Depends(require_perm("analytics")),
    username: str = Query(None),
    action: str = Query(None),
    date_from: str = Query(None),
    date_to: str = Query(None),
    q: str = Query(None),
    limit: int = Query(500, ge=1, le=5000),
):
    db = get_database()
    logs = db.get_audit_log(limit=5000)

    def keep(e):
        if username and username.lower() not in (e.get("username") or "").lower():
            return False
        if action and e.get("action") != action:
            return False
        ts = e.get("timestamp") or ""
        if date_from and ts < date_from:
            return False
        if date_to and ts > date_to + "T23:59:59":
            return False
        if q:
            blob = f"{e.get('username','')} {e.get('action','')} {e.get('details','')}".lower()
            if q.lower() not in blob:
                return False
        return True

    logs = [e for e in logs if keep(e)][:limit]
    clean = [{k: str(v) if v is not None else None for k, v in e.items()} for e in logs]
    return JSONResponse(content=clean)


# ──────────────────────────────────────────────
# GET /api/analytics  — platform usage analytics
# ──────────────────────────────────────────────
def compute_analytics() -> dict:
    """Aggregate audit log + jobs + users into a platform-analytics payload."""
    from datetime import datetime, timedelta
    db = get_database()
    audit = db.get_audit_log(limit=100000)
    jobs = db.get_all_jobs(limit=100000)
    users = list_users()
    now = datetime.now()

    def parse(ts):
        try:
            return datetime.fromisoformat(ts)
        except Exception:
            return None

    def days_since(ts):
        p = parse(ts)
        return (now - p).days if p else 99999

    def _num(v):
        """Coerce a DB value to a number — decodes legacy numpy BLOB bytes."""
        if isinstance(v, (int, float)):
            return v
        if isinstance(v, (bytes, bytearray)):
            try:
                return int.from_bytes(v, "little", signed=True)
            except Exception:
                return 0
        try:
            return float(v or 0)
        except Exception:
            return 0

    by_user = {u["username"]: {**u, "last_login": None, "login_count": 0,
                               "jobs_run": 0, "exports": 0, "last_active": None}
               for u in users}
    user_source = {u["username"]: u.get("source", "local") for u in users}
    user_server = {u["username"]: u.get("ldap_server", "") for u in users}

    actions_count, trend, hour_count = {}, {}, {}
    failed = []
    local_logins = ldap_logins = 0
    server_logins = {}

    for e in audit:
        ts = parse(e.get("timestamp"))
        un = e.get("username") or ""
        act = e.get("action") or ""
        actions_count[act] = actions_count.get(act, 0) + 1
        if ts:
            d = ts.date().isoformat()
            t = trend.setdefault(d, {"logins": 0, "jobs": 0, "actions": 0})
            t["actions"] += 1
            if act == "LOGIN":
                t["logins"] += 1
                hour_count[ts.hour] = hour_count.get(ts.hour, 0) + 1
        if un in by_user:
            bu = by_user[un]
            if act == "LOGIN":
                bu["login_count"] += 1
                if bu["last_login"] is None or (e.get("timestamp") or "") > bu["last_login"]:
                    bu["last_login"] = e.get("timestamp")
            if act == "EXPORT":
                bu["exports"] += 1
            if bu["last_active"] is None or (e.get("timestamp") or "") > (bu["last_active"] or ""):
                bu["last_active"] = e.get("timestamp")
        if act == "LOGIN_FAILED":
            failed.append({"username": un, "timestamp": e.get("timestamp"), "details": e.get("details", "")})
        if act == "LOGIN":
            if user_source.get(un) == "ldap":
                ldap_logins += 1
                srv = user_server.get(un) or "unknown"
                server_logins[srv] = server_logins.get(srv, 0) + 1
            else:
                local_logins += 1

    job_status = {"completed": 0, "failed": 0, "other": 0}
    jobs_per_user, rule_ver, cost_per_user = {}, {}, {}
    total_outlets = total_rev = n_completed = 0
    total_llm_cost = total_llm_tokens = 0
    for j in jobs:
        st = j.get("status", "")
        job_status[st if st in job_status else "other"] += 1
        rb = j.get("run_by") or "—"
        jobs_per_user[rb] = jobs_per_user.get(rb, 0) + 1
        if rb in by_user:
            by_user[rb]["jobs_run"] += 1
        rv = j.get("rule_version")
        rule_ver[f"v{rv}" if rv else "default"] = rule_ver.get(f"v{rv}" if rv else "default", 0) + 1
        ts = parse(j.get("created_at"))
        if ts:
            trend.setdefault(ts.date().isoformat(), {"logins": 0, "jobs": 0, "actions": 0})["jobs"] += 1
        # LLM cost / tokens — applies to every run
        jc = _num(j.get("llm_cost"))
        jt = _num(j.get("llm_prompt_tokens")) + _num(j.get("llm_completion_tokens"))
        total_llm_cost += jc
        total_llm_tokens += jt
        cost_per_user[rb] = cost_per_user.get(rb, 0.0) + jc
        if st == "completed":
            total_outlets += _num(j.get("total_outlets"))
            total_rev += _num(j.get("total_revenue"))
            n_completed += 1

    trend_arr = []
    for i in range(29, -1, -1):
        d = (now - timedelta(days=i)).date().isoformat()
        trend_arr.append({"date": d, **trend.get(d, {"logins": 0, "jobs": 0, "actions": 0})})

    user_rows = []
    for b in by_user.values():
        user_rows.append({
            "id": b["id"], "username": b["username"], "role": b["role"],
            "source": b.get("source", "local"), "email": b.get("email", ""),
            "disabled": b.get("disabled", False),
            "last_login": b["last_login"], "login_count": b["login_count"],
            "jobs_run": b["jobs_run"], "exports": b["exports"], "last_active": b["last_active"],
            "inactive": (not b["last_login"]) or days_since(b["last_login"]) > 30,
        })
    user_rows.sort(key=lambda r: -(r["login_count"] + r["jobs_run"]))

    top_users = sorted(
        [{"username": un, "count": by_user[un]["login_count"] + by_user[un]["jobs_run"] + by_user[un]["exports"]}
         for un in by_user],
        key=lambda x: -x["count"])[:10]

    this_m = now.strftime("%Y-%m")
    last_m = (now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")

    return {
        "overview": {
            "total_users": len(users),
            "active_7d": sum(1 for b in by_user.values() if b["last_login"] and days_since(b["last_login"]) <= 7),
            "active_30d": sum(1 for b in by_user.values() if b["last_login"] and days_since(b["last_login"]) <= 30),
            "total_logins": actions_count.get("LOGIN", 0),
            "total_jobs": len(jobs),
            "total_exports": actions_count.get("EXPORT", 0),
            "jobs_this_month": sum(1 for j in jobs if (j.get("created_at") or "").startswith(this_m)),
            "jobs_last_month": sum(1 for j in jobs if (j.get("created_at") or "").startswith(last_m)),
        },
        "trend": trend_arr,
        "users": user_rows,
        "actions": [{"action": k, "count": v} for k, v in sorted(actions_count.items(), key=lambda x: -x[1])],
        "top_users": top_users,
        "jobs": {
            "by_status": job_status,
            "avg_outlets": round(total_outlets / n_completed) if n_completed else 0,
            "total_revenue": total_rev,
            "per_user": sorted([{"username": k, "count": v} for k, v in jobs_per_user.items()], key=lambda x: -x["count"]),
            "by_rule_version": [{"version": k, "count": v} for k, v in sorted(rule_ver.items())],
        },
        "cost": {
            "total_cost": round(total_llm_cost, 4),
            "total_tokens": int(total_llm_tokens),
            "avg_cost_per_job": round(total_llm_cost / len(jobs), 4) if jobs else 0,
            "per_user": sorted(
                [{"username": k, "cost": round(v, 4)} for k, v in cost_per_user.items() if v > 0],
                key=lambda x: -x["cost"]),
        },
        "auth": {
            "local_logins": local_logins,
            "ldap_logins": ldap_logins,
            "by_server": [{"server": k, "count": v} for k, v in server_logins.items()],
            "failed_logins": len(failed),
            "recent_failures": failed[:20],
        },
        "peak": {
            "busiest_day": max(trend_arr, key=lambda t: t["actions"])["date"] if trend_arr else None,
            "busiest_hour": max(hour_count, key=hour_count.get) if hour_count else None,
        },
    }


@app.get("/api/analytics")
def get_analytics(user: dict = Depends(require_perm("analytics"))):
    """Platform usage analytics — users, activity, jobs, auth, logs."""
    return JSONResponse(content=compute_analytics())


# ============================================================
# SERVE SVELTEKIT STATIC BUILD (single port)
# ============================================================
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "build")

if os.path.isdir(STATIC_DIR):
    # Serve static assets (_app, js, css, etc.)
    app.mount("/_app", StaticFiles(directory=os.path.join(STATIC_DIR, "_app")), name="static_app")

    # index.html must never be cached, or browsers keep loading a stale app
    # (which references old JS hashes — e.g. missing new roles/nav).
    NO_CACHE = {"Cache-Control": "no-cache, no-store, must-revalidate"}

    # SPA fallback: serve index.html for all non-API routes (client-side routing)
    @app.get("/{path:path}")
    async def spa_fallback(path: str):
        # Serve actual files if they exist
        file_path = os.path.join(STATIC_DIR, path)
        if os.path.isfile(file_path) and not path.endswith(".html"):
            return FileResponse(file_path)
        # Otherwise serve index.html for SPA routing (always revalidated)
        return FileResponse(os.path.join(STATIC_DIR, "index.html"), headers=NO_CACHE)
