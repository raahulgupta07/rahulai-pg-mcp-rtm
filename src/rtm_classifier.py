#!/usr/bin/env python3
"""
RTM Outlet Classification - Complete Classifier
Single-file workflow, partitioned by BranchName
"""

import pandas as pd
import numpy as np
from datetime import datetime
import warnings

warnings.filterwarnings("ignore")


class RTMClassifier:
    """
    RTM Outlet Classification Engine
    Classifies outlets using Pareto 80/15/5 partitioned by BranchName.
    Each branch is its own universe — denominator is the branch total.
    """

    def __init__(self, sales_df):
        """
        Initialize with pre-merged sales data containing all required columns.
        """
        self.sales = sales_df.copy()
        self.results = None
        self.max_date = None
        self.min_date = None

    def validate_data(self):
        """Validate required columns exist"""

        required_cols = [
            "Cus.Code",
            "Cus.Name",
            "TotalAmount",
            "TotalPcs",
            "BranchName",
            "Item Class",
            "NumInBuy",
        ]

        missing_required = [
            col for col in required_cols if col not in self.sales.columns
        ]
        if missing_required:
            raise ValueError(f"MISSING REQUIRED COLUMNS: {missing_required}")

        # Check optional columns
        optional_cols = {
            "DocDate": "Transaction date",
            "InvoiceNo": "Invoice number",
            "BrandName": "Brand name",
            "Item Type": "Item type (Local/Import)",
            "Outlet Channel": "Outlet channel",
            "Channel": "Channel name",
        }

        missing_optional = {}
        for col, desc in optional_cols.items():
            if col not in self.sales.columns:
                missing_optional[col] = desc

        if missing_optional:
            print(f"  Optional columns missing: {list(missing_optional.keys())}")

        self.has_docdate = "DocDate" in self.sales.columns
        self.has_invoice = "InvoiceNo" in self.sales.columns
        self.has_brand = "BrandName" in self.sales.columns
        self.has_item_type = "Item Type" in self.sales.columns

        # Handle missing optional columns
        if not self.has_docdate:
            self.sales["DocDate"] = pd.Timestamp.now()
        if not self.has_invoice:
            self.sales["InvoiceNo"] = range(len(self.sales))
        if not self.has_brand:
            self.sales["BrandName"] = "Unknown"
        if not self.has_item_type:
            self.sales["Item Type"] = "Unknown"

        # Use Channel column for OutletChannel if Outlet Channel is missing or all zeros
        if "Outlet Channel" not in self.sales.columns:
            if "Channel" in self.sales.columns:
                self.sales["Outlet Channel"] = self.sales["Channel"]
            else:
                self.sales["Outlet Channel"] = "Unknown"
        else:
            # If Outlet Channel exists but is all 0 or empty, use Channel instead
            oc_values = self.sales["Outlet Channel"].astype(str).unique()
            if set(oc_values) <= {"0", "0.0", "", "nan"}:
                if "Channel" in self.sales.columns:
                    self.sales["Outlet Channel"] = self.sales["Channel"]

        # Parse dates
        if (
            self.sales["DocDate"].dtype == "object"
            or self.sales["DocDate"].dtype == "str"
        ):
            self.sales["DocDate"] = pd.to_datetime(
                self.sales["DocDate"], format="%d/%m/%Y", errors="coerce"
            )
        else:
            self.sales["DocDate"] = pd.to_datetime(
                self.sales["DocDate"], errors="coerce"
            )

        null_dates = self.sales["DocDate"].isnull().sum()
        if null_dates > 0:
            print(f"   Warning: {null_dates} invalid dates, using current date")
            self.sales["DocDate"] = self.sales["DocDate"].fillna(pd.Timestamp.now())

        self.max_date = self.sales["DocDate"].max()
        self.min_date = self.sales["DocDate"].min()
        self.months_count = (self.max_date - self.min_date).days / 30

        if self.months_count < 1:
            self.months_count = 1

        branches = self.sales["BranchName"].nunique()
        print(
            f"Data validated: {self.min_date.date()} to {self.max_date.date()} "
            f"({self.months_count:.1f} months, {branches} branches)"
        )
        return True

    def aggregate_by_customer(self):
        """Aggregate transaction data by (BranchName, Cus.Code)"""

        agg_dict = {
            "Cus.Name": "first",
            "TotalAmount": "sum",
            "TotalPcs": "sum",
            "InvoiceNo": "nunique",
            "DocDate": ["min", "max"],
            "Outlet Channel": "first",
        }

        # Add extra columns if present
        extra_cols = ["Channel", "GroupName"]
        for col in extra_cols:
            if col in self.sales.columns:
                agg_dict[col] = "first"

        customer_agg = self.sales.groupby(["BranchName", "Cus.Code"]).agg(agg_dict)

        # Flatten multi-level column names
        flat_cols = []
        for col in customer_agg.columns:
            if isinstance(col, tuple):
                if col[1] in ("", "first", "sum", "nunique"):
                    flat_cols.append(col[0])
                else:
                    flat_cols.append(f"{col[0]}_{col[1]}")
            else:
                flat_cols.append(col)
        customer_agg.columns = flat_cols

        # Rename DocDate agg columns
        rename_map = {}
        if "DocDate_min" in customer_agg.columns:
            rename_map["DocDate_min"] = "FirstPurchaseDate"
        if "DocDate_max" in customer_agg.columns:
            rename_map["DocDate_max"] = "LastPurchaseDate"
        if "TotalAmount" in customer_agg.columns:
            rename_map["TotalAmount"] = "TotalSales"
        if "InvoiceNo" in customer_agg.columns:
            rename_map["InvoiceNo"] = "TransactionCount"
        if "Outlet Channel" in customer_agg.columns:
            rename_map["Outlet Channel"] = "OutletChannel"
        customer_agg = customer_agg.rename(columns=rename_map)

        customer_agg = customer_agg.reset_index()

        self._add_period_sales(customer_agg)

        print(f"Aggregated {len(customer_agg)} customer-branch combinations across {customer_agg['BranchName'].nunique()} branches")
        return customer_agg

    def _add_period_sales(self, df):
        """Calculate sales for different time periods"""

        periods = {"2Yr": None, "12M": 12, "6M": 6, "3M": 3}

        for period, months in periods.items():
            if months:
                cutoff = self.max_date - pd.DateOffset(months=months)
                period_data = self.sales[self.sales["DocDate"] >= cutoff]
            else:
                period_data = self.sales

            # Group by BranchName + Cus.Code to match aggregation level
            period_sales = period_data.groupby(["BranchName", "Cus.Code"])["TotalAmount"].sum()
            df[f"TotalSales_{period}"] = df.set_index(["BranchName", "Cus.Code"]).index.map(
                lambda x: period_sales.get(x, 0)
            )
            df[f"TotalSales_{period}"] = df[f"TotalSales_{period}"].fillna(0)

            for item_class in ["Nutrition", "Food", "Non Food"]:
                class_data = period_data[period_data["Item Class"] == item_class]
                class_sales = class_data.groupby(["BranchName", "Cus.Code"])["TotalAmount"].sum()
                df[f"{item_class}_Sales_{period}"] = df.set_index(["BranchName", "Cus.Code"]).index.map(
                    lambda x, cs=class_sales: cs.get(x, 0)
                )
                df[f"{item_class}_Sales_{period}"] = df[f"{item_class}_Sales_{period}"].fillna(0)

            if self.has_item_type:
                for item_type in ["Local", "Import"]:
                    type_data = period_data[period_data["Item Type"] == item_type]
                    type_sales = type_data.groupby(["BranchName", "Cus.Code"])["TotalAmount"].sum()
                    df[f"{item_type}_Sales_{period}"] = df.set_index(["BranchName", "Cus.Code"]).index.map(
                        lambda x, ts=type_sales: ts.get(x, 0)
                    )
                    df[f"{item_type}_Sales_{period}"] = df[f"{item_type}_Sales_{period}"].fillna(0)

    def calculate_averages(self, df):
        """Calculate average sales for each period"""

        for period, months in [
            ("2Yr", self.months_count),
            ("12M", 12),
            ("6M", 6),
            ("3M", 3),
        ]:
            for category in ["All", "Nutrition", "Food", "Non Food", "Local", "Import"]:
                col = f"{'Total' if category == 'All' else category}_Sales_{period}"
                if col in df.columns:
                    df[f"AvgSales_{category}_{period}"] = df[col] / months

        print(f"Calculated period averages")
        return df

    def calculate_contributions(self, df):
        """Calculate contribution percentages — per BranchName"""

        # Per-branch contribution: each outlet's % of its own branch total
        branch_totals = df.groupby("BranchName")["TotalSales_2Yr"].transform("sum")
        df["Overall_Contribution_Pct"] = (df["TotalSales_2Yr"] / branch_totals) * 100

        for item_class in ["Nutrition", "Food", "Non Food"]:
            col = f"{item_class}_Sales_2Yr"
            if col in df.columns:
                branch_class_total = df.groupby("BranchName")[col].transform("sum")
                df[f"{item_class}_Contribution_Pct"] = np.where(
                    branch_class_total > 0,
                    (df[col] / branch_class_total) * 100,
                    0,
                )

        for item_type in ["Local", "Import"]:
            col = f"{item_type}_Sales_2Yr"
            if col in df.columns:
                branch_type_total = df.groupby("BranchName")[col].transform("sum")
                df[f"{item_type}_Contribution_Pct"] = np.where(
                    branch_type_total > 0,
                    (df[col] / branch_type_total) * 100,
                    0,
                )

        print(f"Calculated contribution percentages (per branch)")
        return df

    def identify_wholesalers(self, df):
        """Identify wholesalers: >=3 cartons per brand per month of local products"""

        if not self.has_item_type:
            df["Is_Wholesaler"] = False
            print(f"Identified 0 wholesalers (no Item Type column)")
            return df

        local_df = self.sales[self.sales["Item Type"] == "Local"].copy()

        if local_df.empty:
            df["Is_Wholesaler"] = False
            print(f"Identified 0 wholesalers (no Local products)")
            return df

        local_df["Cartons"] = local_df["TotalPcs"] / local_df["NumInBuy"]
        local_df["BrandName"] = local_df["BrandName"].fillna("Unknown")
        local_df["YearMonth"] = local_df["DocDate"].dt.to_period("M")

        brand_monthly = (
            local_df.groupby(["BranchName", "Cus.Code", "BrandName", "YearMonth"])["Cartons"]
            .sum()
            .reset_index()
        )
        high_volume = brand_monthly[brand_monthly["Cartons"] >= 3]
        wholesaler_keys = set(
            zip(high_volume["BranchName"], high_volume["Cus.Code"])
        )

        df["Is_Wholesaler"] = df.apply(
            lambda row: (row["BranchName"], row["Cus.Code"]) in wholesaler_keys,
            axis=1,
        )

        print(f"Identified {df['Is_Wholesaler'].sum()} wholesalers")
        return df

    def classify_outlets(self, df):
        """Apply 80/15/5 Pareto classification — per BranchName"""

        all_branch_results = []

        for branch, branch_df in df.groupby("BranchName"):
            bdf = branch_df.sort_values("TotalSales_2Yr", ascending=False).reset_index(drop=True)

            branch_total = bdf["TotalSales_2Yr"].sum()
            if branch_total > 0:
                bdf["CumulativeSales"] = bdf["TotalSales_2Yr"].cumsum()
                bdf["CumulativePct"] = (bdf["CumulativeSales"] / branch_total) * 100
            else:
                bdf["CumulativeSales"] = 0
                bdf["CumulativePct"] = 0

            def classify_pareto(cum_pct):
                if cum_pct <= 80:
                    return "Class A"
                elif cum_pct <= 95:
                    return "Class B"
                else:
                    return "Class C"

            bdf["Base_Classification"] = bdf["CumulativePct"].apply(classify_pareto)

            def apply_special_rules(row):
                if row.get("OutletChannel") == "Wholesales" or row.get("Is_Wholesaler", False):
                    return "Class A Local (F4)"
                for item_class in ["Nutrition", "Food", "Non Food"]:
                    if row.get(f"{item_class}_Contribution_Pct", 0) >= 80:
                        return f"Class A {item_class}"
                return row["Base_Classification"]

            bdf["Classification"] = bdf.apply(apply_special_rules, axis=1)

            all_branch_results.append(bdf)

        result = pd.concat(all_branch_results, ignore_index=True)
        counts = result["Classification"].value_counts()
        print(f"Classification complete across {df['BranchName'].nunique()} branches")
        for cls, cnt in counts.items():
            print(f"  {cls}: {cnt}")
        return result

    def calculate_frequency(self, df):
        """Calculate purchase frequency metrics"""

        for period, months in [("2Yr", None), ("12M", 12), ("6M", 6)]:
            if months:
                cutoff = self.max_date - pd.DateOffset(months=months)
                period_data = self.sales[self.sales["DocDate"] >= cutoff]
            else:
                period_data = self.sales

            purchase_days = period_data.groupby(["BranchName", "Cus.Code"])["DocDate"].nunique()
            df[f"PurchaseDays_{period}"] = df.set_index(["BranchName", "Cus.Code"]).index.map(
                lambda x, pd_=purchase_days: pd_.get(x, 0)
            )
            df[f"PurchaseDays_{period}"] = df[f"PurchaseDays_{period}"].fillna(0)

        total_days = (self.max_date - self.min_date).days
        if total_days < 1:
            total_days = 1
        df["Frequency_2Yr"] = total_days / df["PurchaseDays_2Yr"].replace(0, np.nan)

        print(f"Calculated purchase frequency")
        return df

    def process(self):
        """Run complete classification pipeline"""

        print("\n" + "=" * 60)
        print("RTM OUTLET CLASSIFICATION (Per Branch)")
        print("=" * 60 + "\n")

        print("Step 1: Validating data...")
        self.validate_data()

        print("\nStep 2: Aggregating by customer (per branch)...")
        df = self.aggregate_by_customer()

        print("\nStep 3: Calculating averages...")
        df = self.calculate_averages(df)

        print("\nStep 4: Calculating contributions (per branch)...")
        df = self.calculate_contributions(df)

        print("\nStep 5: Identifying wholesalers...")
        df = self.identify_wholesalers(df)

        print("\nStep 6: Applying Pareto classification (per branch)...")
        df = self.classify_outlets(df)

        print("\nStep 7: Calculating frequency...")
        df = self.calculate_frequency(df)

        self.results = df

        print("\n" + "=" * 60)
        print(f"CLASSIFICATION COMPLETE: {len(df)} customer-branch combinations")
        print(f"Branches: {df['BranchName'].nunique()}")
        print("=" * 60)

        return df

    def get_summary(self):
        """Get classification summary"""

        if self.results is None:
            return None

        summary = (
            self.results.groupby("Classification")
            .agg({"Cus.Code": "count", "TotalSales_2Yr": ["sum", "mean"]})
            .round(2)
        )

        summary.columns = ["Count", "TotalSales", "AvgSales"]
        summary["SalesPct"] = (
            summary["TotalSales"] / summary["TotalSales"].sum() * 100
        ).round(2)

        return summary

    def get_branch_summary(self):
        """Get classification summary per branch"""

        if self.results is None:
            return None

        summary = (
            self.results.groupby(["BranchName", "Classification"])
            .agg({"Cus.Code": "count", "TotalSales_2Yr": "sum"})
            .round(2)
        )
        summary.columns = ["Count", "TotalSales"]
        return summary.reset_index()

    def export_to_excel(self, filepath):
        """Export results to Excel"""

        if self.results is None:
            raise ValueError("No results to export")

        with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
            self.results.to_excel(
                writer, sheet_name="Classification Results", index=False
            )
            self.get_summary().reset_index().to_excel(
                writer, sheet_name="Summary", index=False
            )
            self.get_branch_summary().to_excel(
                writer, sheet_name="By Branch", index=False
            )

        print(f"Exported to {filepath}")


if __name__ == "__main__":
    import sys

    sales_file = sys.argv[1] if len(sys.argv) > 1 else "data/sample_sales.csv"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "output/classification_output.xlsx"

    sales_df = pd.read_csv(sales_file, low_memory=False)
    classifier = RTMClassifier(sales_df)
    results = classifier.process()

    print("\n=== SUMMARY ===")
    print(classifier.get_summary())

    classifier.export_to_excel(output_file)
