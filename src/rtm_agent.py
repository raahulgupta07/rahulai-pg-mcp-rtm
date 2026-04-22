#!/usr/bin/env python3
"""
RTM Classification Agent
AI-powered assistant that explains each step of the classification process
"""

import streamlit as st
from datetime import datetime


class RTMAgent:
    """
    AI Agent that provides explanations for each step of RTM classification
    """

    def __init__(self):
        self.step_explanations = {}
        self.data_summary = {}

    def set_data_summary(self, results_df, summary_df):
        """Store data summary for agent context"""
        self.data_summary = {
            "total_customers": len(results_df),
            "total_sales": results_df["TotalSales_2Yr"].sum(),
            "class_distribution": results_df["Classification"].value_counts().to_dict(),
            "top_customers": results_df.nlargest(5, "TotalSales_2Yr")[
                ["Cus.Code", "Cus.Name", "TotalSales_2Yr", "Classification"]
            ].to_dict("records"),
            "wholesaler_count": results_df["Is_Wholesaler"].sum(),
            "date_range": f"{results_df['FirstPurchaseDate'].min()} to {results_df['LastPurchaseDate'].max()}",
        }

    def get_step_explanation(self, step_name):
        """Get explanation for each classification step"""

        explanations = {
            "1_validate": """
## Step 1: Data Validation ✅

**What happens:**
- The system checks if your CSV has all required columns
- Validates data types (numbers, dates, etc.)
- Checks for missing or invalid values

**Required Columns:**
- `Cus.Code` - Customer ID
- `Cus.Name` - Customer Name  
- `TotalAmount` - Sales Amount
- `TotalPcs` - Quantity Sold
- `Outlet Channel` - Channel Type
- `Item Type` - Local/Import
- `Item Class` - Category
- `NumInBuy` - Units per Carton

**If columns are missing:**
- Required columns → ERROR (won't proceed)
- Optional columns → WARNING + use defaults
""",
            "2_aggregate": """
## Step 2: Customer Aggregation ✅

**What happens:**
- Groups all transactions by customer (Cus.Code)
- Calculates total sales per customer
- Counts number of transactions
- Identifies first and last purchase dates

**Calculations:**
```
TotalSales = SUM(All Transaction Amounts)
TotalPcs = SUM(All Quantities)
TransactionCount = COUNT(Unique Invoices)
FirstPurchase = MIN(Transaction Date)
LastPurchase = MAX(Transaction Date)
```
""",
            "3_averages": """
## Step 3: Period Averages ✅

**What happens:**
- Calculates average sales for different time periods
- Helps identify trends and growth patterns

**Time Periods:**
- **2 Year Average**: Total Sales ÷ 24 months
- **12 Month Average**: Last 12 months sales ÷ 12
- **6 Month Average**: Last 6 months sales ÷ 6
- **3 Month Average**: Last 3 months sales ÷ 3

**By Category:**
- Also calculated separately for:
  - Nutrition, Food, Non Food
  - Local, Import
""",
            "4_contributions": """
## Step 4: Contribution Analysis ✅

**What happens:**
- Calculates each customer's contribution to total business
- Shows market share by customer and category

**Formula:**
```
Customer Contribution % = (Customer Sales ÷ Total Branch Sales) × 100
```

**Categories Analyzed:**
- Overall (all products)
- By Item Class: Nutrition, Food, Non Food
- By Item Type: Local, Import

**Key Insight:** The sum of all customer contributions = 100%
""",
            "5_wholesaler": """
## Step 5: Wholesaler Identification ✅

**What happens:**
- Identifies bulk buyers (wholesalers) based on purchase volume
- These are key distribution points in the supply chain

**Wholesaler Criteria:**
- Purchases ≥ 3 cartons per brand per month
- Only Local products (not Import)
- Reviewed over the data period

**Formula:**
```
Cartons = TotalPcs ÷ NumInBuy
Is Wholesaler = True if (Cartons ≥ 3 for any brand/month)
```

**Result:** Classified as "Class A Local (F4)" - highest priority
""",
            "6_classify": """
## Step 6: Pareto Classification (80/15/5) ✅

**What happens:**
- Applies the Pareto principle (80/20 rule)
- Classifies outlets based on business contribution

**Classification Rules:**

| Class | Contribution | Description |
|-------|---------------|-------------|
| **Class A** | Top 80% | High-priority outlets |
| **Class B** | 80-95% | Medium-priority |
| **Class C** | Remaining 5% | Low-priority |

**Special Overrides:**
- Wholesalers → Class A Local (F4)
- Any category ≥80% → Class A [Category]
""",
            "7_frequency": """
## Step 7: Purchase Frequency ✅

**What happens:**
- Measures how often customers make purchases
- Helps plan visit schedules

**Calculations:**
```
PurchaseDays = COUNT(Unique Transaction Dates)
Frequency = Total Days ÷ Purchase Days
```

**Example:**
- If customer purchases on 100 days over 2 years (730 days)
- Frequency = 730 ÷ 100 = 7.3 days between purchases

**Lower frequency = More regular customer**
""",
            "8_complete": """
## Step 8: Classification Complete ✅

**Final Output Generated:**
- Customer classification results
- Summary statistics
- Excel export ready

**Classification Summary:**
See dashboard for distribution by class.
""",
        }

        return explanations.get(step_name, "Step not found")

    def answer_question(self, question, results_df=None):
        """Answer user questions about the classification"""

        question = question.lower()

        # Get data summary if available
        if results_df is not None and self.data_summary:
            total = self.data_summary.get("total_customers", "N/A")
            sales = self.data_summary.get("total_sales", 0)
        else:
            total = "N/A"
            sales = 0

        # Predefined Q&A
        qa_pairs = {
            "what is class a": """
**Class A Outlets** are the top 80% of your customers by sales.

These are your most important customers who generate the majority of revenue.
They should receive:
- Priority service
- Frequent visits
- Special attention
- Better credit terms
""",
            "what is class b": """
**Class B Outlets** are the next 15% (from 80% to 95%).

These are medium-performing customers with growth potential.
They could become Class A with:
- Better service
- Promotional support
- Regular visits
""",
            "what is class c": """
**Class C Outlets** are the bottom 5% of customers.

These are low-performing outlets with minimal contribution.
Options:
- Reduce visit frequency
- Consider dropping if unprofitable
- Use for overflow orders
""",
            "what is f4": """
**Class A Local (F4)** = Wholesalers

These are bulk buyers who purchase ≥3 cartons per brand monthly.
They serve as distribution points to smaller retailers.

Key characteristics:
- Buy in bulk (3+ cartons per brand)
- Resell to other retailers
- Important for market reach
- High priority for delivery
""",
            "how many customers": f"""
**Total Customers: {total}**

This is the number of unique outlets in your sales data.
""",
            "total sales": f"""
**Total Sales: {sales:,.0f} MMK**

This is the sum of all sales over the data period.
""",
            "what is pareto": """
**Pareto Principle (80/20 Rule)**

The concept that 80% of effects come from 20% of causes.

In RTM:
- Top 20% of customers = 80% of sales
- Focus resources on high-value outlets
- Optimize route efficiency
""",
            "how is classification calculated": """
**Classification is calculated in 3 steps:**

1. **Rank customers** by total sales (highest first)
2. **Calculate cumulative %** running total ÷ total sales
3. **Apply thresholds:**
   - ≤80% cumulative → Class A
   - 80-95% → Class B  
   - >95% → Class C

**Plus special rules:**
- Wholesalers → F4
- Category leaders → Category A
""",
        }

        # Match question
        for key, answer in qa_pairs.items():
            if key in question:
                return answer

        # Default response
        return """
I'm here to help! You can ask me questions like:

- What is Class A?
- What is F4?
- How many customers?
- Total sales?
- What is Pareto?
- How is classification calculated?

Or check each step in the pipeline for detailed explanations.
"""

    def display_step_ui(self, step_name):
        """Display step explanation in Streamlit"""
        import streamlit as st

        explanation = self.get_step_explanation(step_name)

        with st.expander(
            f"📖 Step {step_name.split('_')[0]}: Explain This Step", expanded=False
        ):
            st.markdown(explanation)


# Singleton instance
agent = RTMAgent()
