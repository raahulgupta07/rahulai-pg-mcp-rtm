#!/usr/bin/env python3
"""
PostgreSQL database layer for RTM Classification.
Stores job metadata, classification results, insights, audit log and
rule-config history. Uses a psycopg3 connection pool for concurrency.
pgvector is enabled (CREATE EXTENSION vector) for future similarity features.
"""

import os
import json
from datetime import datetime
from typing import Optional, List, Dict
import pandas as pd
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

DEFAULT_DSN = "postgresql://rtm:rtm@localhost:5432/rtm"

# job_results carries mixed-case column names — they must be quoted in DDL/DML
# so PostgreSQL preserves the exact case (unquoted identifiers fold to lowercase).
JOB_RESULTS_COLUMNS = [
    ("Cus_Code", "TEXT"), ("Cus_Name", "TEXT"), ("OutletChannel", "TEXT"),
    ("TotalSales_2Yr", "DOUBLE PRECISION DEFAULT 0"),
    ("TotalSales_12M", "DOUBLE PRECISION DEFAULT 0"),
    ("TotalSales_6M", "DOUBLE PRECISION DEFAULT 0"),
    ("TotalSales_3M", "DOUBLE PRECISION DEFAULT 0"),
    ("TotalPcs", "DOUBLE PRECISION DEFAULT 0"),
    ("TransactionCount", "INTEGER DEFAULT 0"),
    ("Nutrition_Sales_2Yr", "DOUBLE PRECISION DEFAULT 0"),
    ("Nutrition_Sales_12M", "DOUBLE PRECISION DEFAULT 0"),
    ("Nutrition_Sales_6M", "DOUBLE PRECISION DEFAULT 0"),
    ("Nutrition_Sales_3M", "DOUBLE PRECISION DEFAULT 0"),
    ("Food_Sales_2Yr", "DOUBLE PRECISION DEFAULT 0"),
    ("Food_Sales_12M", "DOUBLE PRECISION DEFAULT 0"),
    ("Food_Sales_6M", "DOUBLE PRECISION DEFAULT 0"),
    ("Food_Sales_3M", "DOUBLE PRECISION DEFAULT 0"),
    ("NonFood_Sales_2Yr", "DOUBLE PRECISION DEFAULT 0"),
    ("NonFood_Sales_12M", "DOUBLE PRECISION DEFAULT 0"),
    ("NonFood_Sales_6M", "DOUBLE PRECISION DEFAULT 0"),
    ("NonFood_Sales_3M", "DOUBLE PRECISION DEFAULT 0"),
    ("Local_Sales_2Yr", "DOUBLE PRECISION DEFAULT 0"),
    ("Import_Sales_2Yr", "DOUBLE PRECISION DEFAULT 0"),
    ("AvgSales_All_2Yr", "DOUBLE PRECISION DEFAULT 0"),
    ("AvgSales_Nutrition_2Yr", "DOUBLE PRECISION DEFAULT 0"),
    ("AvgSales_Food_2Yr", "DOUBLE PRECISION DEFAULT 0"),
    ("AvgSales_NonFood_2Yr", "DOUBLE PRECISION DEFAULT 0"),
    ("Overall_Contribution_Pct", "DOUBLE PRECISION DEFAULT 0"),
    ("Nutrition_Contribution_Pct", "DOUBLE PRECISION DEFAULT 0"),
    ("Food_Contribution_Pct", "DOUBLE PRECISION DEFAULT 0"),
    ("NonFood_Contribution_Pct", "DOUBLE PRECISION DEFAULT 0"),
    ("Local_Contribution_Pct", "DOUBLE PRECISION DEFAULT 0"),
    ("Import_Contribution_Pct", "DOUBLE PRECISION DEFAULT 0"),
    ("Is_Wholesaler", "INTEGER DEFAULT 0"),
    ("Base_Classification", "TEXT"), ("Classification", "TEXT"),
    ("CumulativeSales", "DOUBLE PRECISION DEFAULT 0"),
    ("CumulativePct", "DOUBLE PRECISION DEFAULT 0"),
    ("PurchaseDays_2Yr", "INTEGER DEFAULT 0"),
    ("PurchaseDays_12M", "INTEGER DEFAULT 0"),
    ("PurchaseDays_6M", "INTEGER DEFAULT 0"),
    ("Frequency_2Yr", "DOUBLE PRECISION DEFAULT 0"),
    ("FirstPurchaseDate", "TEXT"), ("LastPurchaseDate", "TEXT"),
    ("Growth_6M_vs_12M", "DOUBLE PRECISION DEFAULT 0"),
    ("Growth_3M_vs_6M", "DOUBLE PRECISION DEFAULT 0"),
    ("BranchName", "TEXT"),
    ("Latitude", "DOUBLE PRECISION"),
    ("Longitude", "DOUBLE PRECISION"),
    ("Township", "TEXT"),
    ("CntctPrsn", "TEXT"),
    ("Address", "TEXT"),
    ("Phone1", "TEXT"),
    ("Lifecycle_Stage", "TEXT"),
    ("RouteCode", "TEXT"),
    ("RouteName", "TEXT"),
    ("VAN", "TEXT"),
    ("SalesGroup", "TEXT"),
    ("Principal", "TEXT"),
    ("Route_SalesGroup", "TEXT"),
    ("Ref", "TEXT"),
]


