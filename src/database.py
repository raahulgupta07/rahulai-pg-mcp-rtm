#!/usr/bin/env python3
"""
SQLite Database Operations for RTM Classification
Stores job metadata and all classification results
"""

import sqlite3
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
import pandas as pd


class RTMDatabase:
    """SQLite database manager for RTM Classification"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_path = os.path.join(base_dir, "data", "rtm.db")

        self.db_path = db_path
        self._ensure_data_folder()
        self._init_database()

    def _ensure_data_folder(self):
        """Ensure data folder exists"""
        data_dir = os.path.dirname(self.db_path)
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)

    def _get_connection(self):
        """Get SQLite connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_database(self):
        """Initialize database tables"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Jobs table - metadata
        cursor.execute("""
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
                total_revenue REAL DEFAULT 0,
                date_from TEXT,
                date_to TEXT,
                result_path TEXT,
                completed_at TEXT,
                error_message TEXT
            )
        """)

        # Job results table - all outlet data
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS job_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                Cus_Code TEXT,
                Cus_Name TEXT,
                OutletChannel TEXT,
                TotalSales_2Yr REAL DEFAULT 0,
                TotalSales_12M REAL DEFAULT 0,
                TotalSales_6M REAL DEFAULT 0,
                TotalSales_3M REAL DEFAULT 0,
                TotalPcs REAL DEFAULT 0,
                TransactionCount INTEGER DEFAULT 0,
                Nutrition_Sales_2Yr REAL DEFAULT 0,
                Nutrition_Sales_12M REAL DEFAULT 0,
                Nutrition_Sales_6M REAL DEFAULT 0,
                Nutrition_Sales_3M REAL DEFAULT 0,
                Food_Sales_2Yr REAL DEFAULT 0,
                Food_Sales_12M REAL DEFAULT 0,
                Food_Sales_6M REAL DEFAULT 0,
                Food_Sales_3M REAL DEFAULT 0,
                NonFood_Sales_2Yr REAL DEFAULT 0,
                NonFood_Sales_12M REAL DEFAULT 0,
                NonFood_Sales_6M REAL DEFAULT 0,
                NonFood_Sales_3M REAL DEFAULT 0,
                Local_Sales_2Yr REAL DEFAULT 0,
                Import_Sales_2Yr REAL DEFAULT 0,
                AvgSales_All_2Yr REAL DEFAULT 0,
                AvgSales_Nutrition_2Yr REAL DEFAULT 0,
                AvgSales_Food_2Yr REAL DEFAULT 0,
                AvgSales_NonFood_2Yr REAL DEFAULT 0,
                Overall_Contribution_Pct REAL DEFAULT 0,
                Nutrition_Contribution_Pct REAL DEFAULT 0,
                Food_Contribution_Pct REAL DEFAULT 0,
                NonFood_Contribution_Pct REAL DEFAULT 0,
                Local_Contribution_Pct REAL DEFAULT 0,
                Import_Contribution_Pct REAL DEFAULT 0,
                Is_Wholesaler INTEGER DEFAULT 0,
                Base_Classification TEXT,
                Classification TEXT,
                CumulativeSales REAL DEFAULT 0,
                CumulativePct REAL DEFAULT 0,
                PurchaseDays_2Yr INTEGER DEFAULT 0,
                PurchaseDays_12M INTEGER DEFAULT 0,
                PurchaseDays_6M INTEGER DEFAULT 0,
                Frequency_2Yr REAL DEFAULT 0,
                FirstPurchaseDate TEXT,
                LastPurchaseDate TEXT,
                Growth_6M_vs_12M REAL DEFAULT 0,
                Growth_3M_vs_6M REAL DEFAULT 0,
                BranchName TEXT,
                FOREIGN KEY (job_id) REFERENCES jobs (job_id)
            )
        """)

        # Add BranchName column if missing (migration)
        try:
            cursor.execute("ALTER TABLE job_results ADD COLUMN BranchName TEXT")
        except:
            pass  # column already exists

        # Job insights table - AI-generated insights per job
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS job_insights (
                job_id TEXT PRIMARY KEY,
                executive_summary TEXT,
                class_a_recs TEXT,
                class_b_recs TEXT,
                class_c_recs TEXT,
                growth_analysis TEXT,
                data_quality TEXT,
                FOREIGN KEY (job_id) REFERENCES jobs (job_id)
            )
        """)

        conn.commit()
        conn.close()

    def create_job(
        self,
        job_id: str,
        sales_file: str,
        customer_file: str,
        item_file: str,
        threshold_a: int = 80,
        threshold_b: int = 95,
    ) -> bool:
        """Create a new job entry"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO jobs (job_id, created_at, status, sales_filename, 
                           customer_filename, item_filename, threshold_a, threshold_b)
            VALUES (?, ?, 'processing', ?, ?, ?, ?, ?)
        """,
            (
                job_id,
                datetime.now().isoformat(),
                sales_file,
                customer_file,
                item_file,
                threshold_a,
                threshold_b,
            ),
        )

        conn.commit()
        conn.close()
        return True

    def update_job_status(
        self, job_id: str, status: str, error_message: str = None
    ) -> bool:
        """Update job status"""
        conn = self._get_connection()
        cursor = conn.cursor()

        if status == "completed":
            cursor.execute(
                """
                UPDATE jobs SET status = ?, completed_at = ? WHERE job_id = ?
            """,
                (status, datetime.now().isoformat(), job_id),
            )
        elif status == "failed":
            cursor.execute(
                """
                UPDATE jobs SET status = ?, error_message = ? WHERE job_id = ?
            """,
                (status, error_message, job_id),
            )
        else:
            cursor.execute(
                """
                UPDATE jobs SET status = ? WHERE job_id = ?
            """,
                (status, job_id),
            )

        conn.commit()
        conn.close()
        return True

    def update_job_results(
        self,
        job_id: str,
        results_df: pd.DataFrame,
        date_from: str = None,
        date_to: str = None,
    ) -> bool:
        """Save job results to database"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Map dataframe columns to database columns
        column_mapping = {
            "Cus.Code": "Cus_Code",
            "Cus.Name": "Cus_Name",
            "Outlet Channel": "OutletChannel",
            "TotalSales_2Yr": "TotalSales_2Yr",
            "TotalSales_12M": "TotalSales_12M",
            "TotalSales_6M": "TotalSales_6M",
            "TotalSales_3M": "TotalSales_3M",
            "TotalPcs": "TotalPcs",
            "TransactionCount": "TransactionCount",
            "Nutrition_Sales_2Yr": "Nutrition_Sales_2Yr",
            "Nutrition_Sales_12M": "Nutrition_Sales_12M",
            "Nutrition_Sales_6M": "Nutrition_Sales_6M",
            "Nutrition_Sales_3M": "Nutrition_Sales_3M",
            "Food_Sales_2Yr": "Food_Sales_2Yr",
            "Food_Sales_12M": "Food_Sales_12M",
            "Food_Sales_6M": "Food_Sales_6M",
            "Food_Sales_3M": "Food_Sales_3M",
            "Non Food_Sales_2Yr": "NonFood_Sales_2Yr",
            "Non Food_Sales_12M": "NonFood_Sales_12M",
            "Non Food_Sales_6M": "NonFood_Sales_6M",
            "Non Food_Sales_3M": "NonFood_Sales_3M",
            "Local_Sales_2Yr": "Local_Sales_2Yr",
            "Import_Sales_2Yr": "Import_Sales_2Yr",
            "AvgSales_All_2Yr": "AvgSales_All_2Yr",
            "AvgSales_Nutrition_2Yr": "AvgSales_Nutrition_2Yr",
            "AvgSales_Food_2Yr": "AvgSales_Food_2Yr",
            "AvgSales_NonFood_2Yr": "AvgSales_NonFood_2Yr",
            "Overall_Contribution_Pct": "Overall_Contribution_Pct",
            "Nutrition_Contribution_Pct": "Nutrition_Contribution_Pct",
            "Food_Contribution_Pct": "Food_Contribution_Pct",
            "Non Food_Contribution_Pct": "NonFood_Contribution_Pct",
            "Local_Contribution_Pct": "Local_Contribution_Pct",
            "Import_Contribution_Pct": "Import_Contribution_Pct",
            "Is_Wholesaler": "Is_Wholesaler",
            "Base_Classification": "Base_Classification",
            "Classification": "Classification",
            "CumulativeSales": "CumulativeSales",
            "CumulativePct": "CumulativePct",
            "PurchaseDays_2Yr": "PurchaseDays_2Yr",
            "PurchaseDays_12M": "PurchaseDays_12M",
            "PurchaseDays_6M": "PurchaseDays_6M",
            "Frequency_2Yr": "Frequency_2Yr",
            "FirstPurchaseDate": "FirstPurchaseDate",
            "LastPurchaseDate": "LastPurchaseDate",
            "Growth_6M_vs_12M": "Growth_6M_vs_12M",
            "Growth_3M_vs_6M": "Growth_3M_vs_6M",
            "BranchName": "BranchName",
        }

        # Rename columns
        df = results_df.copy()
        df = df.rename(columns=column_mapping)

        # Add job_id
        df["job_id"] = job_id

        # Select only columns that exist in the table
        cursor.execute("PRAGMA table_info(job_results)")
        db_columns = [row[1] for row in cursor.fetchall()]

        available_cols = [c for c in df.columns if c in db_columns]
        df = df[available_cols].copy()

        # Convert datetime/Timestamp columns to string
        date_cols = ["FirstPurchaseDate", "LastPurchaseDate"]
        for col in date_cols:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: str(x) if pd.notna(x) else None)

        # Insert results
        for _, row in df.iterrows():
            placeholders = ", ".join(["?"] * len(available_cols))
            columns = ", ".join(available_cols)
            sql = f"INSERT INTO job_results ({columns}) VALUES ({placeholders})"
            cursor.execute(sql, tuple(row[available_cols].fillna(0)))

        # Update job with summary stats
        class_counts = results_df["Classification"].value_counts().to_dict()
        class_a = class_counts.get("Class A", 0) + class_counts.get(
            "Class A Local (F4)", 0
        )
        class_b = class_counts.get("Class B", 0)
        class_c = class_counts.get("Class C", 0)
        wholesalers = (
            results_df["Is_Wholesaler"].sum()
            if "Is_Wholesaler" in results_df.columns
            else 0
        )

        cursor.execute(
            """
            UPDATE jobs SET 
                total_outlets = ?,
                class_a_count = ?,
                class_b_count = ?,
                class_c_count = ?,
                wholesaler_count = ?,
                total_revenue = ?,
                date_from = ?,
                date_to = ?,
                status = 'completed',
                completed_at = ?
            WHERE job_id = ?
        """,
            (
                len(results_df),
                class_a,
                class_b,
                class_c,
                wholesalers,
                results_df["TotalSales_2Yr"].sum()
                if "TotalSales_2Yr" in results_df.columns
                else 0,
                date_from,
                date_to,
                datetime.now().isoformat(),
                job_id,
            ),
        )

        conn.commit()
        conn.close()
        return True

    def get_job(self, job_id: str) -> Optional[Dict]:
        """Get job by ID"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return dict(row)
        return None

    def get_all_jobs(self, limit: int = 50) -> List[Dict]:
        """Get all jobs, most recent first"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?
        """,
            (limit,),
        )

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_job_results(self, job_id: str) -> pd.DataFrame:
        """Get all results for a job"""
        conn = self._get_connection()
        df = pd.read_sql_query(
            "SELECT * FROM job_results WHERE job_id = ?", conn, params=(job_id,)
        )
        conn.close()
        return df

    def save_job_insights(self, job_id: str, insights: dict, data_quality: list = None):
        """Save AI insights for a job"""
        import json
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO job_insights (job_id, executive_summary, class_a_recs, class_b_recs, class_c_recs, growth_analysis, data_quality)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            job_id,
            insights.get("executive_summary", ""),
            insights.get("class_a_recs", ""),
            insights.get("class_b_recs", ""),
            insights.get("class_c_recs", ""),
            insights.get("growth_analysis", ""),
            json.dumps(data_quality or []),
        ))
        conn.commit()
        conn.close()

    def get_job_insights(self, job_id: str) -> dict:
        """Get AI insights for a job"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM job_insights WHERE job_id = ?", (job_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            import json
            return {
                "executive_summary": row["executive_summary"] or "",
                "class_a_recs": row["class_a_recs"] or "",
                "class_b_recs": row["class_b_recs"] or "",
                "class_c_recs": row["class_c_recs"] or "",
                "growth_analysis": row["growth_analysis"] or "",
                "data_quality": json.loads(row["data_quality"] or "[]"),
            }
        return {}

    def delete_job(self, job_id: str) -> bool:
        """Delete a job and its results"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM job_insights WHERE job_id = ?", (job_id,))
        cursor.execute("DELETE FROM job_results WHERE job_id = ?", (job_id,))
        cursor.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))

        conn.commit()
        conn.close()
        return True


# Singleton instance
_db_instance = None


def get_database() -> RTMDatabase:
    """Get database singleton"""
    global _db_instance
    if _db_instance is None:
        _db_instance = RTMDatabase()
    return _db_instance
