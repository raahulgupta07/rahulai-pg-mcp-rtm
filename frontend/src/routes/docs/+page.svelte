<script lang="ts">
  import ChapterHeading from '$lib/components/ChapterHeading.svelte';
  let activeTab = $state(0);
  const tabs = ['RULES', 'INPUT FILE', 'ALGORITHM', 'PIPELINE', 'THRESHOLDS', 'AI FIELDS'];
</script>

<!-- HERO BOX -->
<div style="background:#383832;color:#feffd6;padding:16px 24px;margin-bottom:24px;border-bottom:4px solid #383832;border-right:4px solid #383832;">
  <div style="font-size:1.5rem;font-weight:900;letter-spacing:-0.03em;">DOCUMENTATION</div>
  <div style="font-size:11px;opacity:0.75;margin-top:4px;">RTM CLASSIFICATION SYSTEM REFERENCE</div>
</div>

<!-- Tab buttons -->
<div style="display:flex;gap:6px;margin-bottom:24px;flex-wrap:wrap;">
  {#each tabs as label, i}
    <button
      onclick={() => activeTab = i}
      style="
        padding:8px 18px;font-size:10px;font-weight:900;letter-spacing:0.08em;
        text-transform:uppercase;cursor:pointer;font-family:'Space Grotesk',sans-serif;
        border:2px solid #383832;transition:all 0.15s;
        {activeTab === i
          ? 'background:#383832;color:#feffd6;box-shadow:3px 3px 0 #383832;'
          : 'background:#feffd6;color:#383832;box-shadow:3px 3px 0 #383832;'}
      "
      onmouseenter={(e) => { if (activeTab !== i) { e.currentTarget.style.background='#007518'; e.currentTarget.style.color='white'; e.currentTarget.style.borderColor='#007518'; }}}
      onmouseleave={(e) => { if (activeTab !== i) { e.currentTarget.style.background='#feffd6'; e.currentTarget.style.color='#383832'; e.currentTarget.style.borderColor='#383832'; }}}
      onmousedown={(e) => { e.currentTarget.style.transform='translate(2px,2px)'; e.currentTarget.style.boxShadow='1px 1px 0 #383832'; }}
      onmouseup={(e) => { e.currentTarget.style.transform='translate(0,0)'; e.currentTarget.style.boxShadow='3px 3px 0 #383832'; }}
    >
      {label}
    </button>
  {/each}
</div>

<div style="max-width:900px;">

<!-- ══ TAB 0: CLASSIFICATION RULES ══ -->
{#if activeTab === 0}
  <ChapterHeading title="Classification Rules" subtitle="Pareto 80/15/5 applied per branch" />
  <div style="background:white;border:3px solid #383832;box-shadow:4px 4px 0 #383832;padding:24px;">
    <table style="width:100%;border-collapse:collapse;font-size:12px;">
      <thead>
        <tr>
          <th style="background:#383832;color:#feffd6;padding:10px 16px;text-align:left;font-size:10px;font-weight:900;letter-spacing:0.1em;">CLASS</th>
          <th style="background:#383832;color:#feffd6;padding:10px 16px;text-align:left;font-size:10px;font-weight:900;letter-spacing:0.1em;">RULE</th>
          <th style="background:#383832;color:#feffd6;padding:10px 16px;text-align:left;font-size:10px;font-weight:900;letter-spacing:0.1em;">TYPICAL %</th>
          <th style="background:#383832;color:#feffd6;padding:10px 16px;text-align:left;font-size:10px;font-weight:900;letter-spacing:0.1em;">DESCRIPTION</th>
        </tr>
      </thead>
      <tbody>
        <tr style="border-bottom:1px solid #ebe8dd;">
          <td style="padding:10px 16px;font-weight:900;color:#007518;">Class A</td>
          <td style="padding:10px 16px;">Cumulative % &le; 80%</td>
          <td style="padding:10px 16px;">~20% of outlets</td>
          <td style="padding:10px 16px;">Top revenue-generating outlets. Highest priority for sales visits and promotions.</td>
        </tr>
        <tr style="background:#fcf9ef;border-bottom:1px solid #ebe8dd;">
          <td style="padding:10px 16px;font-weight:900;color:#ff9d00;">Class B</td>
          <td style="padding:10px 16px;">80% &lt; Cumulative % &le; 95%</td>
          <td style="padding:10px 16px;">~30% of outlets</td>
          <td style="padding:10px 16px;">Growth tier outlets. Regular visits with upsell opportunities.</td>
        </tr>
        <tr style="border-bottom:1px solid #ebe8dd;">
          <td style="padding:10px 16px;font-weight:900;color:#be2d06;">Class C</td>
          <td style="padding:10px 16px;">Cumulative % &gt; 95%</td>
          <td style="padding:10px 16px;">~50% of outlets</td>
          <td style="padding:10px 16px;">Long-tail outlets. Minimal direct visits, digital/telesales preferred.</td>
        </tr>
        <tr style="background:#fcf9ef;">
          <td style="padding:10px 16px;font-weight:900;color:#006f7c;">F4 (Wholesaler)</td>
          <td style="padding:10px 16px;">&ge;3 cartons/brand/month, Local items</td>
          <td style="padding:10px 16px;">Variable</td>
          <td style="padding:10px 16px;">Bulk buyers of Local products. Auto-classified as Class A regardless of revenue rank.</td>
        </tr>
      </tbody>
    </table>
  </div>

<!-- ══ TAB 1: INPUT FILE ══ -->
{:else if activeTab === 1}
  <ChapterHeading title="Input File Requirements" subtitle="CSV format specification for the sales data file" />
  <div style="background:white;border:3px solid #383832;box-shadow:4px 4px 0 #383832;padding:24px;">
    <div style="font-size:12px;font-weight:900;color:#383832;margin-bottom:12px;">REQUIRED COLUMNS</div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:8px;margin-bottom:20px;">
      {#each [
        { col: 'Cus.Code', desc: 'Unique customer identifier' },
        { col: 'Cus.Name', desc: 'Customer / outlet name' },
        { col: 'TotalAmount', desc: 'Sales amount per transaction' },
        { col: 'TotalPcs', desc: 'Quantity sold in pieces' },
        { col: 'BranchName', desc: 'Branch partition key' },
        { col: 'Item Type', desc: 'Local or Import' },
        { col: 'Item Class', desc: 'Nutrition, Food, Non Food' },
        { col: 'NumInBuy', desc: 'Units per carton (for F4)' },
      ] as item}
        <div style="padding:8px 12px;background:#f6f4e9;border:1px solid #ebe8dd;">
          <div style="font-size:10px;font-weight:900;color:#007518;letter-spacing:0.06em;">{item.col}</div>
          <div style="font-size:10px;color:#65655e;margin-top:2px;">{item.desc}</div>
        </div>
      {/each}
    </div>
    <div style="font-size:12px;font-weight:900;color:#383832;margin-bottom:12px;">OPTIONAL COLUMNS</div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;">
      {#each ['DocDate', 'InvoiceNo', 'BrandName', 'Outlet Channel', 'Channel', 'GroupName'] as col}
        <span style="padding:4px 12px;font-size:10px;font-weight:700;background:#ebe8dd;color:#65655e;border:1px solid #828179;">{col}</span>
      {/each}
    </div>
  </div>

<!-- ══ TAB 2: ALGORITHM ══ -->
{:else if activeTab === 2}
  <ChapterHeading title="Algorithm Pseudocode" subtitle="Core classification pipeline logic" />
  <div style="background:#383832;border:3px solid #383832;box-shadow:4px 4px 0 #383832;overflow:hidden;">
    <div style="padding:10px 16px;font-size:10px;font-weight:900;letter-spacing:0.1em;color:#feffd6;border-bottom:1px solid rgba(254,255,214,0.15);">PIPELINE.PY</div>
    <pre style="margin:0;padding:20px;color:#feffd6;font-size:11px;line-height:1.7;overflow-x:auto;font-family:'Space Grotesk',monospace;"><code>FUNCTION classify(sales_csv, threshold_a=80, threshold_b=95):

  # Step 1: Validate
  ASSERT required_columns EXIST in sales_csv
  PARSE dates, COERCE numeric columns

  # Step 2: Aggregate by customer
  FOR EACH branch IN unique_branches:
    grouped = GROUP BY [Cus.Code, Cus.Name, BranchName]
    COMPUTE:
      TotalSales_2Yr  = SUM(TotalAmount)
      TotalSales_12M  = SUM(TotalAmount WHERE date after -12M)
      TotalSales_6M   = SUM(TotalAmount WHERE date after -6M)
      TotalSales_3M   = SUM(TotalAmount WHERE date after -3M)
      TotalPcs        = SUM(TotalPcs)
      TransactionCount = COUNT(DISTINCT InvoiceNo)

  # Step 3: Calculate contributions (per branch)
  FOR EACH branch:
    SORT outlets BY TotalSales_2Yr DESC
    Overall_Contribution_Pct = TotalSales_2Yr / branch_total * 100
    CumulativePct = RUNNING_SUM(Overall_Contribution_Pct)

  # Step 4: Identify wholesalers
  FOR EACH outlet:
    cartons_per_brand = TotalPcs / NumInBuy / unique_brands / months
    IF cartons_per_brand &gt;= 3 AND ItemType == 'Local':
      Is_Wholesaler = TRUE

  # Step 5: Classify (per branch)
  FOR EACH outlet IN branch (sorted by revenue):
    IF Is_Wholesaler:
      Classification = 'Class A Local (F4)'
    ELSE IF CumulativePct &lt;= threshold_a:
      Classification = 'Class A'
    ELSE IF CumulativePct &lt;= threshold_b:
      Classification = 'Class B'
    ELSE:
      Classification = 'Class C'

  # Step 6: Frequency analysis
  Frequency_2Yr = TransactionCount / months_active

  # Step 7: AI enrichment
  AI_Growth_Signal  = RULE(compare 3M vs 12M trend)
  AI_Risk_Level     = RULE(declining + low frequency)
  AI_Visit_Priority = RANK(Classification, Growth, Risk)
  AI_Action         = GENERATE(summary recommendation)

  RETURN classified_outlets, branch_summary, insights</code></pre>
  </div>

<!-- ══ TAB 3: PIPELINE STEPS ══ -->
{:else if activeTab === 3}
  <ChapterHeading title="Pipeline Steps" subtitle="10-step execution flow" />
  <div style="background:white;border:3px solid #383832;box-shadow:4px 4px 0 #383832;padding:24px;">
    {#each [
      { n: '01', title: 'UPLOAD', desc: 'Receive and parse the sales CSV file' },
      { n: '02', title: 'VALIDATE', desc: 'Check required columns, parse dates, coerce types' },
      { n: '03', title: 'AGGREGATE', desc: 'Group transactions by customer and branch' },
      { n: '04', title: 'AVERAGES', desc: 'Calculate period sales (2Yr, 12M, 6M, 3M)' },
      { n: '05', title: 'CONTRIBUTIONS', desc: 'Compute revenue contribution % per branch' },
      { n: '06', title: 'WHOLESALERS', desc: 'Flag F4 bulk buyers (3+ cartons/brand/month, Local)' },
      { n: '07', title: 'CLASSIFY', desc: 'Apply Pareto 80/15/5 rule per branch partition' },
      { n: '08', title: 'FREQUENCY', desc: 'Calculate purchase frequency patterns' },
      { n: '09', title: 'AI ENRICH', desc: 'Generate growth signals, risk levels, actions' },
      { n: '10', title: 'RESULTS', desc: 'Compile dashboard, export, and store job' },
    ] as step}
      <div style="display:flex;align-items:center;gap:16px;padding:10px 0;border-bottom:1px solid #ebe8dd;">
        <div style="width:32px;height:32px;background:#383832;color:#00fc40;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:900;flex-shrink:0;">{step.n}</div>
        <div>
          <div style="font-size:11px;font-weight:900;letter-spacing:0.08em;color:#383832;">{step.title}</div>
          <div style="font-size:11px;color:#65655e;margin-top:1px;">{step.desc}</div>
        </div>
      </div>
    {/each}
  </div>

<!-- ══ TAB 4: THRESHOLDS ══ -->
{:else if activeTab === 4}
  <ChapterHeading title="Threshold Configuration" subtitle="Customizable Pareto cutoff points" />
  <div style="background:white;border:3px solid #383832;box-shadow:4px 4px 0 #383832;padding:24px;">
    <table style="width:100%;border-collapse:collapse;font-size:12px;">
      <thead>
        <tr>
          <th style="background:#383832;color:#feffd6;padding:10px 16px;text-align:left;font-size:10px;font-weight:900;letter-spacing:0.1em;">PARAMETER</th>
          <th style="background:#383832;color:#feffd6;padding:10px 16px;text-align:left;font-size:10px;font-weight:900;letter-spacing:0.1em;">DEFAULT</th>
          <th style="background:#383832;color:#feffd6;padding:10px 16px;text-align:left;font-size:10px;font-weight:900;letter-spacing:0.1em;">RANGE</th>
          <th style="background:#383832;color:#feffd6;padding:10px 16px;text-align:left;font-size:10px;font-weight:900;letter-spacing:0.1em;">EFFECT</th>
        </tr>
      </thead>
      <tbody>
        <tr style="border-bottom:1px solid #ebe8dd;">
          <td style="padding:10px 16px;font-weight:800;">threshold_a</td>
          <td style="padding:10px 16px;">80%</td>
          <td style="padding:10px 16px;">50% - 95%</td>
          <td style="padding:10px 16px;">Cumulative revenue cutoff for Class A. Lower = fewer Class A outlets.</td>
        </tr>
        <tr style="background:#fcf9ef;">
          <td style="padding:10px 16px;font-weight:800;">threshold_b</td>
          <td style="padding:10px 16px;">95%</td>
          <td style="padding:10px 16px;">55% - 99%</td>
          <td style="padding:10px 16px;">Cumulative revenue cutoff for Class B. Must be greater than threshold_a.</td>
        </tr>
      </tbody>
    </table>
  </div>

<!-- ══ TAB 5: AI FIELDS ══ -->
{:else if activeTab === 5}
  <ChapterHeading title="AI Enrichment Fields" subtitle="Rule-based and LLM-powered analysis" />
  <div style="background:white;border:3px solid #383832;box-shadow:4px 4px 0 #383832;padding:24px;">
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;">
      {#each [
        { field: 'AI_Growth_Signal', desc: 'Growing / Stable / Declining based on 3M vs 12M trend comparison' },
        { field: 'AI_Risk_Level', desc: 'Low / Medium / High based on declining sales + low purchase frequency' },
        { field: 'AI_Visit_Priority', desc: 'Numeric rank (1-5) combining classification, growth, and risk signals' },
        { field: 'AI_Action', desc: 'Recommended action item (e.g., increase visits, cross-sell, monitor)' },
        { field: 'AI_Insight', desc: 'LLM-generated per-outlet insight (requires API key)' },
      ] as item}
        <div style="padding:12px;background:#f6f4e9;border:1px solid #ebe8dd;">
          <div style="font-size:10px;font-weight:900;color:#006f7c;letter-spacing:0.06em;margin-bottom:4px;">{item.field}</div>
          <div style="font-size:10px;color:#65655e;line-height:1.5;">{item.desc}</div>
        </div>
      {/each}
    </div>
  </div>
{/if}

</div>
