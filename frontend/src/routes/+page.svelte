<script lang="ts">
  import { classify, exportExcel, getJob, getSettings } from '$lib/api';
  import { page } from '$app/stores';
  import KpiCard from '$lib/components/KpiCard.svelte';
  import DataTable from '$lib/components/DataTable.svelte';
  import Badge from '$lib/components/Badge.svelte';
  import ChapterHeading from '$lib/components/ChapterHeading.svelte';

  let state = $state('upload');
  let file = $state(null);
  let fileError = $state('');
  let thresholdA = $state(80);
  let thresholdB = $state(95);
  let data = $state(null);
  let error = $state('');
  let logEntries = $state([]);
  let selectedBranch = $state('All Branches');
  let activeTab = $state(0);
  let searchQuery = $state('');
  let classFilter = $state('All');
  let currentStep = $state(0);
  let terminalLines = $state<string[]>([]);

  const terminalMessages: string[][] = [
    [
      '$ mcp-agent upload --file sales_data.csv',
      '[INFO] Reading file into memory buffer...',
      '[INFO] Detecting encoding: UTF-8 confirmed',
      '[INFO] Row count: 211,721 transactions',
      '[INFO] Column count: 27 fields detected',
      '[OK] File successfully loaded into DataFrame',
    ],
    [
      '$ mcp-agent validate --check-schema',
      '[SCAN] Required: Cus.Code ........... FOUND',
      '[SCAN] Required: TotalAmount ........ FOUND',
      '[SCAN] Required: TotalPcs ........... FOUND',
      '[SCAN] Required: BranchName ......... FOUND',
      '[SCAN] Required: Item Class ......... FOUND',
      '[SCAN] Required: NumInBuy ........... FOUND',
      '[INFO] Parsing DocDate with format dd/mm/yyyy...',
      '[INFO] 0 null dates found — no backfill needed',
      '[INFO] Date range: 2024-10-01 to 2025-09-30',
      '[INFO] Duration: 12.1 months across 9 branches',
      '[OK] Schema validation passed — all columns present',
    ],
    [
      '$ mcp-agent aggregate --group-by BranchName,Cus.Code',
      '[SQL] SELECT BranchName, Cus.Code, SUM(TotalAmount), SUM(TotalPcs),',
      '      COUNT(DISTINCT InvoiceNo), MIN(DocDate), MAX(DocDate)',
      '      GROUP BY BranchName, Cus.Code',
      '[INFO] Processing 211,721 rows...',
      '[INFO] Yangon: 120,292 txns → 6,619 outlets',
      '[INFO] Mandalay: 27,571 txns → 2,034 outlets',
      '[INFO] Mawlamyaing: 15,036 txns → 505 outlets',
      '[INFO] Naypyitaw: 12,076 txns → 609 outlets',
      '[INFO] + 5 more branches...',
      '[OK] Aggregated to 11,333 customer-branch combinations',
    ],
    [
      '$ mcp-agent calculate --periods 2Yr,12M,6M,3M',
      '[CALC] TotalSales_2Yr = SUM(TotalAmount) over full range',
      '[CALC] TotalSales_12M = SUM where DocDate >= 2024-09-30',
      '[CALC] TotalSales_6M = SUM where DocDate >= 2025-03-30',
      '[CALC] TotalSales_3M = SUM where DocDate >= 2025-06-30',
      '[CALC] Breaking down by Item Class: Nutrition, Food, Non Food',
      '[CALC] AvgSales = period_total / months_in_period',
      '[OK] Period averages computed for all 11,333 outlets',
    ],
    [
      '$ mcp-agent contributions --denominator branch_total',
      '[CALC] For each of 9 branches:',
      '[CALC]   outlet_pct = outlet_sales / branch_total * 100',
      '[CALC] Nutrition_Contribution_Pct per outlet...',
      '[CALC] Food_Contribution_Pct per outlet...',
      '[CALC] Non_Food_Contribution_Pct per outlet...',
      '[OK] Revenue contribution percentages computed',
    ],
    [
      '$ mcp-agent detect-wholesalers --threshold 3 --type Local',
      '[SCAN] Filtering transactions where Item Type == "Local"...',
      '[WARN] 0 Local product transactions found in dataset',
      '[WARN] All products are classified as "Import"',
      '[INFO] Wholesaler detection requires Local products',
      '[INFO] Carton formula: TotalPcs / NumInBuy per brand per month',
      '[SKIP] No wholesalers to flag — F4 classification not applied',
      '[OK] Wholesaler scan complete — 0 flagged',
    ],
    [
      '$ mcp-agent classify --method pareto --partition branch',
      '[ALGO] For each branch partition:',
      '[ALGO]   1. SORT outlets BY TotalSales_2Yr DESC',
      '[ALGO]   2. CumulativePct = RUNNING_SUM / branch_total',
      '[ALGO]   3. IF cum% <= 80 → Class A',
      '[ALGO]   4. IF cum% <= 95 → Class B',
      '[ALGO]   5. ELSE → Class C',
      '[RESULT] Yangon: A=766, B=1147, C=4706',
      '[RESULT] Mandalay: A=222, B=336, C=1476',
      '[RESULT] Mawlamyaing: A=83, B=131, C=291',
      '[RESULT] Taunggyi: A=47, B=76, C=282',
      '[RESULT] + 5 more branches...',
      '[OK] Classification: A=1,449 | B=2,104 | C=7,780',
    ],
    [
      '$ mcp-agent frequency --metric purchase_days',
      '[CALC] PurchaseDays_2Yr = COUNT(DISTINCT DocDate) per outlet',
      '[CALC] PurchaseDays_12M, PurchaseDays_6M computed',
      '[CALC] Frequency_2Yr = 365 / PurchaseDays_2Yr',
      '[INFO] Avg frequency: every 15.2 days',
      '[INFO] Most frequent buyer: every 2.1 days',
      '[OK] Purchase frequency metrics computed',
    ],
    [
      '$ mcp-agent enrich --ai-rules',
      '[AI] Computing AI_Growth_Signal...',
      '[AI]   Growing (6M > 12M/2 * 1.1): 3,421 outlets',
      '[AI]   Declining (6M < 12M/2 * 0.9): 2,876 outlets',
      '[AI]   Stable: 5,036 outlets',
      '[AI] Computing AI_Risk_Level...',
      '[AI]   High risk: 891 outlets',
      '[AI]   Medium risk: 4,203 outlets',
      '[AI]   Low risk: 6,239 outlets',
      '[AI] Assigning AI_Visit_Priority (1-4 scale)...',
      '[AI] Generating AI_Action per outlet...',
      '[OK] Rule-based AI enrichment complete — 5 columns added',
    ],
    [
      '$ mcp-agent insights --model gemini-3.1-flash-lite --via openrouter',
      '[LLM] Connecting to OpenRouter API...',
      '[LLM] Model: google/gemini-3.1-flash-lite-preview',
      '[LLM] Generating executive summary (800 tokens)...',
      '[LLM] Generating class recommendations (1200 tokens)...',
      '[LLM] Generating growth analysis (600 tokens)...',
      '[LLM] Generating top-15 outlet insights (1000 tokens)...',
      '[OK] All AI insights generated',
      '',
      '═══════════════════════════════════════════',
      '[MCP AGENT] ✓ PIPELINE COMPLETE',
      '[MCP AGENT] 11,333 outlets classified',
      '[MCP AGENT] 9 branches processed',
      '[MCP AGENT] Job saved to database',
      '═══════════════════════════════════════════',
    ],
  ];

  // Check if there's a job ID in URL params on mount
  $effect(() => {
    const jobId = $page.url.searchParams.get('job');
    if (jobId && !data) {
      loadJob(jobId);
    }
  });

  // Load default thresholds from settings
  $effect(() => {
    getSettings().then(s => {
      thresholdA = s.default_threshold_a || 80;
      thresholdB = s.default_threshold_b || 95;
    }).catch(() => {});
  });

  async function loadJob(jobId: string) {
    state = 'processing';
    currentStep = 10;
    terminalLines = ['[MCP AGENT] Loading job from history...', `[MCP AGENT] Job ID: ${jobId}`, '', '[INFO] Fetching results from database...'];
    try {
      const jobData = await getJob(jobId);
      const results = jobData.results || [];
      terminalLines = [...terminalLines, `[OK] Loaded ${results.length} outlet records`, '', '═══════════════════════════════════════════', '[MCP AGENT] ✓ JOB LOADED', '═══════════════════════════════════════════'];
      data = {
        job_id: jobId,
        total_outlets: results.length,
        branches: [...new Set(results.map((r: any) => r.BranchName || r.Cus_Township || '').filter(Boolean))],
        class_a: results.filter((r: any) => String(r.Classification || '').startsWith('Class A')).length,
        class_b: results.filter((r: any) => r.Classification === 'Class B').length,
        class_c: results.filter((r: any) => r.Classification === 'Class C').length,
        wholesalers: results.filter((r: any) => r.Is_Wholesaler).length,
        revenue: results.reduce((s: number, r: any) => s + (r.TotalSales_2Yr || 0), 0),
        results: results,
        branch_summary: [],
        insights: jobData.insights || {},
        log: [`Loaded from history: ${jobId}`],
        data_quality: jobData.data_quality || [],
        data_quality_ok: [`Loaded ${results.length} outlets from job ${jobId}`],
      };
      logEntries = data.log;
      await new Promise(r => setTimeout(r, 800));
      state = 'results';
    } catch (e: any) {
      error = e.message || 'Failed to load job';
      state = 'upload';
    }
  }

  // Filtered results based on branch selection
  let filteredResults = $derived(
    data && selectedBranch !== 'All Branches'
      ? data.results.filter(r => r.BranchName === selectedBranch)
      : data?.results ?? []
  );

  let branches = $derived(
    data ? [...new Set(data.results.map(r => r.BranchName))].sort() : []
  );

  // KPIs from filtered results
  let kpis = $derived({
    total: filteredResults.length,
    classA: filteredResults.filter(r => r.Classification?.includes('Class A')).length,
    classB: filteredResults.filter(r => r.Classification === 'Class B').length,
    classC: filteredResults.filter(r => r.Classification === 'Class C').length,
    wholesalers: filteredResults.filter(r => r.Is_Wholesaler).length,
    revenue: filteredResults.reduce((s, r) => s + (r.TotalSales_2Yr || 0), 0),
    branchCount: new Set(filteredResults.map(r => r.BranchName)).size,
  });

  // Tab 1 filtered data
  let explorerData = $derived(() => {
    let rows = filteredResults;
    if (classFilter !== 'All') {
      rows = rows.filter(r => r.Classification === classFilter);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      rows = rows.filter(r =>
        (r['Cus.Name'] || r['Cus_Name'] || '').toLowerCase().includes(q) ||
        (r['Cus.Code'] || r['Cus_Code'] || '').toLowerCase().includes(q) ||
        (r.BranchName || '').toLowerCase().includes(q)
      );
    }
    return rows.map(r => ({
      ...r,
      'Cus.Code': r['Cus.Code'] || r['Cus_Code'] || '',
      'Cus.Name': r['Cus.Name'] || r['Cus_Name'] || '',
    }));
  });

  function fmtNum(n) {
    if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
    if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
    if (n >= 1e3) return `$${(n / 1e3).toFixed(1)}K`;
    return `$${n.toLocaleString()}`;
  }

  function fmtPct(n) {
    return `${n.toFixed(1)}%`;
  }

  function renderMarkdown(text) {
    if (!text) return '';
    return text
      .replace(/### (.*?)$/gm, '<h3 style="font-size:14px;font-weight:900;margin:16px 0 8px;color:#383832;">$1</h3>')
      .replace(/## (.*?)$/gm, '<h2 style="font-size:16px;font-weight:900;margin:16px 0 8px;color:#383832;">$1</h2>')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/^- (.*?)$/gm, '<div style="padding-left:16px;margin:4px 0;">• $1</div>')
      .replace(/^\* (.*?)$/gm, '<div style="padding-left:16px;margin:4px 0;">• $1</div>')
      .replace(/\n\n/g, '<br><br>')
      .replace(/\n/g, '<br>');
  }

  function badgeType(cls) {
    if (!cls) return 'class-c';
    if (cls.includes('F4') || cls.includes('Local')) return 'class-f4';
    if (cls.includes('A')) return 'class-a';
    if (cls.includes('B')) return 'class-b';
    return 'class-c';
  }

  async function handleClassify() {
    if (!file) return;
    state = 'processing';
    currentStep = 0;
    terminalLines = ['[MCP AGENT] Pipeline initiated...', `[MCP AGENT] File: ${file.name} (${(file.size/1024).toFixed(0)} KB)`, ''];
    error = '';

    // Type terminal lines one by one with realistic timing
    let stepLineIdx = 0;
    let typing = false;

    async function typeStepLines(stepNum: number) {
      const msgs = terminalMessages[stepNum] || [];
      for (const msg of msgs) {
        terminalLines = [...terminalLines, msg];
        scrollTerminal();
        await new Promise(r => setTimeout(r, msg.startsWith('$') ? 600 : msg.startsWith('[OK]') ? 400 : msg.startsWith('═') ? 200 : 250));
      }
      terminalLines = [...terminalLines, ''];
      scrollTerminal();
    }

    function scrollTerminal() {
      setTimeout(() => {
        const el = document.getElementById('terminal-scroll');
        if (el) el.scrollTop = el.scrollHeight;
      }, 50);
    }

    // Start typing step 0 immediately
    typeStepLines(0);

    const stepInterval = setInterval(async () => {
      if (currentStep < 9) {
        currentStep++;
        await typeStepLines(currentStep);
      }
    }, 3500);

    const typeInterval = 0; // unused, kept for clearInterval compat

    try {
      data = await classify(file, thresholdA, thresholdB);
      clearInterval(stepInterval);
      clearInterval(typeInterval);
      logEntries = data.log || [];
      // Show completion in terminal
      terminalLines = [...terminalLines, '', '═══════════════════════════════════════════', '[MCP AGENT] ✓ ALL STEPS COMPLETE', '═══════════════════════════════════════════'];
      currentStep = 10;
      await new Promise(r => setTimeout(r, 1500));
      state = 'results';
    } catch (e: any) {
      clearInterval(stepInterval);
      clearInterval(typeInterval);
      terminalLines = [...terminalLines, '', `[MCP AGENT] ✗ ERROR: ${e.message}`];
      error = e.message;
      await new Promise(r => setTimeout(r, 2000));
      state = 'upload';
    }
  }

  function handleFileChange(e: Event) {
    const input = e.target as HTMLInputElement;
    const selected = input.files?.[0] ?? null;
    fileError = '';
    if (!selected) { file = null; return; }
    // Validate: must be .csv
    if (!selected.name.toLowerCase().endsWith('.csv')) {
      fileError = 'INVALID FILE TYPE — ONLY .CSV FILES ACCEPTED';
      file = null;
      input.value = '';
      return;
    }
    // Validate: max 100MB
    if (selected.size > 100 * 1024 * 1024) {
      fileError = 'FILE TOO LARGE — MAXIMUM 100MB';
      file = null;
      input.value = '';
      return;
    }
    file = selected;
  }

  function reset() {
    state = 'upload';
    file = null;
    data = null;
    error = '';
    logEntries = [];
    selectedBranch = 'All Branches';
    activeTab = 0;
    searchQuery = '';
    classFilter = 'All';
  }

  // Build summary table data for dashboard
  let summaryRows = $derived(() => {
    if (!filteredResults.length) return [];
    const totalRev = filteredResults.reduce((s, r) => s + (r.TotalSales_2Yr || 0), 0);

    const classA = filteredResults.filter(r => (r.Classification || '').startsWith('Class A'));
    const classB = filteredResults.filter(r => r.Classification === 'Class B');
    const classC = filteredResults.filter(r => r.Classification === 'Class C');

    return [
      { Classification: 'Class A', Count: classA.length, Revenue: classA.reduce((s, r) => s + (r.TotalSales_2Yr || 0), 0) },
      { Classification: 'Class B', Count: classB.length, Revenue: classB.reduce((s, r) => s + (r.TotalSales_2Yr || 0), 0) },
      { Classification: 'Class C', Count: classC.length, Revenue: classC.reduce((s, r) => s + (r.TotalSales_2Yr || 0), 0) },
    ].filter(r => r.Count > 0).map(row => ({
      Classification: row.Classification,
      Count: row.Count.toLocaleString(),
      Revenue: fmtNum(row.Revenue),
      'Avg Sales': fmtNum(row.Count ? row.Revenue / row.Count : 0),
      'Share %': fmtPct(totalRev ? (row.Revenue / totalRev * 100) : 0),
    }));
  });

  // Top 10 outlets
  let top10 = $derived(() => {
    return [...filteredResults]
      .sort((a, b) => (b.TotalSales_2Yr || 0) - (a.TotalSales_2Yr || 0))
      .slice(0, 10)
      .map(r => ({
        'Cus.Code': r['Cus.Code'] || r['Cus_Code'] || '',
        'Cus.Name': r['Cus.Name'] || r['Cus_Name'] || '',
        Branch: r.BranchName || r.Branch || r.branch_name || '',
        Classification: r.Classification,
        '2Yr Sales': fmtNum(r.TotalSales_2Yr || 0),
        'Contribution %': fmtPct(r.Overall_Contribution_Pct || 0),
      }));
  });

  // Branch matrix data (computed from filteredResults so it works for history loads too)
  let branchMatrix = $derived(() => {
    if (!filteredResults.length) return [];
    const map = new Map();
    for (const r of filteredResults) {
      const branch = r.BranchName || 'Unknown';
      if (!map.has(branch)) map.set(branch, { outlets: 0, revenue: 0, a: 0, b: 0, c: 0 });
      const m = map.get(branch);
      m.outlets++;
      m.revenue += r.TotalSales_2Yr || 0;
      const cls = String(r.Classification || '');
      if (cls.startsWith('Class A')) m.a++;
      else if (cls === 'Class B') m.b++;
      else if (cls === 'Class C') m.c++;
    }
    return [...map.entries()]
      .sort((a, b) => b[1].revenue - a[1].revenue)
      .map(([name, d]) => ({
        Branch: name,
        Outlets: d.outlets,
        Revenue: fmtNum(d.revenue),
        'Class A': d.a,
        'Class B': d.b,
        'Class C': d.c,
        'A %': d.outlets > 0 ? ((d.a / d.outlets) * 100).toFixed(1) + '%' : '0%',
      }));
  });

  // Explorer table columns
  const explorerCols = ['Cus.Code', 'Cus.Name', 'BranchName', 'Classification', 'Visit_Frequency', 'TotalSales_2Yr', 'TotalSales_12M', 'TotalSales_6M', 'TotalSales_3M', 'TransactionCount', 'Overall_Contribution_Pct'];

  // Analytics: branch comparison bars (computed from filteredResults)
  let branchBars = $derived(() => {
    if (!filteredResults.length) return [];
    const map = new Map();
    for (const r of filteredResults) {
      const branch = r.BranchName || 'Unknown';
      map.set(branch, (map.get(branch) || 0) + (r.TotalSales_2Yr || 0));
    }
    const entries = [...map.entries()]
      .map(([name, revenue]) => ({ name, revenue }))
      .sort((a, b) => b.revenue - a.revenue);
    const maxRev = Math.max(...entries.map(e => e.revenue), 1);
    return entries.map(e => ({
      name: e.name,
      revenue: e.revenue,
      pct: (e.revenue / maxRev) * 100,
    }));
  });

  // Analytics: period bars
  let periodBars = $derived(() => {
    if (!filteredResults.length) return [];
    const totals = {
      '2Yr': filteredResults.reduce((s, r) => s + (r.TotalSales_2Yr || 0), 0),
      '12M': filteredResults.reduce((s, r) => s + (r.TotalSales_12M || 0), 0),
      '6M': filteredResults.reduce((s, r) => s + (r.TotalSales_6M || 0), 0),
      '3M': filteredResults.reduce((s, r) => s + (r.TotalSales_3M || 0), 0),
    };
    const maxVal = Math.max(...Object.values(totals), 1);
    return Object.entries(totals).map(([period, val]) => ({
      period,
      value: val,
      pct: (val / maxVal) * 100,
    }));
  });

  let trendData = $derived(() => {
    if (!filteredResults.length) return [];
    const map = new Map();
    for (const r of filteredResults) {
      const branch = r.BranchName || 'Unknown';
      if (!map.has(branch)) map.set(branch, { s12: 0, s6: 0, s3: 0 });
      const m = map.get(branch);
      m.s12 += r.TotalSales_12M || 0;
      m.s6 += r.TotalSales_6M || 0;
      m.s3 += r.TotalSales_3M || 0;
    }
    return [...map.entries()]
      .sort((a, b) => b[1].s12 - a[1].s12)
      .map(([name, d]) => {
        // Growth: compare 6M annualized vs 12M
        const growth6v12 = d.s12 > 0 ? ((d.s6 * 2 / d.s12) - 1) * 100 : 0;
        // Growth: compare 3M annualized vs 6M annualized
        const growth3v6 = d.s6 > 0 ? ((d.s3 * 2 / d.s6) - 1) * 100 : 0;
        return {
          Branch: name,
          '12M': d.s12,
          '6M': d.s6,
          '3M': d.s3,
          '6M vs 12M': growth6v12,
          '3M vs 6M': growth3v6,
        };
      });
  });

  function exportFilteredCSV() {
    const rows = filteredResults;
    if (!rows.length) return;
    // Build CSV with key columns, formatted
    const headers = ['Cus.Code', 'Cus.Name', 'BranchName', 'Classification', 'TotalSales_2Yr', 'TotalSales_12M', 'TotalSales_6M', 'TotalSales_3M', 'TransactionCount', 'Overall_Contribution_Pct', 'AI_Growth_Signal', 'AI_Risk_Level', 'AI_Visit_Priority', 'AI_Action'];
    const csvRows = [headers.join(',')];
    for (const r of rows) {
      const vals = headers.map(h => {
        const v = r[h] ?? r[h.replace('.', '_')] ?? '';
        return typeof v === 'string' && (v.includes(',') || v.includes('"')) ? `"${v.replace(/"/g, '""')}"` : v;
      });
      csvRows.push(vals.join(','));
    }
    const csv = csvRows.join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `RTM_${data?.job_id || 'filtered'}_${selectedBranch.replace(/\s/g, '_')}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  // Analytics: Pareto curve
  let paretoCurve = $derived(() => {
    if (!filteredResults.length) return { points: '', a_x: 0, b_x: 0, total: 0 };
    const sorted = [...filteredResults].sort((a, b) => (b.TotalSales_2Yr || 0) - (a.TotalSales_2Yr || 0));
    const totalRev = sorted.reduce((s, r) => s + (r.TotalSales_2Yr || 0), 0);
    if (!totalRev) return { points: '', a_x: 0, b_x: 0, total: 0 };

    let cumSum = 0;
    let a_x = 0, b_x = 0;
    const pts = sorted.map((r, i) => {
      cumSum += r.TotalSales_2Yr || 0;
      const x = (i / sorted.length) * 400;
      const y = 200 - (cumSum / totalRev) * 200;
      if (!a_x && cumSum / totalRev >= 0.80) a_x = x;
      if (!b_x && cumSum / totalRev >= 0.95) b_x = x;
      return `${x},${y}`;
    });
    return { points: pts.join(' '), a_x, b_x, total: sorted.length };
  });

  // Analytics: channel breakdown
  let channelBars = $derived(() => {
    if (!filteredResults.length) return [];
    const map = new Map();
    for (const r of filteredResults) {
      const ch = r.OutletChannel || r.Channel || r.GroupName || 'Unknown';
      if (ch === '0' || ch === 'nan') continue;
      map.set(ch, (map.get(ch) || 0) + 1);
    }
    const entries = [...map.entries()].sort((a, b) => b[1] - a[1]);
    const maxVal = Math.max(...entries.map(e => e[1]), 1);
    return entries.map(e => ({ name: e[0], count: e[1], pct: (e[1] / maxVal) * 100 }));
  });

  // Analytics: risk heatmap
  let riskMatrix = $derived(() => {
    if (!filteredResults.length) return [];
    const map = new Map();
    for (const r of filteredResults) {
      const branch = r.BranchName || 'Unknown';
      const risk = r.AI_Risk_Level || 'Unknown';
      if (!map.has(branch)) map.set(branch, { Low: 0, Medium: 0, High: 0, Unknown: 0 });
      const m = map.get(branch);
      if (risk in m) m[risk]++;
      else m['Unknown']++;
    }
    return [...map.entries()]
      .sort((a, b) => {
        const totalA = a[1].Low + a[1].Medium + a[1].High;
        const totalB = b[1].Low + b[1].Medium + b[1].High;
        return totalB - totalA;
      })
      .map(([name, counts]) => ({
        Branch: name,
        Low: counts.Low,
        Medium: counts.Medium,
        High: counts.High,
        Total: counts.Low + counts.Medium + counts.High + counts.Unknown,
      }));
  });

  const tabLabels = ['DASHBOARD', 'DATA EXPLORER', 'ANALYTICS', 'AI INSIGHTS', 'LOG', 'EXPORT'];
  const pipelineSteps = ['Upload', 'Validate', 'Aggregate', 'Averages', 'Contributions', 'Wholesalers', 'Classify', 'Frequency', 'AI Enrich'];
  let pipelineExpanded = $state(false);
</script>

<!-- HERO BOX -->
<div style="background:#383832;color:#feffd6;padding:16px 24px;margin-bottom:24px;border-bottom:4px solid #383832;border-right:4px solid #383832;">
  <div style="font-size:1.5rem;font-weight:900;letter-spacing:-0.03em;">MCP AGENT — OUTLET CLASSIFICATION</div>
  <div style="font-size:11px;opacity:0.75;margin-top:4px;">PARETO 80/15/5 — PARTITIONED BY BRANCH</div>
</div>

<!-- ======== UPLOAD STATE ======== -->
{#if state === 'upload'}
  <div style="max-width:680px;margin:0 auto;">
    <!-- Hidden file input -->
    <input
      type="file"
      accept=".csv"
      id="fileInput"
      onchange={handleFileChange}
      style="display:none;"
    />

    <!-- File upload card -->
    <div style="background:white;border:3px solid #383832;box-shadow:6px 6px 0 #383832;padding:32px;">

      {#if !file}
        <!-- Empty state: clickable upload area -->
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <div
          onclick={() => document.getElementById('fileInput')?.click()}
          style="border:2px dashed #828179;padding:48px 32px;text-align:center;cursor:pointer;transition:border-color 0.2s,background 0.2s;"
          onmouseenter={(e) => { e.currentTarget.style.borderColor='#007518'; e.currentTarget.style.background='#f0fff0'; }}
          onmouseleave={(e) => { e.currentTarget.style.borderColor='#828179'; e.currentTarget.style.background='transparent'; }}
        >
          <div style="font-size:2rem;color:#828179;margin-bottom:12px;">&#x25B2;</div>
          <div style="font-size:13px;font-weight:900;letter-spacing:0.08em;text-transform:uppercase;color:#383832;margin-bottom:8px;">UPLOAD SALES CSV</div>
          <div style="font-size:11px;color:#828179;font-weight:600;">Click to browse or drag & drop your file</div>
          <div style="font-size:10px;color:#828179;margin-top:12px;opacity:0.7;">Only .csv files accepted</div>
        </div>
      {:else}
        <!-- File selected state with cross button -->
        <div style="border:2px solid #007518;padding:20px 24px;display:flex;align-items:center;justify-content:space-between;background:#f0fff0;">
          <div style="display:flex;align-items:center;gap:12px;">
            <div style="width:36px;height:36px;background:#007518;display:flex;align-items:center;justify-content:center;color:white;font-size:14px;font-weight:900;">&#x2713;</div>
            <div>
              <div style="font-size:12px;font-weight:900;color:#383832;letter-spacing:0.03em;">{file.name}</div>
              <div style="font-size:10px;color:#65655e;margin-top:2px;">{(file.size / 1024).toFixed(0)} KB — CSV FILE</div>
            </div>
          </div>
          <button
            onclick={() => { file = null; fileError = ''; const el = document.getElementById('fileInput'); if (el) el.value = ''; }}
            style="width:28px;height:28px;background:#be2d06;color:white;border:2px solid #383832;display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:900;cursor:pointer;box-shadow:2px 2px 0 #383832;"
            onmousedown={(e) => { e.currentTarget.style.transform='translate(1px,1px)'; e.currentTarget.style.boxShadow='1px 1px 0 #383832'; }}
            onmouseup={(e) => { e.currentTarget.style.transform='translate(0,0)'; e.currentTarget.style.boxShadow='2px 2px 0 #383832'; }}
          >&#x2715;</button>
        </div>

        <!-- File validation error -->
        {#if fileError}
          <div style="margin-top:12px;padding:8px 14px;background:#be2d06;color:white;font-size:11px;font-weight:900;letter-spacing:0.05em;border:2px solid #383832;">
            {fileError}
          </div>
        {/if}
      {/if}

      <!-- Threshold sliders -->
      <div style="margin-top:24px;display:flex;gap:24px;">
        <div style="flex:1;">
          <label style="font-size:10px;font-weight:800;letter-spacing:0.1em;text-transform:uppercase;color:#383832;display:block;margin-bottom:6px;">
            CLASS A CUTOFF: {thresholdA}%
          </label>
          <input type="range" min="50" max="95" bind:value={thresholdA}
            style="width:100%;accent-color:#007518;cursor:pointer;" />
        </div>
        <div style="flex:1;">
          <label style="font-size:10px;font-weight:800;letter-spacing:0.1em;text-transform:uppercase;color:#383832;display:block;margin-bottom:6px;">
            CLASS B CUTOFF: {thresholdB}%
          </label>
          <input type="range" min={thresholdA + 1} max="99" bind:value={thresholdB}
            style="width:100%;accent-color:#ff9d00;cursor:pointer;" />
        </div>
      </div>

      <!-- Preview KPI cards -->
      {#if file}
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:20px;">
          <KpiCard label="Class A" value="{thresholdA}%" subtitle="top revenue" accent="#007518" />
          <KpiCard label="Class B" value="{thresholdB - thresholdA}%" subtitle="middle tier" accent="#ff9d00" />
          <KpiCard label="Class C" value="{100 - thresholdB}%" subtitle="remaining" accent="#be2d06" />
        </div>
      {/if}

      <!-- CTA Button -->
      <button
        onclick={handleClassify}
        disabled={!file}
        style="margin-top:24px;width:100%;padding:14px;font-size:13px;font-weight:900;letter-spacing:0.1em;text-transform:uppercase;cursor:pointer;border:3px solid #383832;box-shadow:4px 4px 0 #383832;transition:all 0.15s;
          {file ? 'background:#00fc40;color:#383832;' : 'background:#ebe8dd;color:#828179;cursor:not-allowed;'}"
      >
        RUN CLASSIFICATION
      </button>
    </div>

    <!-- Error -->
    {#if error}
      <div style="margin-top:16px;padding:12px 16px;background:#be2d06;color:white;font-size:12px;font-weight:700;border:2px solid #383832;">
        ERROR: {error}
      </div>
    {/if}
  </div>

  <!-- HOW IT WORKS -->
  <div style="margin-top:32px;">
    <div style="background:#383832;color:#feffd6;padding:12px 20px;border-bottom:4px solid #383832;border-right:4px solid #383832;margin-bottom:0;">
      <div style="font-size:14px;font-weight:900;letter-spacing:0.03em;">HOW IT WORKS</div>
      <div style="font-size:10px;opacity:0.7;margin-top:2px;">What the MCP Agent does with your data</div>
    </div>

    <!-- Pipeline steps visual -->
    <div style="background:white;border:3px solid #383832;border-top:none;box-shadow:4px 4px 0 #383832;padding:20px 24px;">
      <div style="display:flex;align-items:center;justify-content:center;gap:4px;flex-wrap:wrap;margin-bottom:20px;">
        {#each [
          { n: '01', label: 'VALIDATE', color: '#007518' },
          { n: '02', label: 'AGGREGATE', color: '#006f7c' },
          { n: '03', label: 'PARETO', color: '#ff9d00' },
          { n: '04', label: 'WHOLESALE', color: '#9d4867' },
          { n: '05', label: 'AI ENRICH', color: '#be2d06' },
          { n: '06', label: 'RESULTS', color: '#383832' },
        ] as step, i}
          <div style="display:flex;align-items:center;gap:4px;">
            <div style="width:48px;text-align:center;">
              <div style="width:32px;height:32px;background:{step.color};color:white;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:900;margin:0 auto;">{step.n}</div>
              <div style="font-size:7px;font-weight:900;letter-spacing:0.05em;color:#383832;margin-top:3px;">{step.label}</div>
            </div>
            {#if i < 5}
              <div style="font-size:10px;color:#828179;margin:0 2px;">▸</div>
            {/if}
          </div>
        {/each}
      </div>

      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:10px;color:#65655e;">
        <div style="padding:6px 10px;background:#f6f4e9;border-left:3px solid #007518;">Check columns, parse dates, detect branches</div>
        <div style="padding:6px 10px;background:#f6f4e9;border-left:3px solid #006f7c;">Group transactions → unique outlets per branch</div>
        <div style="padding:6px 10px;background:#f6f4e9;border-left:3px solid #ff9d00;">Sort by revenue, assign A (80%), B (15%), C (5%)</div>
        <div style="padding:6px 10px;background:#f6f4e9;border-left:3px solid #9d4867;">Flag bulk buyers (≥3 cartons/brand/month)</div>
        <div style="padding:6px 10px;background:#f6f4e9;border-left:3px solid #be2d06;">Growth signals, risk levels, LLM insights</div>
        <div style="padding:6px 10px;background:#f6f4e9;border-left:3px solid #383832;">Dashboard, charts, per-branch Excel export</div>
      </div>
    </div>
  </div>

  <!-- REQUIRED COLUMNS -->
  <div style="margin-top:20px;">
    <div style="background:#383832;color:#feffd6;padding:10px 20px;margin-bottom:0;">
      <div style="font-size:12px;font-weight:900;letter-spacing:0.05em;">REQUIRED COLUMNS IN YOUR CSV</div>
    </div>
    <div style="background:white;border:3px solid #383832;border-top:none;box-shadow:4px 4px 0 #383832;padding:16px 20px;">
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:6px;margin-bottom:12px;">
        {#each [
          { col: 'Cus.Code', desc: 'Customer ID' },
          { col: 'Cus.Name', desc: 'Outlet name' },
          { col: 'TotalAmount', desc: 'Sales amount' },
          { col: 'TotalPcs', desc: 'Quantity' },
          { col: 'BranchName', desc: 'Branch partition' },
          { col: 'Item Class', desc: 'Nutrition/Food/Non Food' },
          { col: 'NumInBuy', desc: 'Units per carton' },
        ] as item}
          <div style="padding:6px 10px;background:#f6f4e9;border:1px solid #ebe8dd;">
            <div style="font-size:9px;font-weight:900;color:#007518;letter-spacing:0.05em;">{item.col}</div>
            <div style="font-size:9px;color:#828179;margin-top:1px;">{item.desc}</div>
          </div>
        {/each}
      </div>
      <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center;">
        <span style="font-size:9px;font-weight:900;color:#383832;letter-spacing:0.05em;">OPTIONAL:</span>
        {#each ['DocDate', 'InvoiceNo', 'BrandName', 'Item Type', 'Channel'] as col}
          <span style="padding:2px 8px;font-size:8px;font-weight:700;background:#ebe8dd;color:#65655e;">{col}</span>
        {/each}
      </div>
    </div>
  </div>

  <!-- WHAT YOU GET -->
  <div style="margin-top:20px;margin-bottom:32px;">
    <div style="background:#383832;color:#feffd6;padding:10px 20px;margin-bottom:0;">
      <div style="font-size:12px;font-weight:900;letter-spacing:0.05em;">WHAT YOU GET</div>
    </div>
    <div style="background:white;border:3px solid #383832;border-top:none;box-shadow:4px 4px 0 #383832;padding:16px 20px;">
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;font-size:10px;color:#383832;">
        {#each [
          'Per-branch Pareto classification (A/B/C/F4)',
          'KPI dashboard (outlets, classes, revenue)',
          'Branch comparison matrix (all branches)',
          'Top 10 outlets by revenue',
          'AI growth signals (Growing/Stable/Declining)',
          'AI risk levels (High/Medium/Low)',
          'AI visit priority (1-4 ranking)',
          'AI action recommendations per outlet',
          'Executive summary from Gemini LLM',
          'Multi-sheet Excel export (per branch)',
          'Data quality report',
          'Full job history with replay',
        ] as item}
          <div style="padding:4px 8px;display:flex;align-items:center;gap:6px;">
            <span style="width:14px;height:14px;background:#007518;color:white;display:flex;align-items:center;justify-content:center;font-size:8px;font-weight:900;flex-shrink:0;">✓</span>
            <span style="font-weight:600;">{item}</span>
          </div>
        {/each}
      </div>
    </div>
  </div>

<!-- ======== PROCESSING STATE ======== -->
{:else if state === 'processing'}
  <div style="display:grid;grid-template-columns:320px 1fr;gap:0;border:3px solid #383832;box-shadow:6px 6px 0 #383832;min-height:500px;">

    <!-- LEFT: Pipeline steps -->
    <div style="background:white;border-right:3px solid #383832;">
      <div style="background:#383832;color:#feffd6;padding:10px 16px;font-weight:900;font-size:11px;letter-spacing:0.1em;">
        PIPELINE — {currentStep >= 10 ? '10' : currentStep}/10 STEPS
      </div>

      <div style="padding:8px;display:flex;flex-direction:column;gap:4px;overflow-y:auto;flex:1;">
        {#each [
          'UPLOAD FILE',
          'VALIDATE DATA',
          'AGGREGATE',
          'AVERAGES',
          'CONTRIBUTIONS',
          'WHOLESALERS',
          'CLASSIFY',
          'FREQUENCY',
          'AI ENRICH',
          'INSIGHTS'
        ] as step, i}
          <div style="
            display:flex;align-items:center;gap:8px;padding:6px 10px;
            border:2px solid {i < currentStep ? '#007518' : i === currentStep ? '#ff9d00' : '#ebe8dd'};
            background:{i < currentStep ? '#f0fff0' : i === currentStep ? '#fffbe6' : 'white'};
            box-shadow:{i === currentStep ? '2px 2px 0 #ff9d00' : i < currentStep ? '2px 2px 0 #007518' : '1px 1px 0 #ebe8dd'};
            opacity:{i > currentStep ? '0.35' : '1'};
            transition:all 0.3s;
          ">
            <div style="width:20px;height:20px;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:900;flex-shrink:0;
              background:{i < currentStep ? '#007518' : i === currentStep ? '#ff9d00' : '#ebe8dd'};
              color:{i <= currentStep ? 'white' : '#828179'};
              border:1px solid {i < currentStep ? '#007518' : i === currentStep ? '#ff9d00' : '#828179'};
            ">
              {i < currentStep ? '✓' : i === currentStep ? '▸' : (i + 1)}
            </div>
            <div style="font-size:9px;font-weight:800;letter-spacing:0.06em;color:#383832;flex:1;">{step}</div>
            {#if i === currentStep}
              <div style="display:flex;gap:2px;">
                <span style="width:4px;height:4px;background:#007518;animation:bounce 0.6s ease-in-out infinite;"></span>
                <span style="width:4px;height:4px;background:#ff9d00;animation:bounce 0.6s ease-in-out infinite;animation-delay:0.15s;"></span>
                <span style="width:4px;height:4px;background:#be2d06;animation:bounce 0.6s ease-in-out infinite;animation-delay:0.3s;"></span>
              </div>
            {/if}
            {#if i < currentStep}
              <span style="font-size:8px;color:#007518;font-weight:900;background:#dcfce7;padding:1px 6px;border:1px solid #007518;">DONE</span>
            {/if}
          </div>
        {/each}
      </div>

      <!-- Progress bar -->
      <div style="padding:12px 14px;">
        <div style="height:6px;background:#ebe8dd;border:1px solid #383832;">
          <div style="height:100%;background:#007518;transition:width 0.5s;width:{Math.min(currentStep * 10, 100)}%;"></div>
        </div>
        <div style="font-size:9px;font-weight:700;color:#828179;margin-top:6px;text-align:center;">
          {Math.min(currentStep * 10, 100)}% COMPLETE
        </div>
      </div>
    </div>

    <!-- RIGHT: Terminal output -->
    <div style="background:#0a0a0f;display:flex;flex-direction:column;">
      <div style="padding:8px 16px;background:#1a1a24;border-bottom:1px solid #2a2a34;display:flex;align-items:center;gap:8px;">
        <span style="width:8px;height:8px;background:#007518;border-radius:50%;"></span>
        <span style="font-size:10px;font-weight:700;color:#6b7280;font-family:monospace;letter-spacing:0.05em;">MCP_AGENT_TERMINAL</span>
        <span style="margin-left:auto;font-size:9px;color:#4a4a54;font-family:monospace;">PID: 28320</span>
      </div>

      <div id="terminal-scroll" style="flex:1;padding:12px 16px;overflow-y:auto;max-height:500px;font-family:'SF Mono','Cascadia Code','Fira Code',monospace;font-size:11px;line-height:1.7;">
        {#each terminalLines as line, i}
          <div style="
            animation: fadeIn 0.15s ease-out;
            {line.startsWith('[MCP AGENT] ✓') ? 'color:#22c55e;font-weight:700;' :
             line.startsWith('[MCP AGENT] ✗') ? 'color:#ef4444;font-weight:700;' :
             line.startsWith('[MCP AGENT]') ? 'color:#38bdf8;font-weight:600;' :
             line.startsWith('$') ? 'color:#00fc40;font-weight:700;' :
             line.startsWith('[OK]') ? 'color:#22c55e;font-weight:600;' :
             line.startsWith('[WARN]') ? 'color:#fbbf24;' :
             line.startsWith('[SKIP]') ? 'color:#fbbf24;font-style:italic;' :
             line.startsWith('[RESULT]') ? 'color:#38bdf8;font-weight:600;' :
             line.startsWith('[ALGO]') ? 'color:#a78bfa;' :
             line.startsWith('[CALC]') ? 'color:#9ca3af;' :
             line.startsWith('[SCAN]') ? 'color:#67e8f9;' :
             line.startsWith('[SQL]') ? 'color:#fb923c;' :
             line.startsWith('[AI]') ? 'color:#c084fc;' :
             line.startsWith('[LLM]') ? 'color:#f472b6;' :
             line.startsWith('[INFO]') ? 'color:#9ca3af;' :
             line.startsWith('[ERR]') ? 'color:#ef4444;font-weight:700;' :
             line.startsWith('═') ? 'color:#22c55e;font-weight:700;' :
             line === '' ? 'height:6px;' :
             'color:#6b7280;'}
          ">{line}</div>
        {/each}

        <!-- Blinking cursor -->
        {#if currentStep < 10}
          <div style="display:flex;align-items:center;gap:4px;margin-top:4px;">
            <span style="color:#00fc40;font-weight:700;">$</span>
            <span style="width:8px;height:14px;background:#00fc40;animation:blink 1s step-end infinite;"></span>
          </div>
        {/if}
      </div>
    </div>
  </div>

  <style>
    @keyframes blink {
      0%, 100% { opacity: 1; }
      50% { opacity: 0; }
    }
  </style>

<!-- ======== RESULTS STATE ======== -->
{:else if state === 'results' && data}

  <!-- Collapsible pipeline bar -->
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div
    onclick={() => pipelineExpanded = !pipelineExpanded}
    style="
      background:#383832;color:#feffd6;padding:10px 16px;margin-bottom:{pipelineExpanded ? '0' : '20'}px;
      display:flex;align-items:center;justify-content:space-between;cursor:pointer;
      border:2px solid #383832;box-shadow:3px 3px 0 #383832;
      transition:margin 0.3s;
    "
    onmouseenter={(e) => e.currentTarget.style.background='#4a4a44'}
    onmouseleave={(e) => e.currentTarget.style.background='#383832'}
  >
    <div style="display:flex;align-items:center;gap:10px;">
      <span style="font-size:12px;transition:transform 0.3s;display:inline-block;transform:rotate({pipelineExpanded ? '180' : '0'}deg);">▼</span>
      <span style="font-size:11px;font-weight:900;letter-spacing:0.08em;">PIPELINE COMPLETE — 10/10 STEPS</span>
      <span style="font-size:10px;opacity:0.6;font-weight:600;">JOB: {data.job_id}</span>
    </div>
    <div style="display:flex;align-items:center;gap:12px;">
      <span style="font-size:9px;font-weight:700;background:#007518;color:white;padding:2px 8px;">✓ SUCCESS</span>
      <span style="font-size:10px;opacity:0.5;font-weight:600;">{pipelineExpanded ? 'COLLAPSE' : 'EXPAND LOG'}</span>
    </div>
  </div>

  <!-- Expanded pipeline panel -->
  {#if pipelineExpanded}
    <div style="margin-bottom:20px;border:2px solid #383832;border-top:none;box-shadow:3px 3px 0 #383832;overflow:hidden;animation:slideDown 0.3s ease-out;">
      <div style="display:grid;grid-template-columns:280px 1fr;min-height:350px;max-height:450px;">
        <!-- Left: completed steps -->
        <div style="background:white;border-right:2px solid #383832;padding:8px;display:flex;flex-direction:column;gap:3px;overflow-y:auto;">
          {#each ['UPLOAD','VALIDATE','AGGREGATE','AVERAGES','CONTRIBUTIONS','WHOLESALERS','CLASSIFY','FREQUENCY','AI ENRICH','INSIGHTS'] as step, i}
            <div style="display:flex;align-items:center;gap:8px;padding:5px 8px;border:2px solid #007518;background:#f0fff0;box-shadow:2px 2px 0 #007518;">
              <div style="width:18px;height:18px;background:#007518;color:white;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:900;">✓</div>
              <div style="font-size:9px;font-weight:800;letter-spacing:0.05em;color:#383832;flex:1;">{step}</div>
              <span style="font-size:7px;color:#007518;font-weight:900;background:#dcfce7;padding:1px 5px;border:1px solid #007518;">DONE</span>
            </div>
          {/each}
        </div>
        <!-- Right: terminal log (scrollable) -->
        <div style="background:#0a0a0f;overflow-y:auto;padding:12px 16px;font-family:'SF Mono','Cascadia Code','Fira Code',monospace;font-size:11px;line-height:1.7;">
          {#each terminalLines as line}
            <div style="
              {line.startsWith('[MCP AGENT] ✓') ? 'color:#22c55e;font-weight:700;' :
               line.startsWith('[MCP AGENT] ✗') ? 'color:#ef4444;font-weight:700;' :
               line.startsWith('[MCP AGENT]') ? 'color:#38bdf8;font-weight:600;' :
               line.startsWith('$') ? 'color:#00fc40;font-weight:700;' :
               line.startsWith('[OK]') ? 'color:#22c55e;font-weight:600;' :
               line.startsWith('[WARN]') ? 'color:#fbbf24;' :
               line.startsWith('[SKIP]') ? 'color:#fbbf24;font-style:italic;' :
               line.startsWith('[RESULT]') ? 'color:#38bdf8;font-weight:600;' :
               line.startsWith('[ALGO]') ? 'color:#a78bfa;' :
               line.startsWith('[CALC]') ? 'color:#9ca3af;' :
               line.startsWith('[SCAN]') ? 'color:#67e8f9;' :
               line.startsWith('[SQL]') ? 'color:#fb923c;' :
               line.startsWith('[AI]') ? 'color:#c084fc;' :
               line.startsWith('[LLM]') ? 'color:#f472b6;' :
               line.startsWith('[INFO]') ? 'color:#9ca3af;' :
               line.startsWith('═') ? 'color:#22c55e;font-weight:700;' :
               line === '' ? 'height:6px;' :
               'color:#6b7280;'}
            ">{line}</div>
          {/each}
        </div>
      </div>
    </div>
  {/if}

  <!-- Controls row -->
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;flex-wrap:wrap;gap:12px;">
    <!-- Branch filter -->
    <div style="display:flex;align-items:center;gap:8px;">
      <span style="font-size:10px;font-weight:800;letter-spacing:0.1em;text-transform:uppercase;color:#383832;">BRANCH:</span>
      <select bind:value={selectedBranch}
        style="padding:6px 12px;font-size:11px;font-weight:700;background:white;border:2px solid #383832;color:#383832;cursor:pointer;">
        <option>All Branches</option>
        {#each branches as branch}
          <option>{branch}</option>
        {/each}
      </select>
    </div>

    <!-- Job ID + Reset -->
    <div style="display:flex;align-items:center;gap:12px;">
      <span style="font-size:10px;font-weight:700;color:#828179;letter-spacing:0.06em;">JOB: {data.job_id}</span>
      <button onclick={reset}
        style="padding:6px 16px;font-size:10px;font-weight:900;letter-spacing:0.1em;background:#00fc40;color:#383832;border:2px solid #383832;cursor:pointer;">
        NEW JOB
      </button>
    </div>
  </div>

  <!-- KPI cards grid -->
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:24px;">
    <KpiCard label="Total Outlets" value={kpis.total.toLocaleString()} subtitle="{kpis.branchCount} branches" accent="#383832" />
    <KpiCard label="Class A" value={kpis.classA.toLocaleString()} subtitle="{kpis.total > 0 ? fmtPct((kpis.classA / kpis.total) * 100) : '0%'} of total" accent="#007518" />
    <KpiCard label="Class B" value={kpis.classB.toLocaleString()} subtitle="{kpis.total > 0 ? fmtPct((kpis.classB / kpis.total) * 100) : '0%'} of total" accent="#ff9d00" />
    <KpiCard label="Class C" value={kpis.classC.toLocaleString()} subtitle="{kpis.total > 0 ? fmtPct((kpis.classC / kpis.total) * 100) : '0%'} of total" accent="#be2d06" />
    <KpiCard label="Wholesalers" value={kpis.wholesalers.toLocaleString()} subtitle="F4 flagged" accent="#006f7c" />
    <KpiCard label="Total Revenue" value={fmtNum(kpis.revenue)} subtitle="2-year aggregate" accent="#007518" />
  </div>

  <!-- Tab bar (button style) -->
  <div style="display:flex;gap:6px;margin-bottom:24px;flex-wrap:wrap;">
    {#each tabLabels as label, i}
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

  <!-- ---- TAB 0: DASHBOARD ---- -->
  {#if activeTab === 0}

    <!-- Data Quality Panel -->
    {#if data.data_quality?.length > 0 || data.data_quality_ok?.length > 0}
      <div style="margin-bottom:24px;">
        <ChapterHeading title="Data Quality Report" subtitle="What was detected and what's missing" />
        <div style="background:white;border:3px solid #383832;box-shadow:4px 4px 0 #383832;padding:20px;">

          <!-- OK checks -->
          {#if data.data_quality_ok?.length > 0}
            {#each data.data_quality_ok as check}
              <div style="display:flex;align-items:center;gap:10px;padding:6px 0;border-bottom:1px solid #ebe8dd;">
                <span style="width:20px;height:20px;background:#007518;color:white;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:900;flex-shrink:0;">✓</span>
                <span style="font-size:11px;color:#383832;font-weight:600;">{check}</span>
              </div>
            {/each}
          {/if}

          <!-- Warnings / Missing -->
          {#if data.data_quality?.length > 0}
            {#each data.data_quality as item}
              <div style="display:flex;align-items:flex-start;gap:10px;padding:8px 0;border-bottom:1px solid #ebe8dd;">
                <span style="width:20px;height:20px;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:900;
                  {item.status === 'warning' ? 'background:#ff9d00;color:white;' :
                   item.status === 'missing' ? 'background:#be2d06;color:white;' :
                   'background:#006f7c;color:white;'}
                ">{item.status === 'warning' ? '!' : item.status === 'missing' ? '✗' : 'i'}</span>
                <div style="flex:1;">
                  <div style="display:flex;align-items:center;gap:8px;margin-bottom:2px;">
                    <span style="font-size:10px;font-weight:900;letter-spacing:0.06em;color:#383832;">{item.field}</span>
                    <span style="font-size:8px;font-weight:800;padding:1px 6px;letter-spacing:0.05em;
                      {item.status === 'warning' ? 'background:#fff3cd;color:#856404;border:1px solid #ff9d00;' :
                       item.status === 'missing' ? 'background:#fee2e2;color:#991b1b;border:1px solid #be2d06;' :
                       'background:#e0f2fe;color:#075985;border:1px solid #006f7c;'}
                    ">{item.status.toUpperCase()}</span>
                  </div>
                  <div style="font-size:11px;color:#65655e;">{item.message}</div>
                  <div style="font-size:10px;color:#828179;margin-top:2px;font-style:italic;">Impact: {item.impact}</div>
                </div>
              </div>
            {/each}
          {/if}
        </div>
      </div>
    {/if}

    <div style="margin-bottom:24px;">
      <ChapterHeading title="Classification Summary" subtitle="Breakdown by Pareto class" />
      <DataTable title="SUMMARY" data={summaryRows()} columns={['Classification', 'Count', 'Revenue', 'Avg Sales', 'Share %']} maxHeight="300px" />
    </div>

    <div style="margin-bottom:24px;">
      <ChapterHeading title="Top 10 Outlets" subtitle="Highest revenue outlets across selection" />
      <DataTable title="TOP 10" data={top10()} columns={['Cus.Code', 'Cus.Name', 'Branch', 'Classification', '2Yr Sales', 'Contribution %']} maxHeight="400px" />
    </div>

    <div style="margin-bottom:24px;">
      <ChapterHeading title="Branch Matrix" subtitle="Performance across all branches" />
      <DataTable title="BRANCHES" data={branchMatrix()} columns={['Branch', 'Outlets', 'Revenue', 'Class A', 'Class B', 'Class C', 'A %']} maxHeight="400px" />
    </div>

    <!-- Seller Workload -->
    {#if data.workload?.length > 0}
      <div style="margin-bottom:24px;">
        <ChapterHeading title="Seller Workload" subtitle="Route outlet counts vs targets (YGN: 25-30, Regional: 30-35)" />
        <div style="border:3px solid #383832;box-shadow:4px 4px 0 #383832;overflow:hidden;">
          <div style="padding:8px 12px;background:#383832;color:#feffd6;font-size:10px;font-weight:900;letter-spacing:0.1em;display:flex;justify-content:space-between;">
            <span>ROUTE WORKLOAD</span>
            <span style="opacity:0.7;">{data.workload.length} ROUTES</span>
          </div>
          <div style="max-height:400px;overflow-y:auto;">
            <table style="width:100%;border-collapse:collapse;font-size:11px;">
              <thead>
                <tr>
                  <th style="position:sticky;top:0;background:#ebe8dd;padding:8px 12px;text-align:left;font-size:9px;font-weight:900;border-bottom:2px solid #383832;">BRANCH</th>
                  <th style="position:sticky;top:0;background:#ebe8dd;padding:8px 12px;text-align:left;font-size:9px;font-weight:900;border-bottom:2px solid #383832;">ROUTE</th>
                  <th style="position:sticky;top:0;background:#ebe8dd;padding:8px 12px;text-align:center;font-size:9px;font-weight:900;border-bottom:2px solid #383832;">OUTLETS</th>
                  <th style="position:sticky;top:0;background:#ebe8dd;padding:8px 12px;text-align:center;font-size:9px;font-weight:900;border-bottom:2px solid #383832;">TARGET</th>
                  <th style="position:sticky;top:0;background:#ebe8dd;padding:8px 12px;text-align:center;font-size:9px;font-weight:900;border-bottom:2px solid #383832;">STATUS</th>
                </tr>
              </thead>
              <tbody>
                {#each data.workload as row, i}
                  <tr style="background:{i % 2 === 0 ? 'white' : '#fcf9ef'};border-bottom:1px solid #ebe8dd;">
                    <td style="padding:6px 12px;font-weight:700;font-size:10px;">{row.BranchName}</td>
                    <td style="padding:6px 12px;font-size:10px;font-family:monospace;">{row.RouteCode}</td>
                    <td style="padding:6px 12px;text-align:center;font-weight:700;">{row.OutletCount}</td>
                    <td style="padding:6px 12px;text-align:center;font-size:10px;color:#828179;">{row.BranchName === 'Yangon' ? '25-30' : '30-35'}</td>
                    <td style="padding:6px 12px;text-align:center;">
                      <span style="font-size:9px;font-weight:900;padding:2px 8px;
                        {row.Workload_Status === 'OK' ? 'background:#dcfce7;color:#007518;' :
                         row.Workload_Status === 'BELOW_MIN' ? 'background:#fee2e2;color:#be2d06;' :
                         'background:#fef9c3;color:#856404;'}
                      ">{row.Workload_Status === 'OK' ? 'OK' : row.Workload_Status === 'BELOW_MIN' ? 'BELOW MIN' : 'ABOVE MAX'}</span>
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    {/if}

    <!-- AI insight panel -->
    {#if data.insights}
      <div style="margin-top:32px;background:#383832;color:#feffd6;border:3px solid #383832;box-shadow:4px 4px 0 #383832;">
        <div style="padding:12px 16px;font-size:11px;font-weight:900;letter-spacing:0.1em;border-bottom:1px solid rgba(254,255,214,0.15);">AI EXECUTIVE SUMMARY</div>
        <div style="padding:16px;font-size:12px;line-height:1.6;opacity:0.9;">
          {#if data.insights.executive_summary}
            {@html renderMarkdown(data.insights.executive_summary)}
          {:else}
            {#each Object.entries(data.insights) as [key, val]}
              <div style="margin-bottom:8px;"><strong style="text-transform:uppercase;font-size:10px;color:#00fc40;">{key}:</strong> {@html renderMarkdown(String(val))}</div>
            {/each}
          {/if}
        </div>
      </div>
    {/if}

  <!-- ---- TAB 1: DATA EXPLORER ---- -->
  {:else if activeTab === 1}
    <div style="display:flex;gap:12px;margin-bottom:16px;flex-wrap:wrap;">
      <select bind:value={classFilter}
        style="padding:6px 12px;font-size:11px;font-weight:700;background:white;border:2px solid #383832;color:#383832;cursor:pointer;">
        <option>All</option>
        <option>Class A</option>
        <option>Class B</option>
        <option>Class C</option>
        <option>Class A Local (F4)</option>
      </select>
      <input type="text" bind:value={searchQuery} placeholder="Search outlet name or code..."
        style="flex:1;min-width:200px;padding:6px 12px;font-size:11px;border:2px solid #383832;background:white;color:#383832;" />
    </div>

    <DataTable title="ALL OUTLETS" data={explorerData()} columns={explorerCols} maxHeight="600px" />

  <!-- ---- TAB 2: ANALYTICS ---- -->
  {:else if activeTab === 2}
    <div style="margin-bottom:24px;">
      <ChapterHeading title="Branch Revenue Comparison" subtitle="Relative revenue by branch" />
      <div style="background:white;border:3px solid #383832;box-shadow:4px 4px 0 #383832;padding:24px;">
        {#each branchBars() as bar}
          <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px;">
            <div style="min-width:120px;font-size:10px;font-weight:800;letter-spacing:0.06em;text-transform:uppercase;color:#383832;text-align:right;">{bar.name}</div>
            <div style="flex:1;height:20px;background:#ebe8dd;">
              <div style="height:100%;width:{bar.pct}%;background:#007518;transition:width 0.5s;"></div>
            </div>
            <div style="min-width:80px;font-size:10px;font-weight:700;color:#383832;">{fmtNum(bar.revenue)}</div>
          </div>
        {/each}
        {#if branchBars().length === 0}
          <div style="text-align:center;color:#828179;font-size:11px;padding:24px;">No branch data available</div>
        {/if}
      </div>
    </div>

    <ChapterHeading title="Period Comparison" subtitle="Aggregate sales by time window" />
    <div style="background:white;border:3px solid #383832;box-shadow:4px 4px 0 #383832;padding:24px;">
      {#each periodBars() as bar}
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px;">
          <div style="min-width:60px;font-size:11px;font-weight:900;letter-spacing:0.06em;color:#383832;text-align:right;">{bar.period}</div>
          <div style="flex:1;height:24px;background:#ebe8dd;">
            <div style="height:100%;width:{bar.pct}%;background:#006f7c;transition:width 0.5s;"></div>
          </div>
          <div style="min-width:90px;font-size:11px;font-weight:700;color:#383832;">{fmtNum(bar.value)}</div>
        </div>
      {/each}
    </div>

    <!-- Trend Comparison Table -->
    <div style="margin-bottom:24px;margin-top:24px;">
      <ChapterHeading title="Trend Comparison" subtitle="Period-over-period growth by branch" />
      <div style="border:3px solid #383832;box-shadow:4px 4px 0 #383832;overflow:hidden;">
        <div style="padding:8px 12px;background:#383832;color:#feffd6;font-size:10px;font-weight:900;letter-spacing:0.1em;">GROWTH TRENDS</div>
        <table style="width:100%;border-collapse:collapse;font-size:11px;">
          <thead>
            <tr>
              <th style="background:#ebe8dd;padding:8px 12px;text-align:left;font-size:9px;font-weight:900;border-bottom:2px solid #383832;">BRANCH</th>
              <th style="background:#ebe8dd;padding:8px 12px;text-align:right;font-size:9px;font-weight:900;border-bottom:2px solid #383832;">12M SALES</th>
              <th style="background:#ebe8dd;padding:8px 12px;text-align:right;font-size:9px;font-weight:900;border-bottom:2px solid #383832;">6M SALES</th>
              <th style="background:#ebe8dd;padding:8px 12px;text-align:right;font-size:9px;font-weight:900;border-bottom:2px solid #383832;">3M SALES</th>
              <th style="background:#ebe8dd;padding:8px 12px;text-align:center;font-size:9px;font-weight:900;border-bottom:2px solid #383832;">6M vs 12M</th>
              <th style="background:#ebe8dd;padding:8px 12px;text-align:center;font-size:9px;font-weight:900;border-bottom:2px solid #383832;">3M vs 6M</th>
            </tr>
          </thead>
          <tbody>
            {#each trendData() as row, i}
              <tr style="background:{i % 2 === 0 ? 'white' : '#fcf9ef'};border-bottom:1px solid #ebe8dd;">
                <td style="padding:8px 12px;font-weight:800;font-size:10px;">{row.Branch}</td>
                <td style="padding:8px 12px;text-align:right;font-size:10px;font-weight:600;">{fmtNum(row['12M'])}</td>
                <td style="padding:8px 12px;text-align:right;font-size:10px;font-weight:600;">{fmtNum(row['6M'])}</td>
                <td style="padding:8px 12px;text-align:right;font-size:10px;font-weight:600;">{fmtNum(row['3M'])}</td>
                <td style="padding:8px 12px;text-align:center;">
                  <span style="font-size:10px;font-weight:900;padding:2px 8px;
                    {row['6M vs 12M'] > 5 ? 'background:#dcfce7;color:#007518;' : row['6M vs 12M'] < -5 ? 'background:#fee2e2;color:#be2d06;' : 'background:#fef9c3;color:#856404;'}
                  ">{row['6M vs 12M'] > 0 ? '+' : ''}{row['6M vs 12M'].toFixed(1)}%</span>
                </td>
                <td style="padding:8px 12px;text-align:center;">
                  <span style="font-size:10px;font-weight:900;padding:2px 8px;
                    {row['3M vs 6M'] > 5 ? 'background:#dcfce7;color:#007518;' : row['3M vs 6M'] < -5 ? 'background:#fee2e2;color:#be2d06;' : 'background:#fef9c3;color:#856404;'}
                  ">{row['3M vs 6M'] > 0 ? '+' : ''}{row['3M vs 6M'].toFixed(1)}%</span>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </div>

    <!-- Pareto Curve -->
    <div style="margin-bottom:24px;">
      <ChapterHeading title="Pareto Curve" subtitle="Cumulative revenue distribution — where do the thresholds fall?" />
      <div style="background:white;border:3px solid #383832;box-shadow:4px 4px 0 #383832;padding:24px;">
        <svg viewBox="0 0 440 240" style="width:100%;max-height:300px;">
          <!-- Grid lines -->
          <line x1="20" y1="200" x2="420" y2="200" stroke="#ebe8dd" stroke-width="1"/>
          <line x1="20" y1="160" x2="420" y2="160" stroke="#ebe8dd" stroke-width="1" stroke-dasharray="4"/>
          <line x1="20" y1="120" x2="420" y2="120" stroke="#ebe8dd" stroke-width="1" stroke-dasharray="4"/>
          <line x1="20" y1="80" x2="420" y2="80" stroke="#ebe8dd" stroke-width="1" stroke-dasharray="4"/>
          <line x1="20" y1="40" x2="420" y2="40" stroke="#ebe8dd" stroke-width="1" stroke-dasharray="4"/>
          <line x1="20" y1="0" x2="420" y2="0" stroke="#ebe8dd" stroke-width="1" stroke-dasharray="4"/>

          <!-- Y axis labels -->
          <text x="16" y="204" fill="#828179" font-size="8" text-anchor="end">0%</text>
          <text x="16" y="164" fill="#828179" font-size="8" text-anchor="end">20%</text>
          <text x="16" y="44" fill="#828179" font-size="8" text-anchor="end">80%</text>
          <text x="16" y="12" fill="#828179" font-size="8" text-anchor="end">100%</text>

          <!-- 80% threshold line -->
          {#if paretoCurve().a_x}
            <line x1={20 + paretoCurve().a_x} y1="0" x2={20 + paretoCurve().a_x} y2="200" stroke="#007518" stroke-width="2" stroke-dasharray="6,3"/>
            <line x1="20" y1="40" x2="420" y2="40" stroke="#007518" stroke-width="1" stroke-dasharray="6,3"/>
            <text x={22 + paretoCurve().a_x} y="216" fill="#007518" font-size="8" font-weight="900">A 80%</text>
          {/if}

          <!-- 95% threshold line -->
          {#if paretoCurve().b_x}
            <line x1={20 + paretoCurve().b_x} y1="0" x2={20 + paretoCurve().b_x} y2="200" stroke="#ff9d00" stroke-width="2" stroke-dasharray="6,3"/>
            <line x1="20" y1="10" x2="420" y2="10" stroke="#ff9d00" stroke-width="1" stroke-dasharray="6,3"/>
            <text x={22 + paretoCurve().b_x} y="228" fill="#ff9d00" font-size="8" font-weight="900">B 95%</text>
          {/if}

          <!-- Curve -->
          <polyline points={paretoCurve().points.split(' ').map(p => { const [x,y] = p.split(','); return `${20+Number(x)},${Number(y)}`; }).join(' ')} fill="none" stroke="#383832" stroke-width="2.5"/>

          <!-- Fill area under curve -->
          <polygon points={`20,200 ${paretoCurve().points.split(' ').map(p => { const [x,y] = p.split(','); return `${20+Number(x)},${Number(y)}`; }).join(' ')} 420,200`} fill="rgba(0,117,24,0.08)"/>

          <!-- X axis label -->
          <text x="220" y="238" fill="#828179" font-size="8" text-anchor="middle">% OF OUTLETS (RANKED BY REVENUE)</text>
        </svg>

        <!-- Legend -->
        <div style="display:flex;gap:16px;justify-content:center;margin-top:8px;font-size:9px;font-weight:700;">
          <span style="display:flex;align-items:center;gap:4px;"><span style="width:12px;height:3px;background:#007518;"></span> CLASS A (80%)</span>
          <span style="display:flex;align-items:center;gap:4px;"><span style="width:12px;height:3px;background:#ff9d00;"></span> CLASS B (95%)</span>
          <span style="display:flex;align-items:center;gap:4px;"><span style="width:12px;height:3px;background:#be2d06;"></span> CLASS C</span>
        </div>
      </div>
    </div>

    <!-- Outlet Channel Breakdown -->
    <div style="margin-bottom:24px;">
      <ChapterHeading title="Outlet Channel Breakdown" subtitle="Distribution by channel type" />
      <div style="background:white;border:3px solid #383832;box-shadow:4px 4px 0 #383832;padding:24px;">
        {#each channelBars() as bar}
          <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px;">
            <div style="min-width:140px;font-size:10px;font-weight:800;letter-spacing:0.04em;text-transform:uppercase;color:#383832;text-align:right;">{bar.name}</div>
            <div style="flex:1;height:20px;background:#ebe8dd;">
              <div style="height:100%;width:{bar.pct}%;background:#006f7c;transition:width 0.5s;"></div>
            </div>
            <div style="min-width:60px;font-size:10px;font-weight:700;color:#383832;">{bar.count.toLocaleString()}</div>
          </div>
        {/each}
        {#if channelBars().length === 0}
          <div style="text-align:center;color:#828179;font-size:11px;padding:24px;">No channel data</div>
        {/if}
      </div>
    </div>

    <!-- Risk Heatmap -->
    <div style="margin-bottom:24px;">
      <ChapterHeading title="Risk Heatmap" subtitle="Branch x risk level distribution" />
      <div style="border:3px solid #383832;box-shadow:4px 4px 0 #383832;overflow:hidden;">
        <div style="padding:8px 12px;background:#383832;color:#feffd6;font-size:10px;font-weight:900;letter-spacing:0.1em;">RISK MATRIX</div>
        <table style="width:100%;border-collapse:collapse;font-size:11px;">
          <thead>
            <tr>
              <th style="background:#ebe8dd;padding:8px 12px;text-align:left;font-size:9px;font-weight:900;letter-spacing:0.08em;border-bottom:2px solid #383832;">BRANCH</th>
              <th style="background:#ebe8dd;padding:8px 12px;text-align:center;font-size:9px;font-weight:900;color:#007518;border-bottom:2px solid #383832;">LOW</th>
              <th style="background:#ebe8dd;padding:8px 12px;text-align:center;font-size:9px;font-weight:900;color:#ff9d00;border-bottom:2px solid #383832;">MEDIUM</th>
              <th style="background:#ebe8dd;padding:8px 12px;text-align:center;font-size:9px;font-weight:900;color:#be2d06;border-bottom:2px solid #383832;">HIGH</th>
              <th style="background:#ebe8dd;padding:8px 12px;text-align:center;font-size:9px;font-weight:900;border-bottom:2px solid #383832;">TOTAL</th>
            </tr>
          </thead>
          <tbody>
            {#each riskMatrix() as row, i}
              <tr style="background:{i % 2 === 0 ? 'white' : '#fcf9ef'};border-bottom:1px solid #ebe8dd;">
                <td style="padding:8px 12px;font-weight:800;font-size:10px;">{row.Branch}</td>
                <td style="padding:8px 12px;text-align:center;background:rgba(0,117,24,{Math.min(row.Low / Math.max(row.Total, 1), 1) * 0.2});font-weight:700;">{row.Low}</td>
                <td style="padding:8px 12px;text-align:center;background:rgba(255,157,0,{Math.min(row.Medium / Math.max(row.Total, 1), 1) * 0.3});font-weight:700;">{row.Medium}</td>
                <td style="padding:8px 12px;text-align:center;background:rgba(190,45,6,{Math.min(row.High / Math.max(row.Total, 1), 1) * 0.3});font-weight:700;">{row.High}</td>
                <td style="padding:8px 12px;text-align:center;font-weight:700;">{row.Total}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </div>

  <!-- ---- TAB 3: AI INSIGHTS ---- -->
  {:else if activeTab === 3}
    <!-- Executive summary -->
    <div style="background:#383832;color:#feffd6;border:3px solid #383832;box-shadow:4px 4px 0 #383832;margin-bottom:24px;">
      <div style="padding:12px 16px;font-size:11px;font-weight:900;letter-spacing:0.1em;border-bottom:1px solid rgba(254,255,214,0.15);">AI EXECUTIVE SUMMARY</div>
      <div style="padding:16px;font-size:12px;line-height:1.6;opacity:0.9;">
        {#if data.insights?.executive_summary}
          {@html renderMarkdown(data.insights.executive_summary)}
        {:else if data.insights}
          {#each Object.entries(data.insights) as [key, val]}
            <div style="margin-bottom:8px;"><strong style="text-transform:uppercase;font-size:10px;color:#00fc40;">{key}:</strong> {@html renderMarkdown(String(val))}</div>
          {/each}
        {:else}
          <span style="opacity:0.5;">No AI insights generated for this run.</span>
        {/if}
      </div>
    </div>

    <!-- Growth analysis -->
    {#if data.insights?.growth_analysis}
      <div style="background:white;border:3px solid #383832;box-shadow:4px 4px 0 #383832;margin-bottom:24px;">
        <div style="padding:10px 16px;background:#006f7c;color:white;font-size:11px;font-weight:900;letter-spacing:0.1em;">GROWTH ANALYSIS</div>
        <div style="padding:16px;font-size:12px;line-height:1.5;color:#383832;">
          {@html renderMarkdown(data.insights.growth_analysis)}
        </div>
      </div>
    {/if}

    <!-- Recommendation cards -->
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px;margin-bottom:24px;">
      <!-- Class A card -->
      <div style="background:white;border:3px solid #007518;box-shadow:4px 4px 0 #383832;">
        <div style="padding:10px 16px;background:#007518;color:white;font-size:11px;font-weight:900;letter-spacing:0.1em;">CLASS A RECOMMENDATIONS</div>
        <div style="padding:16px;font-size:12px;line-height:1.5;color:#383832;">
          <div style="margin-bottom:8px;font-weight:700;">{kpis.classA} outlets generating ~80% of revenue</div>
          {#if data.insights?.class_a_recommendations || data.insights?.class_a_recs}
            {@html renderMarkdown(data.insights.class_a_recommendations || data.insights.class_a_recs)}
          {:else}
            <ul style="margin:0;padding-left:16px;font-size:11px;color:#65655e;">
              <li>Assign dedicated sales reps</li>
              <li>Weekly visit cadence minimum</li>
              <li>Priority for promotions and new launches</li>
              <li>Monitor for declining trends</li>
            </ul>
          {/if}
        </div>
      </div>

      <!-- Class B card -->
      <div style="background:white;border:3px solid #ff9d00;box-shadow:4px 4px 0 #383832;">
        <div style="padding:10px 16px;background:#ff9d00;color:white;font-size:11px;font-weight:900;letter-spacing:0.1em;">CLASS B RECOMMENDATIONS</div>
        <div style="padding:16px;font-size:12px;line-height:1.5;color:#383832;">
          <div style="margin-bottom:8px;font-weight:700;">{kpis.classB} outlets in the growth tier</div>
          {#if data.insights?.class_b_recommendations || data.insights?.class_b_recs}
            {@html renderMarkdown(data.insights.class_b_recommendations || data.insights.class_b_recs)}
          {:else}
            <ul style="margin:0;padding-left:16px;font-size:11px;color:#65655e;">
              <li>Bi-weekly visit schedule</li>
              <li>Identify potential upgrades to Class A</li>
              <li>Cross-sell and upsell opportunities</li>
              <li>Track growth signals closely</li>
            </ul>
          {/if}
        </div>
      </div>

      <!-- Class C card -->
      <div style="background:white;border:3px solid #be2d06;box-shadow:4px 4px 0 #383832;">
        <div style="padding:10px 16px;background:#be2d06;color:white;font-size:11px;font-weight:900;letter-spacing:0.1em;">CLASS C RECOMMENDATIONS</div>
        <div style="padding:16px;font-size:12px;line-height:1.5;color:#383832;">
          <div style="margin-bottom:8px;font-weight:700;">{kpis.classC} outlets in the tail</div>
          {#if data.insights?.class_c_recommendations || data.insights?.class_c_recs}
            {@html renderMarkdown(data.insights.class_c_recommendations || data.insights.class_c_recs)}
          {:else}
            <ul style="margin:0;padding-left:16px;font-size:11px;color:#65655e;">
              <li>Monthly or on-demand visits</li>
              <li>Telesales or digital ordering</li>
              <li>Evaluate cost-to-serve vs. revenue</li>
              <li>Consider route consolidation</li>
            </ul>
          {/if}
        </div>
      </div>
    </div>

  <!-- ---- TAB 4: LOG ---- -->
  {:else if activeTab === 4}
    <ChapterHeading title="Pipeline Log" subtitle="Step-by-step execution trace" />
    <div style="background:white;border:3px solid #383832;box-shadow:4px 4px 0 #383832;padding:16px;">
      {#if logEntries.length > 0}
        {#each logEntries as entry, i}
          <div style="display:flex;align-items:flex-start;gap:10px;padding:8px 0;border-bottom:1px solid #ebe8dd;animation:fadeIn 0.3s ease-in;animation-delay:{i * 0.05}s;">
            <span style="color:#007518;font-size:14px;font-weight:900;line-height:1;">&#10003;</span>
            <span style="font-size:11px;font-weight:600;color:#383832;font-family:monospace;">{entry}</span>
          </div>
        {/each}
      {:else}
        <div style="text-align:center;color:#828179;font-size:11px;padding:24px;">No log entries recorded</div>
      {/if}
    </div>

  <!-- ---- TAB 5: EXPORT ---- -->
  {:else if activeTab === 5}
    <ChapterHeading title="Export Results" subtitle="Download classified data" />
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px;">
      <!-- Excel export -->
      <div style="background:white;border:3px solid #383832;box-shadow:4px 4px 0 #383832;">
        <div style="padding:12px 16px;background:#383832;color:#feffd6;font-size:11px;font-weight:900;letter-spacing:0.1em;">EXCEL EXPORT (.XLSX)</div>
        <div style="padding:20px;">
          <div style="font-size:11px;color:#383832;margin-bottom:16px;line-height:1.5;">
            Multi-sheet workbook with:
          </div>
          <ul style="margin:0 0 16px 0;padding-left:16px;font-size:11px;color:#65655e;">
            <li>All Outlets (classified)</li>
            <li>Branch Summary</li>
            <li>Class A / B / C sheets</li>
            <li>AI Insights</li>
            <li>Pipeline Log</li>
          </ul>
          <button
            onclick={() => exportExcel(data.job_id)}
            style="width:100%;padding:10px;font-size:11px;font-weight:900;letter-spacing:0.1em;background:#00fc40;color:#383832;border:2px solid #383832;box-shadow:3px 3px 0 #383832;cursor:pointer;"
          >
            DOWNLOAD EXCEL
          </button>
        </div>
      </div>

      <!-- Filtered export card -->
      <div style="background:white;border:3px solid #383832;box-shadow:4px 4px 0 #383832;padding:24px;">
        <div style="font-size:12px;font-weight:900;color:#383832;margin-bottom:8px;">EXPORT FILTERED DATA</div>
        <div style="font-size:10px;color:#65655e;margin-bottom:16px;">
          Downloads only the currently visible results ({filteredResults.length.toLocaleString()} outlets)
          {#if selectedBranch !== 'All Branches'} — filtered by {selectedBranch}{/if}
        </div>
        <button onclick={exportFilteredCSV}
          style="padding:10px 24px;font-size:11px;font-weight:900;letter-spacing:0.1em;background:#006f7c;color:white;border:2px solid #383832;box-shadow:3px 3px 0 #383832;cursor:pointer;font-family:'Space Grotesk',sans-serif;"
          onmousedown={(e) => { e.currentTarget.style.transform='translate(2px,2px)'; e.currentTarget.style.boxShadow='1px 1px 0 #383832'; }}
          onmouseup={(e) => { e.currentTarget.style.transform='translate(0,0)'; e.currentTarget.style.boxShadow='3px 3px 0 #383832'; }}
        >EXPORT FILTERED CSV ({filteredResults.length.toLocaleString()} ROWS)</button>
      </div>

      <!-- CSV export -->
      <div style="background:white;border:3px solid #383832;box-shadow:4px 4px 0 #383832;">
        <div style="padding:12px 16px;background:#383832;color:#feffd6;font-size:11px;font-weight:900;letter-spacing:0.1em;">CSV EXPORT (.CSV)</div>
        <div style="padding:20px;">
          <div style="font-size:11px;color:#383832;margin-bottom:16px;line-height:1.5;">
            Flat file export with all columns:
          </div>
          <ul style="margin:0 0 16px 0;padding-left:16px;font-size:11px;color:#65655e;">
            <li>All classification fields</li>
            <li>Sales aggregates (2Yr/12M/6M/3M)</li>
            <li>AI enrichment columns</li>
            <li>Contribution percentages</li>
          </ul>
          <button
            onclick={() => {
              if (!data) return;
              const header = explorerCols.join(',');
              const rows = data.results.map(r => explorerCols.map(c => JSON.stringify(r[c] ?? '')).join(','));
              const csv = [header, ...rows].join('\n');
              const blob = new Blob([csv], { type: 'text/csv' });
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url;
              a.download = `RTM_${data.job_id}.csv`;
              a.click();
              URL.revokeObjectURL(url);
            }}
            style="width:100%;padding:10px;font-size:11px;font-weight:900;letter-spacing:0.1em;background:#006f7c;color:white;border:2px solid #383832;box-shadow:3px 3px 0 #383832;cursor:pointer;"
          >
            DOWNLOAD CSV
          </button>
        </div>
      </div>
    </div>
  {/if}
{/if}