def _coerce(v):
    """numpy scalar → native Python; bool → int (for INTEGER columns)."""
    if hasattr(v, "item"):
        v = v.item()
    if isinstance(v, bool):
        return int(v)
    return v


class RTMDatabase:
    """PostgreSQL database manager for RTM Classification."""

    def __init__(self, dsn: str = None):
        self.dsn = dsn or os.environ.get("DATABASE_URL", DEFAULT_DSN)
        self.pool = ConnectionPool(
            self.dsn,
            min_size=4,
            max_size=32,
            max_idle=60,
            kwargs={"row_factory": dict_row},
            open=False,
        )
        self.pool.open()
        self.pool.wait(timeout=30)   # block until Postgres is reachable
        self._init_database()

    def _init_database(self):
        """Create tables and the pgvector extension if absent."""
        with self.pool.connection() as conn, conn.cursor() as cur:
            # pgvector — ready for future similarity / clustering features
            try:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            except Exception:
                pass

            cur.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    sales_filename TEXT,
                    customer_filename TEXT,
                    item_filename TEXT,
                    threshold_a INTEGER DEFAULT 80,
                    threshold_b INTEGER DEFAULT 95,
                    total_outlets INTEGER DEFAULT 0,
                    class_a_count INTEGER DEFAULT 0,
                    class_b_count INTEGER DEFAULT 0,
                    class_c_count INTEGER DEFAULT 0,
                    wholesaler_count INTEGER DEFAULT 0,
                    total_revenue DOUBLE PRECISION DEFAULT 0,
                    date_from TEXT,
                    date_to TEXT,
                    result_path TEXT,
                    completed_at TEXT,
                    error_message TEXT,
                    rule_config TEXT,
                    run_by TEXT,
                    run_by_id INTEGER,
                    rule_version INTEGER,
                    llm_prompt_tokens INTEGER DEFAULT 0,
                    llm_completion_tokens INTEGER DEFAULT 0,
                    llm_cost DOUBLE PRECISION DEFAULT 0
                )
            """)

            cols_ddl = ",\n".join(f'"{name}" {dtype}' for name, dtype in JOB_RESULTS_COLUMNS)
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS job_results (
                    id SERIAL PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    {cols_ddl}
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_job_results_job_id ON job_results (job_id)")

            # Migrations — add columns to already-existing tables
            for col_def in (
                "llm_prompt_tokens INTEGER DEFAULT 0",
                "llm_completion_tokens INTEGER DEFAULT 0",
                "llm_cost DOUBLE PRECISION DEFAULT 0",
                "progress_step INTEGER DEFAULT 0",
                "progress_total INTEGER DEFAULT 10",
                "progress_message TEXT",
                "progress_log TEXT",
                "result_payload TEXT",
            ):
                cur.execute(f"ALTER TABLE jobs ADD COLUMN IF NOT EXISTS {col_def}")
            for col_def in (
                '"Latitude" DOUBLE PRECISION',
                '"Longitude" DOUBLE PRECISION',
                '"Township" TEXT',
                '"CntctPrsn" TEXT',
                '"Address" TEXT',
                '"Phone1" TEXT',
                '"Lifecycle_Stage" TEXT',
                '"RouteCode" TEXT',
                '"RouteName" TEXT',
                '"VAN" TEXT',
                '"SalesGroup" TEXT',
                '"Principal" TEXT',
                '"Route_SalesGroup" TEXT',
                '"Ref" TEXT',
            ):
                cur.execute(f"ALTER TABLE job_results ADD COLUMN IF NOT EXISTS {col_def}")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS job_insights (
                    job_id TEXT PRIMARY KEY,
                    executive_summary TEXT,
                    class_a_recs TEXT,
                    class_b_recs TEXT,
                    class_c_recs TEXT,
                    growth_analysis TEXT,
                    data_quality TEXT
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id SERIAL PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    user_id INTEGER,
                    username TEXT,
                    action TEXT NOT NULL,
                    details TEXT,
                    ip_address TEXT
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS rule_config_history (
                    id SERIAL PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    user_id INTEGER,
                    username TEXT,
                    config_json TEXT NOT NULL,
                    note TEXT
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS job_shares (
                    id SERIAL PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    shared_by TEXT,
                    created_at TEXT,
                    UNIQUE (job_id, user_id)
                )
            """)

    # ── Audit log ──

    def log_action(self, username: str, action: str, details: str = "", user_id: int = 0):
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO audit_log (timestamp, user_id, username, action, details) "
                "VALUES (%s, %s, %s, %s, %s)",
                (datetime.now().isoformat(), user_id, username, action, details),
            )

    def get_audit_log(self, limit: int = 100) -> list:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT %s", (limit,))
            return [dict(r) for r in cur.fetchall()]

    # ── Jobs ──

    def create_job(self, job_id, sales_file, customer_file, item_file,
                   threshold_a=80, threshold_b=95) -> bool:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """INSERT INTO jobs (job_id, created_at, status, sales_filename,
                       customer_filename, item_filename, threshold_a, threshold_b)
                   VALUES (%s, %s, 'processing', %s, %s, %s, %s, %s)""",
                (job_id, datetime.now().isoformat(), sales_file, customer_file,
                 item_file, threshold_a, threshold_b),
            )
        return True

    def save_job_result_payload(self, job_id: str, payload: str) -> None:
        """Persist the full classification response JSON so async-launched jobs
        can be fetched back by frontend polling after completion."""
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute("UPDATE jobs SET result_payload=%s WHERE job_id=%s", (payload, job_id))
            conn.commit()

    def get_job_progress(self, job_id: str) -> dict:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT status, progress_step, progress_total, progress_message, "
                "progress_log, error_message, result_payload IS NOT NULL AS has_payload "
                "FROM jobs WHERE job_id=%s", (job_id,))
            row = cur.fetchone()
            return dict(row) if row else {}

    def get_job_result_payload(self, job_id: str) -> Optional[str]:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT result_payload FROM jobs WHERE job_id=%s", (job_id,))
            row = cur.fetchone()
            return (row.get("result_payload") if row else None)

    def update_job_progress(self, job_id, step=None, total=None, message=None, log_append: str = None) -> None:
        """Persist incremental progress so async polling can read live state."""
        with self.pool.connection() as conn, conn.cursor() as cur:
            sets, params = [], []
            if step is not None:
                sets.append('progress_step=%s'); params.append(int(step))
            if total is not None:
                sets.append('progress_total=%s'); params.append(int(total))
            if message is not None:
                sets.append('progress_message=%s'); params.append(str(message)[:500])
            if log_append:
                # append a line to progress_log (cap at ~256KB to avoid runaway growth)
                sets.append("progress_log=LEFT(COALESCE(progress_log,'') || %s || E'\\n', 262144)")
                params.append(str(log_append))
            if not sets:
                return
            params.append(job_id)
            cur.execute(f"UPDATE jobs SET {', '.join(sets)} WHERE job_id=%s", params)
            conn.commit()

    def update_job_status(self, job_id, status, error_message=None) -> bool:
        with self.pool.connection() as conn, conn.cursor() as cur:
            if status == "completed":
                cur.execute("UPDATE jobs SET status=%s, completed_at=%s WHERE job_id=%s",
                            (status, datetime.now().isoformat(), job_id))
            elif status == "failed":
                cur.execute("UPDATE jobs SET status=%s, error_message=%s WHERE job_id=%s",
                            (status, error_message, job_id))
            else:
                cur.execute("UPDATE jobs SET status=%s WHERE job_id=%s", (status, job_id))
        return True

    def update_job_results(self, job_id, results_df: pd.DataFrame,
                           date_from=None, date_to=None) -> bool:
        """Save all classification result rows + roll up job summary stats."""
        column_mapping = {
            "Cus.Code": "Cus_Code", "Cus.Name": "Cus_Name", "Outlet Channel": "OutletChannel",
            "Non Food_Sales_2Yr": "NonFood_Sales_2Yr", "Non Food_Sales_12M": "NonFood_Sales_12M",
            "Non Food_Sales_6M": "NonFood_Sales_6M", "Non Food_Sales_3M": "NonFood_Sales_3M",
            "Non Food_Contribution_Pct": "NonFood_Contribution_Pct",
        }
        df = results_df.copy().rename(columns=column_mapping)
        df["job_id"] = job_id

        for col in ("FirstPurchaseDate", "LastPurchaseDate"):
            if col in df.columns:
                df[col] = df[col].apply(lambda x: str(x) if pd.notna(x) else None)

        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT column_name FROM information_schema.columns "
                        "WHERE table_name='job_results'")
            db_columns = {r["column_name"] for r in cur.fetchall()}
            available = [c for c in df.columns if c in db_columns]

            colnames = ", ".join(f'"{c}"' for c in available)
            sub = df[available].where(pd.notnull(df[available]), None)
            rows = [tuple(_coerce(v) for v in r) for r in sub.itertuples(index=False, name=None)]
            if rows:
                # Bulk COPY — 10-50x faster than executemany for thousands of rows.
                # ~11k rows × 70 cols: executemany ~25s → COPY ~1s
                with cur.copy(f"COPY job_results ({colnames}) FROM STDIN") as cp:
                    for r in rows:
                        cp.write_row(r)

            # Job summary — cast numpy → native Python
            class_counts = results_df["Classification"].value_counts().to_dict()
            class_a = int(class_counts.get("Class A", 0) + class_counts.get("Class A Local (F4)", 0))
            class_b = int(class_counts.get("Class B", 0))
            class_c = int(class_counts.get("Class C", 0))
            wholesalers = int(results_df["Is_Wholesaler"].sum()) if "Is_Wholesaler" in results_df.columns else 0
            revenue = float(results_df["TotalSales_2Yr"].sum()) if "TotalSales_2Yr" in results_df.columns else 0.0

            cur.execute(
                """UPDATE jobs SET total_outlets=%s, class_a_count=%s, class_b_count=%s,
                       class_c_count=%s, wholesaler_count=%s, total_revenue=%s,
                       date_from=%s, date_to=%s, status='completed', completed_at=%s
                   WHERE job_id=%s""",
                (int(len(results_df)), class_a, class_b, class_c, wholesalers, revenue,
                 date_from, date_to, datetime.now().isoformat(), job_id),
            )
        return True

    def save_job_rule_config(self, job_id: str, config: dict) -> bool:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute("UPDATE jobs SET rule_config=%s WHERE job_id=%s",
                        (json.dumps(config), job_id))
        return True

    def save_job_meta(self, job_id: str, run_by: str, run_by_id: int, rule_version: int) -> bool:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute("UPDATE jobs SET run_by=%s, run_by_id=%s, rule_version=%s WHERE job_id=%s",
                        (run_by, run_by_id, rule_version, job_id))
        return True

    def set_job_result_path(self, job_id: str, path: str) -> bool:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute("UPDATE jobs SET result_path=%s WHERE job_id=%s", (path, job_id))
        return True

    def save_job_usage(self, job_id: str, prompt_tokens: int, completion_tokens: int, cost: float) -> bool:
        """Store the LLM token usage + real cost for a job."""
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE jobs SET llm_prompt_tokens=%s, llm_completion_tokens=%s, llm_cost=%s WHERE job_id=%s",
                (int(prompt_tokens), int(completion_tokens), float(cost), job_id),
            )
        return True

    def get_job(self, job_id: str) -> Optional[Dict]:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM jobs WHERE job_id=%s", (job_id,))
            row = cur.fetchone()
        return dict(row) if row else None

    def get_all_jobs(self, limit: int = 50) -> List[Dict]:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT %s", (limit,))
            return [dict(r) for r in cur.fetchall()]

    def get_job_results(self, job_id: str) -> pd.DataFrame:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM job_results WHERE job_id=%s", (job_id,))
            rows = cur.fetchall()
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    def delete_job(self, job_id: str) -> bool:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM job_insights WHERE job_id=%s", (job_id,))
            cur.execute("DELETE FROM job_results WHERE job_id=%s", (job_id,))
            cur.execute("DELETE FROM jobs WHERE job_id=%s", (job_id,))
        return True

    # ── Rule config history ──

    def add_rule_config_version(self, config: dict, user_id: int, username: str, note: str = "") -> int:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO rule_config_history (timestamp, user_id, username, config_json, note) "
                "VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (datetime.now().isoformat(), user_id, username, json.dumps(config), note),
            )
            return cur.fetchone()["id"]

    def get_rule_config_history(self, limit: int = 100) -> list:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM rule_config_history ORDER BY id DESC LIMIT %s", (limit,))
            return [dict(r) for r in cur.fetchall()]

    def get_rule_config_version(self, version_id: int) -> Optional[Dict]:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM rule_config_history WHERE id=%s", (version_id,))
            row = cur.fetchone()
        return dict(row) if row else None

    def latest_rule_config_version(self) -> Optional[Dict]:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM rule_config_history ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
        return dict(row) if row else None

    # ── Job insights ──

    def save_job_insights(self, job_id: str, insights: dict, data_quality: list = None):
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """INSERT INTO job_insights (job_id, executive_summary, class_a_recs,
                       class_b_recs, class_c_recs, growth_analysis, data_quality)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (job_id) DO UPDATE SET
                       executive_summary=EXCLUDED.executive_summary,
                       class_a_recs=EXCLUDED.class_a_recs,
                       class_b_recs=EXCLUDED.class_b_recs,
                       class_c_recs=EXCLUDED.class_c_recs,
                       growth_analysis=EXCLUDED.growth_analysis,
                       data_quality=EXCLUDED.data_quality""",
                (job_id,
                 insights.get("executive_summary", ""),
                 insights.get("class_a_recs", ""),
                 insights.get("class_b_recs", ""),
                 insights.get("class_c_recs", ""),
                 insights.get("growth_analysis", ""),
                 json.dumps(data_quality or [])),
            )

    def get_job_insights(self, job_id: str) -> dict:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM job_insights WHERE job_id=%s", (job_id,))
            row = cur.fetchone()
        if row:
            return {
                "executive_summary": row["executive_summary"] or "",
                "class_a_recs": row["class_a_recs"] or "",
                "class_b_recs": row["class_b_recs"] or "",
                "class_c_recs": row["class_c_recs"] or "",
                "growth_analysis": row["growth_analysis"] or "",
                "data_quality": json.loads(row["data_quality"] or "[]"),
            }
        return {}


    # ── Job sharing (one-to-one) ──

    def set_job_shares(self, job_id: str, user_ids: list, shared_by: str) -> bool:
        """Replace a job's share list with the given set of user ids."""
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM job_shares WHERE job_id=%s", (job_id,))
            for uid in set(user_ids):
                cur.execute(
                    "INSERT INTO job_shares (job_id, user_id, shared_by, created_at) "
                    "VALUES (%s, %s, %s, %s)",
                    (job_id, int(uid), shared_by, datetime.now().isoformat()),
                )
        return True

    def get_job_share_user_ids(self, job_id: str) -> list:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT user_id FROM job_shares WHERE job_id=%s", (job_id,))
            return [r["user_id"] for r in cur.fetchall()]

    def get_shared_job_ids(self, user_id: int) -> list:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT job_id FROM job_shares WHERE user_id=%s", (user_id,))
            return [r["job_id"] for r in cur.fetchall()]


# Singleton
_db_instance = None


def get_database() -> RTMDatabase:
    global _db_instance
    if _db_instance is None:
        _db_instance = RTMDatabase()
    return _db_instance
