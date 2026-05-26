"""Default Documentation content (markdown). Used to seed /api/docs-content
when no saved data/docs_content.json exists yet. Admins edit it in the UI."""

DEFAULT_DOCS = [
    {
        "id": "rules",
        "label": "Rules",
        "markdown": """## Classification Rules

Outlets are graded **Class A / B / C** by a per-branch Pareto split, with
**F4** wholesalers and category leaders promoted to Class A.

> **These rules are live and configurable.** Open the **Rules** page — every
> parameter (Pareto cut-offs, wholesaler threshold, category override) shows
> exactly how it works and the impact of changing it. Changes are
> version-tracked and apply to the next classification run.
""",
    },
    {
        "id": "input",
        "label": "Input File",
        "kind": "columns",
        "intro": "CSV format specification for the sales data file uploaded on the Classify page.",
        "required": [
            {"column": "Cus.Code", "description": "Unique customer identifier"},
            {"column": "Cus.Name", "description": "Customer / outlet name"},
            {"column": "TotalAmount", "description": "Sales amount per transaction"},
            {"column": "TotalPcs", "description": "Quantity sold in pieces"},
            {"column": "BranchName", "description": "Branch partition key"},
            {"column": "Item Type", "description": "Local or Import"},
            {"column": "Item Class", "description": "Nutrition, Food, Non Food"},
            {"column": "NumInBuy", "description": "Units per carton (for F4)"},
        ],
        "optional": [
            {"column": "DocDate", "description": "Transaction date"},
            {"column": "InvoiceNo", "description": "Invoice number"},
            {"column": "BrandName", "description": "Product brand"},
            {"column": "Outlet Channel", "description": "Channel type"},
            {"column": "Channel", "description": "Channel name (fallback)"},
            {"column": "GroupName", "description": "Customer group"},
        ],
    },
    {
        "id": "algorithm",
        "label": "Algorithm",
        "markdown": """## Algorithm Pseudocode

Core classification pipeline logic.

```
FUNCTION classify(sales_csv, threshold_a=80, threshold_b=95):

  # Step 1: Validate
  ASSERT required_columns EXIST in sales_csv
  PARSE dates, COERCE numeric columns

  # Step 2: Aggregate by customer
  FOR EACH branch IN unique_branches:
    grouped = GROUP BY [Cus.Code, Cus.Name, BranchName]
    COMPUTE:
      TotalSales_2Yr   = SUM(TotalAmount)
      TotalSales_12M   = SUM(TotalAmount WHERE date after -12M)
      TotalSales_6M    = SUM(TotalAmount WHERE date after -6M)
      TotalSales_3M    = SUM(TotalAmount WHERE date after -3M)
      TransactionCount = COUNT(DISTINCT InvoiceNo)

  # Step 3: Calculate contributions (per branch)
  FOR EACH branch:
    SORT outlets BY TotalSales_2Yr DESC
    Overall_Contribution_Pct = TotalSales_2Yr / branch_total * 100
    CumulativePct = RUNNING_SUM(Overall_Contribution_Pct)

  # Step 4: Identify wholesalers
  FOR EACH outlet:
    cartons_per_brand = TotalPcs / NumInBuy / unique_brands / months
    IF cartons_per_brand >= 3 AND ItemType == 'Local':
      Is_Wholesaler = TRUE

  # Step 5: Classify (per branch)
  FOR EACH outlet IN branch (sorted by revenue):
    IF Is_Wholesaler:
      Classification = 'Class A Local (F4)'
    ELSE IF CumulativePct <= threshold_a:
      Classification = 'Class A'
    ELSE IF CumulativePct <= threshold_b:
      Classification = 'Class B'
    ELSE:
      Classification = 'Class C'

  # Step 6: AI enrichment
  AI_Growth_Signal  = RULE(compare 3M vs 12M trend)
  AI_Risk_Level     = RULE(declining + low frequency)
  AI_Visit_Priority = RANK(Classification, Growth, Risk)

  RETURN classified_outlets, branch_summary, insights
```
""",
    },
    {
        "id": "pipeline",
        "label": "Pipeline",
        "markdown": """## Pipeline Steps

10-step execution flow.

1. **Upload** — Receive and parse the sales CSV file
2. **Validate** — Check required columns, parse dates, coerce types
3. **Aggregate** — Group transactions by customer and branch
4. **Averages** — Calculate period sales (2Yr, 12M, 6M, 3M)
5. **Contributions** — Compute revenue contribution % per branch
6. **Wholesalers** — Flag F4 bulk buyers (3+ cartons/brand/month, Local)
7. **Classify** — Apply Pareto 80/15/5 rule per branch partition
8. **Frequency** — Calculate purchase frequency patterns
9. **AI Enrich** — Generate growth signals, risk levels, actions
10. **Results** — Compile dashboard, export, and store job
""",
    },
    {
        "id": "thresholds",
        "label": "Thresholds",
        "markdown": """## Threshold Configuration

The Pareto cut-offs — the Class A ceiling and Class B ceiling — are tunable.

> **Configure them on the Rules page** (Classification Engine section). Each
> slider shows a live A / B / C preview, the change is version-tracked, and it
> applies to the next classification run.
""",
    },
    {
        "id": "ai",
        "label": "AI Fields",
        "markdown": """## AI Enrichment Fields

Every outlet is enriched after classification with:

| Field | Description |
|-------|-------------|
| `AI_Growth_Signal` | Growing / Stable / Declining — 6M vs 12M trend |
| `AI_Risk_Level` | Low / Medium / High — declining sales + low frequency |
| `AI_Visit_Priority` | Rank combining classification, growth and risk |
| `AI_Action` | Recommended next step per outlet |
| `AI_Insight` | LLM-generated per-outlet note (requires an API key) |

> **Tune the AI behaviour on the Rules page** (AI Enrichment section) — growth
> and risk thresholds, plus LLM model settings.
""",
    },
]
