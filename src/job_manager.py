#!/usr/bin/env python3
"""
Job Manager - Job ID Generation and Job Tracking
"""

import os
from datetime import datetime
from typing import Optional, Dict
import pandas as pd
import io

from src.database import get_database


class JobManager:
    """Manages job creation, tracking, and execution"""

    def __init__(self):
        self.db = get_database()
        self.current_job_id = None
        self.outputs_dir = self._get_outputs_dir()

    def _get_outputs_dir(self) -> str:
        """Get outputs directory path"""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        outputs_dir = os.path.join(base_dir, "outputs")
        if not os.path.exists(outputs_dir):
            os.makedirs(outputs_dir)
        return outputs_dir

    def generate_job_id(self) -> str:
        """
        Generate unique job ID
        Format: RTM-YYYYMMDD-XXXX
        """
        today = datetime.now().strftime("%Y%m%d")

        # Get all jobs from today
        all_jobs = self.db.get_all_jobs(limit=100)
        today_jobs = [j for j in all_jobs if j["job_id"].startswith(f"RTM-{today}")]

        if today_jobs:
            # Get the last sequence number
            sequences = [int(j["job_id"].split("-")[-1]) for j in today_jobs]
            next_seq = max(sequences) + 1
        else:
            next_seq = 1

        job_id = f"RTM-{today}-{next_seq:04d}"
        return job_id

    def start_job(
        self,
        sales_filename: str,
        customer_filename: str = "",
        item_filename: str = "",
        threshold_a: int = 80,
        threshold_b: int = 95,
    ) -> str:
        """
        Start a new job
        Returns job_id
        """
        job_id = self.generate_job_id()
        self.db.create_job(
            job_id,
            sales_filename,
            customer_filename,
            item_filename,
            threshold_a,
            threshold_b,
        )
        self.current_job_id = job_id
        return job_id

    def create_excel_report(self, results_df: pd.DataFrame) -> bytes:
        """Create multi-sheet Excel report with per-branch breakdown"""
        buf = io.BytesIO()

        with pd.ExcelWriter(buf, engine="openpyxl") as w:

            # ── Sheet 1: All Results ──
            results_df.to_excel(w, sheet_name="All Results", index=False)

            # ── Sheet 2: Overall Summary ──
            summary = (
                results_df.groupby("Classification")
                .agg({"Cus.Code": "count", "TotalSales_2Yr": ["sum", "mean"]})
                .round(2)
            )
            summary.columns = ["Count", "TotalSales", "AvgSales"]
            summary["SalesPct"] = (
                summary["TotalSales"] / summary["TotalSales"].sum() * 100
            ).round(2)
            summary.reset_index().to_excel(w, sheet_name="Overall Summary", index=False)

            # ── Sheet 3: Branch Summary (matrix: Branch x Class) ──
            if "BranchName" in results_df.columns:
                branch_class = (
                    results_df.groupby(["BranchName", "Classification"])
                    .agg({"Cus.Code": "count", "TotalSales_2Yr": "sum"})
                    .round(0)
                )
                branch_class.columns = ["Outlets", "Revenue"]
                branch_class = branch_class.reset_index()

                # Add branch-level totals and percentages
                branch_totals = results_df.groupby("BranchName").agg(
                    Total_Outlets=("Cus.Code", "count"),
                    Total_Revenue=("TotalSales_2Yr", "sum"),
                ).reset_index()

                # Pivot for a clean matrix view
                pivot_counts = branch_class.pivot_table(
                    index="BranchName", columns="Classification",
                    values="Outlets", fill_value=0, aggfunc="sum",
                )
                pivot_revenue = branch_class.pivot_table(
                    index="BranchName", columns="Classification",
                    values="Revenue", fill_value=0, aggfunc="sum",
                )

                # Build summary table
                branch_summary = branch_totals.copy()
                for cls in ["Class A", "Class B", "Class C", "Class A Local (F4)"]:
                    if cls in pivot_counts.columns:
                        branch_summary[f"{cls}_Count"] = branch_summary["BranchName"].map(
                            pivot_counts[cls]
                        ).fillna(0).astype(int)
                        branch_summary[f"{cls}_Revenue"] = branch_summary["BranchName"].map(
                            pivot_revenue[cls]
                        ).fillna(0).astype(int)
                        branch_summary[f"{cls}_Pct"] = (
                            branch_summary[f"{cls}_Revenue"] / branch_summary["Total_Revenue"] * 100
                        ).round(1)

                branch_summary = branch_summary.sort_values("Total_Revenue", ascending=False)
                branch_summary.to_excel(w, sheet_name="Branch Summary", index=False)

            # ── Sheets 4-N: One sheet per branch ──
            if "BranchName" in results_df.columns:
                branches = sorted(results_df["BranchName"].unique())
                for branch in branches:
                    branch_df = results_df[results_df["BranchName"] == branch].copy()
                    branch_df = branch_df.sort_values("TotalSales_2Yr", ascending=False)

                    # Truncate sheet name to 31 chars (Excel limit)
                    sheet_name = branch[:31]
                    branch_df.to_excel(w, sheet_name=sheet_name, index=False)

            # ── Top 50 (across all branches) ──
            top_cols = ["BranchName", "Cus.Code", "Cus.Name", "Classification", "TotalSales_2Yr"]
            available_top = [c for c in top_cols if c in results_df.columns]
            if "TotalSales_12M" in results_df.columns:
                available_top.append("TotalSales_12M")
            top_customers = results_df.nlargest(50, "TotalSales_2Yr")[available_top]
            top_customers.to_excel(w, sheet_name="Top 50", index=False)

            # ── AI Action Plan ──
            ai_cols = [
                "BranchName", "Cus.Code", "Cus.Name", "Classification",
                "TotalSales_2Yr", "AI_Growth_Signal", "AI_Risk_Level",
                "AI_Visit_Priority", "AI_Action", "AI_Insight",
            ]
            available_ai = [c for c in ai_cols if c in results_df.columns]
            if len(available_ai) > 4:
                results_df[available_ai].to_excel(w, sheet_name="AI Action Plan", index=False)

            # ── AI Insights (text) ──
            # This will be populated by Home.py if insights are available

        return buf.getvalue()

    def complete_job(
        self,
        results_df: pd.DataFrame,
        date_from: str = None,
        date_to: str = None,
        result_excel: bytes = None,
    ) -> bool:
        """
        Mark job as completed with results
        """
        if not self.current_job_id:
            raise ValueError("No active job to complete")

        # Save results to database
        self.db.update_job_results(self.current_job_id, results_df, date_from, date_to)

        # Create Excel report if not provided
        if result_excel is None:
            result_excel = self.create_excel_report(results_df)

        # Save Excel file
        excel_path = os.path.join(self.outputs_dir, f"{self.current_job_id}.xlsx")
        with open(excel_path, "wb") as f:
            f.write(result_excel)

            # Update job with result path
            conn = self.db._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE jobs SET result_path = ? WHERE job_id = ?
            """,
                (excel_path, self.current_job_id),
            )
            conn.commit()
            conn.close()

        return True

    def fail_job(self, error_message: str) -> bool:
        """Mark job as failed"""
        if not self.current_job_id:
            return False

        self.db.update_job_status(self.current_job_id, "failed", error_message)
        return True

    def get_current_job_id(self) -> Optional[str]:
        """Get current job ID"""
        return self.current_job_id

    def get_job(self, job_id: str) -> Optional[Dict]:
        """Get job details"""
        return self.db.get_job(job_id)

    def get_all_jobs(self, limit: int = 50) -> list:
        """Get all jobs"""
        return self.db.get_all_jobs(limit)

    def get_job_results(self, job_id: str) -> pd.DataFrame:
        """Get job results"""
        return self.db.get_job_results(job_id)

    def get_excel_path(self, job_id: str) -> Optional[str]:
        """Get Excel file path for a job"""
        job = self.db.get_job(job_id)
        if job and job.get("result_path"):
            return job["result_path"]
        return None

    def read_excel_file(self, job_id: str) -> Optional[bytes]:
        """Read Excel file for a job"""
        excel_path = self.get_excel_path(job_id)
        if excel_path and os.path.exists(excel_path):
            with open(excel_path, "rb") as f:
                return f.read()
        return None


# Singleton instance
_job_manager = None


def get_job_manager() -> JobManager:
    """Get job manager singleton"""
    global _job_manager
    if _job_manager is None:
        _job_manager = JobManager()
    return _job_manager
