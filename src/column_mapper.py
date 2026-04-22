#!/usr/bin/env python3
"""
Column Mapping Utility
Use this to rename your CSV columns to match expected format
"""

import pandas as pd


def map_columns(df, mapping_dict=None):
    """
    Map CSV columns to expected format

    Args:
        df: Input DataFrame
        mapping_dict: Dict of {old_name: new_name}
                     If None, tries automatic mapping

    Returns:
        DataFrame with mapped columns
    """

    if mapping_dict is None:
        # Try automatic mapping based on common variations
        mapping_dict = {
            # Customer ID variations
            "CustomerCode": "Cus.Code",
            "Customer ID": "Cus.Code",
            "CustomerCode": "Cus.Code",
            "CardCode": "Cus.Code",
            "CustCode": "Cus.Code",
            # Customer Name variations
            "CustomerName": "Cus.Name",
            "Customer Name": "Cus.Name",
            "CardName": "Cus.Name",
            "CustName": "Cus.Name",
            # Sales Amount variations
            "Sales": "TotalAmount",
            "SalesAmount": "TotalAmount",
            "Amount": "TotalAmount",
            "NetAmount": "TotalAmount",
            # Quantity variations
            "Qty": "TotalPcs",
            "Quantity": "TotalPcs",
            "Pcs": "TotalPcs",
            "TotalQty": "TotalPcs",
            # Outlet Channel variations
            "Channel": "Outlet Channel",
            "OutletChannel": "Outlet Channel",
            # Item Type variations
            "ItemType": "Item Type",
            "ProductType": "Item Type",
            # Item Class variations
            "ItemClass": "Item Class",
            "ProductClass": "Item Class",
            "Category": "Item Class",
            # NumInBuy variations
            "PackSize": "NumInBuy",
            "Pack": "NumInBuy",
            "NumInPack": "NumInBuy",
            # Date variations
            "Date": "DocDate",
            "TransactionDate": "DocDate",
            "InvDate": "DocDate",
            "InvoiceDate": "DocDate",
            # Invoice variations
            "Invoice": "InvoiceNo",
            "InvoiceNum": "InvoiceNo",
            # Brand variations
            "Brand": "BrandName",
            "ProductBrand": "BrandName",
        }

    # Apply mapping
    df_mapped = df.copy()
    renamed_cols = {}

    for old_name, new_name in mapping_dict.items():
        if old_name in df.columns and new_name not in df.columns:
            df_mapped = df_mapped.rename(columns={old_name: new_name})
            renamed_cols[old_name] = new_name

    return df_mapped, renamed_cols


def validate_columns(df):
    """Check which required columns are present/missing"""

    required = [
        "Cus.Code",
        "Cus.Name",
        "TotalAmount",
        "TotalPcs",
        "Outlet Channel",
        "Item Type",
        "Item Class",
        "NumInBuy",
    ]

    present = [col for col in required if col in df.columns]
    missing = [col for col in required if col not in df.columns]

    return {"present": present, "missing": missing, "all_present": len(missing) == 0}


# Example usage
if __name__ == "__main__":
    # Example: If your CSV has different column names
    example_mapping = {
        "CustomerCode": "Cus.Code",
        "CustomerName": "Cus.Name",
        "SalesAmount": "TotalAmount",
        "Qty": "TotalPcs",
        "Channel": "Outlet Channel",
        "ProductType": "Item Type",
        "Category": "Item Class",
        "PackSize": "NumInBuy",
    }

    print("Column mapping utility ready!")
    print("Use: df_mapped, renamed = map_columns(df, your_mapping)")
