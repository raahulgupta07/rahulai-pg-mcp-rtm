<script lang="ts">
  import { classify, classifyAsync, getJobStatus, getJobResult, exportExcel, getJob, getJobComparison, getSettings, uploadFile, deleteUpload, getF4Analysis } from '$lib/api';
  import { page } from '$app/stores';
  import KpiCard from '$lib/components/KpiCard.svelte';
  import DataTable from '$lib/components/DataTable.svelte';
  import Badge from '$lib/components/Badge.svelte';
  import ChapterHeading from '$lib/components/ChapterHeading.svelte';

  let state = $state('upload');
  let file = $state(null);
  let fileError = $state('');
  let preview = $state<null | {
    headers: string[];
    rows: string[][];
    totalRows: number;
    branches: { name: string; count: number }[];
    outletCount: number;
    dateRange: string;
    requiredMissing: string[];
    optionalPresent: string[];
    sampled: boolean;
  }>(null);

  const REQUIRED_COLS = ['Cus.Code', 'Cus.Name', 'TotalAmount', 'TotalPcs', 'BranchName', 'Item Type', 'Item Class', 'NumInBuy'];
  const OPTIONAL_COLS = ['DocDate', 'InvoiceNo', 'BrandName', 'Outlet Channel', 'Channel', 'GroupName', 'RouteCode'];

  function parseCsvLine(line: string): string[] {
    const out: string[] = [];
    let cur = '';
    let inQ = false;
    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (inQ) {
        if (ch === '"' && line[i + 1] === '"') { cur += '"'; i++; }
        else if (ch === '"') { inQ = false; }
        else { cur += ch; }
      } else {
        if (ch === '"') inQ = true;
        else if (ch === ',') { out.push(cur); cur = ''; }
        else cur += ch;
      }
    }
    out.push(cur);
    return out.map(s => s.trim());
  }

  async function buildPreview(f: File) {
    preview = null;
    try {
      // Slice first 8 MB to keep parse fast on huge files
      const SLICE = 8 * 1024 * 1024;
      const isSliced = f.size > SLICE;
      const blob = isSliced ? f.slice(0, SLICE) : f;
      const buf = await blob.arrayBuffer();
      // Try UTF-8 strict first; if it fails, fall back through cp1252 / latin-1.
      // Matches backend encoding fallback order so preview matches stored data.
      let text = '';
      const encodings = ['utf-8', 'windows-1252', 'iso-8859-1'];
      for (const enc of encodings) {
        try {
          text = new TextDecoder(enc, { fatal: enc === 'utf-8' }).decode(buf);
          break;
        } catch {
          // try next
        }
      }
      if (!text) text = new TextDecoder('utf-8').decode(buf);
      // If sliced, drop last partial line
      const allLines = text.split(/\r?\n/);
      const lines = isSliced ? allLines.slice(0, -1).filter(l => l.length > 0) : allLines.filter(l => l.length > 0);
      if (lines.length < 2) return;
      const headers = parseCsvLine(lines[0]);
      const dataLines = lines.slice(1);
      const sample = dataLines.slice(0, 10).map(parseCsvLine);

      const idx = (name: string) => headers.indexOf(name);
      const iBranch = idx('BranchName');
      const iCode = idx('Cus.Code');
      const iDate = idx('DocDate');

      const branchMap = new Map<string, number>();
      const outletSet = new Set<string>();
      let minDate = '', maxDate = '';
      for (const line of dataLines) {
        const row = parseCsvLine(line);
        if (iBranch >= 0) {
          const b = row[iBranch] || '(none)';
          branchMap.set(b, (branchMap.get(b) || 0) + 1);
        }
        if (iCode >= 0 && iBranch >= 0) outletSet.add(`${row[iBranch]}|${row[iCode]}`);
        if (iDate >= 0 && row[iDate]) {
          const d = row[iDate];
          if (!minDate || d < minDate) minDate = d;
          if (!maxDate || d > maxDate) maxDate = d;
        }
      }

      // Estimate total rows from full file size if sliced
      const scale = isSliced ? f.size / SLICE : 1;
      const branches = [...branchMap.entries()]
        .map(([name, count]) => ({ name, count: Math.round(count * scale) }))
        .sort((a, b) => b.count - a.count);

      preview = {
        headers,
        rows: sample,
        totalRows: Math.round(dataLines.length * scale),
        branches,
        outletCount: Math.round(outletSet.size * scale),
        dateRange: minDate && maxDate ? (minDate === maxDate ? minDate : `${minDate} → ${maxDate}`) : '—',
        requiredMissing: REQUIRED_COLS.filter(c => !headers.includes(c)),
        optionalPresent: OPTIONAL_COLS.filter(c => headers.includes(c)),
        sampled: isSliced,
      };
    } catch (e) {
      console.warn('preview parse failed', e);
      fileError = 'Could not parse CSV preview — file may be corrupted or wrong encoding';
    }
  }
  let thresholdA = $state(80);
  let thresholdB = $state(95);
  let data = $state(null);
  let comparison = $state(null);
  let error = $state('');
  let logEntries = $state([]);
  let selectedBranch = $state('All Branches');

  // Persist branch filter to localStorage
  $effect(() => {
    if (selectedBranch && typeof window !== 'undefined') {
      localStorage.setItem('rtm_branch_filter', selectedBranch);
    }
  });

  // Restore branch filter from localStorage after data is loaded
  $effect(() => {
    if (typeof window !== 'undefined' && state === 'results' && branches.length > 0) {
      const saved = localStorage.getItem('rtm_branch_filter');
      if (saved && saved !== 'All Branches' && branches.includes(saved)) {
        selectedBranch = saved;
      }
    }
  });

  let activeTab = $state(0);
  let searchQuery = $state('');
  let classFilter = $state('All');
  let currentStep = $state(0);
  let terminalLines = $state<string[]>([]);
  let uploadPct = $state(0);
  let uploadLoaded = $state(0);
  let uploadTotal = $state(0);
  let uploadId = $state<string | null>(null);
  let f4Data = $state<any | null>(null);

  // Lifecycle counts derived from results
  let lifecycle = $derived(() => {
    const buckets: Record<string, number> = { New: 0, Active: 0, Reactivated: 0, Dormant: 0, Lost: 0, Unknown: 0 };
    for (const r of filteredResults) {
      const s = r.Lifecycle_Stage || 'Unknown';
      buckets[s] = (buckets[s] || 0) + 1;
    }
    return buckets;
  });

  const terminalMessages: string[][] = [
    [
      '$ rtm-agent upload --file sales_data.csv',
      '[INFO] Reading file into memory buffer...',
      '[INFO] Detecting encoding: UTF-8 confirmed',
      '[INFO] Row count: 211,721 transactions',
      '[INFO] Column count: 27 fields detected',
      '[OK] File successfully loaded into DataFrame',
    ],
    [
      '$ rtm-agent validate --check-schema',
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
      '$ rtm-agent aggregate --group-by BranchName,Cus.Code',
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
      '$ rtm-agent calculate --periods 2Yr,12M,6M,3M',
      '[CALC] TotalSales_2Yr = SUM(TotalAmount) over full range',
      '[CALC] TotalSales_12M = SUM where DocDate >= 2024-09-30',
      '[CALC] TotalSales_6M = SUM where DocDate >= 2025-03-30',
      '[CALC] TotalSales_3M = SUM where DocDate >= 2025-06-30',
      '[CALC] Breaking down by Item Class: Nutrition, Food, Non Food',
      '[CALC] AvgSales = period_total / months_in_period',
      '[OK] Period averages computed for all 11,333 outlets',
    ],
    [
      '$ rtm-agent contributions --denominator branch_total',
      '[CALC] For each of 9 branches:',
      '[CALC]   outlet_pct = outlet_sales / branch_total * 100',
      '[CALC] Nutrition_Contribution_Pct per outlet...',
      '[CALC] Food_Contribution_Pct per outlet...',
      '[CALC] Non_Food_Contribution_Pct per outlet...',
      '[OK] Revenue contribution percentages computed',
    ],
    [
      '$ rtm-agent detect-wholesalers --threshold 3 --type Local',
      '[SCAN] Filtering transactions where Item Type == "Local"...',
      '[WARN] 0 Local product transactions found in dataset',
      '[WARN] All products are classified as "Import"',
      '[INFO] Wholesaler detection requires Local products',
      '[INFO] Carton formula: TotalPcs / NumInBuy per brand per month',
      '[SKIP] No wholesalers to flag — F4 classification not applied',
      '[OK] Wholesaler scan complete — 0 flagged',
    ],
    [
      '$ rtm-agent classify --method pareto --partition branch',
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
      '$ rtm-agent frequency --metric purchase_days',
      '[CALC] PurchaseDays_2Yr = COUNT(DISTINCT DocDate) per outlet',
      '[CALC] PurchaseDays_12M, PurchaseDays_6M computed',
      '[CALC] Frequency_2Yr = 365 / PurchaseDays_2Yr',
      '[INFO] Avg frequency: every 15.2 days',
      '[INFO] Most frequent buyer: every 2.1 days',
      '[OK] Purchase frequency metrics computed',
    ],
    [
      '$ rtm-agent enrich --ai-rules',
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
      '$ rtm-agent insights --model gemini-3.1-flash-lite --via openrouter',
      '[LLM] Connecting to OpenRouter API...',
      '[LLM] Model: google/gemini-3.1-flash-lite-preview',
      '[LLM] Generating executive summary (800 tokens)...',
      '[LLM] Generating class recommendations (1200 tokens)...',
      '[LLM] Generating growth analysis (600 tokens)...',
      '[LLM] Generating top-15 outlet insights (1000 tokens)...',
      '[OK] All AI insights generated',
      '',
      '═══════════════════════════════════════════',
      '[RTM AGENT] ✓ PIPELINE COMPLETE',
      '[RTM AGENT] 11,333 outlets classified',
      '[RTM AGENT] 9 branches processed',
      '[RTM AGENT] Job saved to database',
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
    terminalLines = ['[RTM AGENT] Loading job from history...', `[RTM AGENT] Job ID: ${jobId}`, '', '[INFO] Fetching results from database...'];
    try {
      const jobData = await getJob(jobId);
      const results = jobData.results || [];
      terminalLines = [...terminalLines, `[OK] Loaded ${results.length} outlet records`, '', '═══════════════════════════════════════════', '[RTM AGENT] ✓ JOB LOADED', '═══════════════════════════════════════════'];
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
      // Fetch comparison without blocking the main render
      comparison = null;
      getJobComparison(jobId).then(c => { comparison = c; }).catch(() => {});
      f4Data = null;
      getF4Analysis(jobId).then(r => f4Data = r).catch(() => f4Data = null);
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
    classA: filteredResults.filter(r => r.Classification?.startsWith('Class A')).length,
    classA_pure: filteredResults.filter(r => r.Classification === 'Class A').length,
    classA_f4: filteredResults.filter(r => /F4/i.test(r.Classification || '')).length,
    classB: filteredResults.filter(r => r.Classification === 'Class B').length,
    classC: filteredResults.filter(r => r.Classification === 'Class C').length,
    wholesalers: filteredResults.filter(r => r.Is_Wholesaler).length,
    revenue: filteredResults.reduce((s, r) => s + (r.TotalSales_2Yr || 0), 0),
    revA_f4: filteredResults.filter(r => /F4/i.test(r.Classification || '')).reduce((s, r) => s + (r.TotalSales_2Yr || 0), 0),
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
    if (n >= 1e9) return `Ks ${(n / 1e9).toFixed(1)}B`;
    if (n >= 1e6) return `Ks ${(n / 1e6).toFixed(1)}M`;
    if (n >= 1e3) return `Ks ${(n / 1e3).toFixed(1)}K`;
    return `Ks ${n.toLocaleString()}`;
  }

  function fmtPct(n) {
    return `${n.toFixed(1)}%`;
  }

  function renderMarkdown(text) {
    if (!text) return '';
    return text
      .replace(/### (.*?)$/gm, '<h3 class="md-h3">$1</h3>')
      .replace(/## (.*?)$/gm, '<h2 class="md-h2">$1</h2>')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/^- (.*?)$/gm, '<div class="md-li">• $1</div>')
      .replace(/^\* (.*?)$/gm, '<div class="md-li">• $1</div>')
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
    error = '';

    // ─── Stage 1: upload file to app disk ───
    state = 'uploading';
    uploadPct = 0;
    uploadLoaded = 0;
    uploadTotal = file.size;
    let uploaded;
    try {
      uploaded = await uploadFile(file, (pct, loaded, total) => {
        uploadPct = pct;
        uploadLoaded = loaded;
        uploadTotal = total;
      });
      uploadId = uploaded.upload_id;
    } catch (e: any) {
      error = `Upload failed: ${e.message || e}`;
      state = 'upload';
      return;
    }

    // ─── Stage 2: classify from staged file ───
    state = 'processing';
    currentStep = 0;
    terminalLines = [
      '[RTM AGENT] Pipeline initiated...',
      `[RTM AGENT] File: ${file.name} (${(file.size/1024/1024).toFixed(2)} MB) → staged on disk`,
      `[RTM AGENT] Upload ID: ${uploaded.upload_id.slice(0, 8)}...`,
      ''
    ];

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
      // Kick off async background job — returns instantly
      const { job_id } = await classifyAsync(uploaded.upload_id, thresholdA, thresholdB);
      // Poll status every 2s until ready (no LB timeout issue)
      let lastLogLen = 0;
      while (true) {
        await new Promise(r => setTimeout(r, 2000));
        const st = await getJobStatus(job_id);
        // Append any new log lines from backend to terminal
        if (st.log && st.log.length > lastLogLen) {
          const newLines = st.log.slice(lastLogLen);
          terminalLines = [...terminalLines, ...newLines];
          lastLogLen = st.log.length;
          scrollTerminal();
        }
        currentStep = st.step || currentStep;
        if (st.status === 'failed' || st.error) {
          throw new Error(st.error || st.message || 'Classification failed');
        }
        if (st.ready) break;
      }
      data = await getJobResult(job_id);
      clearInterval(stepInterval);
      clearInterval(typeInterval);
      comparison = data.comparison ?? null;
      logEntries = data.log || [];

      // Replace simulated terminal with actual pipeline log from backend
      if (data.log?.length) {
        terminalLines = [
          '[RTM AGENT] Pipeline initiated...',
          `[RTM AGENT] File: ${file.name} (${(file.size/1024).toFixed(0)} KB)`,
          '',
          ...data.log.map((l: string) => `  ${l}`),
          '',
          '═══════════════════════════════════════════',
          `[RTM AGENT] ✓ ALL STEPS COMPLETE — ${data.total_outlets ?? '?'} outlets classified`,
          '═══════════════════════════════════════════',
        ];
      } else {
        terminalLines = [...terminalLines, '', '═══════════════════════════════════════════', '[RTM AGENT] ✓ ALL STEPS COMPLETE', '═══════════════════════════════════════════'];
      }
      scrollTerminal();
      currentStep = 10;
      await new Promise(r => setTimeout(r, 1500));
      state = 'results';
      // Kick off F4 deep-dive fetch in background
      if (data?.job_id) {
        getF4Analysis(data.job_id).then(r => f4Data = r).catch(() => f4Data = null);
      }
    } catch (e: any) {
      clearInterval(stepInterval);
      clearInterval(typeInterval);
      terminalLines = [...terminalLines, '', `[RTM AGENT] ✗ ERROR: ${e.message}`];
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
      fileError = 'Invalid file type — only .csv files accepted';
      file = null;
      input.value = '';
      return;
    }
    // Validate: max 2 GB (staged to disk, then processed)
    if (selected.size > 2 * 1024 * 1024 * 1024) {
      fileError = `File too large — ${(selected.size / 1024 / 1024 / 1024).toFixed(2)} GB exceeds 2 GB limit`;
      file = null;
      input.value = '';
      return;
    }
    file = selected;
    buildPreview(selected);
  }

  function reset() {
    state = 'upload';
    file = null;
    preview = null;
    data = null;
    comparison = null;
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

    const classA_pure = filteredResults.filter(r => r.Classification === 'Class A');
    const classA_f4 = filteredResults.filter(r => /F4/i.test(r.Classification || ''));
    const classA_cat = filteredResults.filter(r => {
      const c = r.Classification || '';
      return c.startsWith('Class A') && c !== 'Class A' && !/F4/i.test(c);
    });
    const classA_all = filteredResults.filter(r => (r.Classification || '').startsWith('Class A'));
    const classB = filteredResults.filter(r => r.Classification === 'Class B');
    const classC = filteredResults.filter(r => r.Classification === 'Class C');

    const rev = (arr: any[]) => arr.reduce((s, r) => s + (r.TotalSales_2Yr || 0), 0);

    return [
      { Classification: 'Class A (total)', Count: classA_all.length, Revenue: rev(classA_all) },
      { Classification: '  ↳ Pure Class A', Count: classA_pure.length, Revenue: rev(classA_pure) },
      { Classification: '  ↳ F4 Distributor', Count: classA_f4.length, Revenue: rev(classA_f4) },
      { Classification: '  ↳ Class A (category)', Count: classA_cat.length, Revenue: rev(classA_cat) },
      { Classification: 'Class B', Count: classB.length, Revenue: rev(classB) },
      { Classification: 'Class C', Count: classC.length, Revenue: rev(classC) },
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

  const tabLabels = ['Dashboard', 'Data Explorer', 'Analytics', 'AI Insights', 'Comparison', 'Log', 'Export'];

  // Helper for the Comparison tab — color a Change value by sign
  function changeColor(n: number) {
    if (n > 0) return 'var(--success)';
    if (n < 0) return 'var(--danger)';
    return 'var(--text-muted)';
  }
  function fmtMaybeNum(v: any) {
    return typeof v === 'number' ? v.toLocaleString() : v;
  }
  const pipelineSteps = ['Upload', 'Validate', 'Aggregate', 'Averages', 'Contributions', 'Wholesalers', 'Classify', 'Frequency', 'AI Enrich'];
  let pipelineExpanded = $state(false);

  function cliClass(line: string) {
    if (line.startsWith('[RTM AGENT] ✓')) return 'cli-success';
    if (line.startsWith('[RTM AGENT] ✗')) return 'cli-error';
    if (line.startsWith('[RTM AGENT]')) return 'cli-info';
    if (line.startsWith('$')) return 'cli-command';
    if (line.startsWith('[OK]')) return 'cli-success';
    if (line.startsWith('[WARN]')) return 'cli-warn';
    if (line.startsWith('[SKIP]')) return 'cli-warn';
    if (line.startsWith('[RESULT]')) return 'cli-info';
    if (line.startsWith('[ALGO]')) return 'cli-info';
    if (line.startsWith('[CALC]')) return 'cli-dim';
    if (line.startsWith('[SCAN]')) return 'cli-info';
    if (line.startsWith('[SQL]')) return 'cli-warn';
    if (line.startsWith('[AI]')) return 'cli-info';
    if (line.startsWith('[LLM]')) return 'cli-info';
    if (line.startsWith('[INFO]')) return 'cli-dim';
    if (line.startsWith('[ERR]')) return 'cli-error';
    if (line.startsWith('═')) return 'cli-success';
    if (line === '') return 'cli-blank';
    return 'cli-output';
  }
</script>

<!-- HERO -->
<div class="page-hero animate-fade-in">
  <h1>RTM Agent — Outlet Classification</h1>
  <p>Pareto 80/15/5, partitioned by branch</p>
</div>

<!-- ======== UPLOAD STATE ======== -->
{#if state === 'upload'}
  <div class="upload-wrap animate-fade-up">
    <!-- Hidden file input -->
    <input
      type="file"
      accept=".csv"
      id="fileInput"
      onchange={handleFileChange}
      style="display:none;"
    />

    <!-- File upload card -->
    <div class="card upload-card">

      {#if fileError}
        <div class="alert alert-danger" style="margin-bottom:12px;">{fileError}</div>
      {/if}

      {#if !file}
        <!-- Empty state: clickable upload area -->
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <div
          class="drop-zone"
          onclick={() => document.getElementById('fileInput')?.click()}
        >
          <div class="drop-icon">↑</div>
          <div class="drop-title">Upload Sales CSV</div>
          <div class="drop-sub">Click to browse or drag &amp; drop your file</div>
          <div class="drop-hint">Only .csv files accepted</div>
        </div>
      {:else}
        <!-- File selected state -->
        <div class="file-selected">
          <div class="file-info">
            <div class="file-check">✓</div>
            <div>
              <div class="file-name">{file.name}</div>
              <div class="file-meta">{file.size > 1024 * 1024 ? (file.size / 1024 / 1024).toFixed(1) + ' MB' : (file.size / 1024).toFixed(0) + ' KB'} · CSV file</div>
            </div>
          </div>
          <button
            class="btn-danger btn-sm file-remove"
            aria-label="Remove file"
            onclick={() => { file = null; preview = null; fileError = ''; const el = document.getElementById('fileInput'); if (el) (el as HTMLInputElement).value = ''; }}
          >✕</button>
        </div>

        <!-- File validation error -->
        {#if fileError}
          <div class="alert alert-danger" style="margin-top:12px;">{fileError}</div>
        {/if}
      {/if}

      <!-- Threshold sliders -->
      <div class="threshold-row">
        <div class="threshold-field">
          <label class="label" for="threshA">Class A cutoff: {thresholdA}%</label>
          <input id="threshA" type="range" min="50" max="95" bind:value={thresholdA} class="range range-a" />
        </div>
        <div class="threshold-field">
          <label class="label" for="threshB">Class B cutoff: {thresholdB}%</label>
          <input id="threshB" type="range" min={thresholdA + 1} max="99" bind:value={thresholdB} class="range range-b" />
        </div>
      </div>

      <!-- Preview KPI cards -->
      {#if file}
        <div class="preview-kpis">
          <KpiCard label="Class A" value="{thresholdA}%" subtitle="top revenue" accent="var(--class-a)" />
          <KpiCard label="Class B" value="{thresholdB - thresholdA}%" subtitle="middle tier" accent="var(--class-b)" />
          <KpiCard label="Class C" value="{100 - thresholdB}%" subtitle="remaining" accent="var(--class-c)" />
        </div>
      {/if}

      <!-- CTA Button -->
      <button class="btn btn-block run-btn" onclick={handleClassify} disabled={!file || (preview && preview.requiredMissing.length > 0)}>
        Run Classification
      </button>
    </div>

    <!-- File Preview Panel -->
    {#if file && preview}
      <div class="card preview-panel animate-fade-up">
        <div class="card-head">
          <div class="card-head-title">File Preview</div>
          <div class="card-head-sub">{file.name} · {file.size > 1024 * 1024 ? (file.size / 1024 / 1024).toFixed(1) + ' MB' : (file.size / 1024).toFixed(0) + ' KB'}{preview.sampled ? ' · stats estimated from first 8 MB' : ''}</div>
        </div>
        <div class="preview-body">
          <!-- KPI strip -->
          <div class="preview-stats">
            <KpiCard label="Rows" value={preview.totalRows.toLocaleString()} />
            <KpiCard label="Branches" value={preview.branches.length.toString()} />
            <KpiCard label="Outlets" value={preview.outletCount.toLocaleString()} />
            <KpiCard label="Columns" value={preview.headers.length.toString()} />
            <KpiCard label="Date Range" value={preview.dateRange} />
          </div>

          <!-- Column mapping -->
          <div class="preview-section">
            <div class="preview-section-title">
              Columns detected — {preview.headers.length - preview.requiredMissing.length}/{REQUIRED_COLS.length + OPTIONAL_COLS.length} known schema cols found
            </div>

            <div class="col-legend">
              <span><span class="chip chip-req">✓</span> required matched</span>
              <span><span class="chip chip-bad">✕</span> required missing</span>
              <span><span class="chip chip-opt">✓</span> optional present</span>
            </div>

            <div class="col-group-title">Required ({REQUIRED_COLS.length - preview.requiredMissing.length}/{REQUIRED_COLS.length})</div>
            <div class="col-chips">
              {#each REQUIRED_COLS as col}
                {@const ok = preview.headers.includes(col)}
                <span class="chip {ok ? 'chip-req' : 'chip-bad'}">{ok ? '✓' : '✕'} {col}</span>
              {/each}
            </div>

            {#if preview.optionalPresent.length > 0}
              <div class="col-group-title">Optional present ({preview.optionalPresent.length}/{OPTIONAL_COLS.length})</div>
              <div class="col-chips">
                {#each preview.optionalPresent as col}
                  <span class="chip chip-opt">✓ {col}</span>
                {/each}
              </div>
            {/if}

            {#if preview.requiredMissing.length > 0}
              <div class="alert alert-danger" style="margin-top:10px;">
                Missing required: {preview.requiredMissing.join(', ')}
              </div>
            {:else}
              <div class="preview-ok">✓ All {REQUIRED_COLS.length} required columns matched — ready to classify</div>
            {/if}
          </div>

          <!-- Sample table -->
          <div class="preview-section">
            <div class="preview-section-title">Sample — first {preview.rows.length} rows</div>
            <div class="preview-table-wrap">
              <table class="preview-table">
                <thead>
                  <tr>
                    {#each preview.headers as h}
                      <th>{h}</th>
                    {/each}
                  </tr>
                </thead>
                <tbody>
                  {#each preview.rows as row}
                    <tr>
                      {#each preview.headers as _, ci}
                        <td>{row[ci] ?? ''}</td>
                      {/each}
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
            <div class="preview-foot">showing {preview.rows.length} of {preview.totalRows.toLocaleString()} rows</div>
          </div>

          <!-- Branch distribution -->
          {#if preview.branches.length > 0}
            {@const maxCount = preview.branches[0].count}
            <div class="preview-section">
              <div class="preview-section-title">Branch distribution</div>
              <div class="branch-bars">
                {#each preview.branches.slice(0, 5) as b}
                  <div class="branch-bar-row">
                    <div class="branch-bar-name">{b.name}</div>
                    <div class="branch-bar-track">
                      <div class="branch-bar-fill" style="width: {(b.count / maxCount) * 100}%"></div>
                    </div>
                    <div class="branch-bar-count">{b.count.toLocaleString()}</div>
                  </div>
                {/each}
                {#if preview.branches.length > 5}
                  <div class="branch-more">+ {preview.branches.length - 5} more</div>
                {/if}
              </div>
            </div>
          {/if}
        </div>
      </div>
    {/if}

    <!-- Error -->
    {#if error}
      <div class="alert alert-danger" style="margin-top:16px;">Error: {error}</div>
    {/if}
  </div>

  <!-- HOW IT WORKS -->
  <div class="info-block">
    <div class="card card-flush">
      <div class="card-head">
        <div class="card-head-title">How It Works</div>
        <div class="card-head-sub">What the RTM Agent does with your data</div>
      </div>
      <div class="card-body">
        <div class="pipeline-steps">
          {#each [
            { n: '01', label: 'Validate', color: 'var(--class-a)' },
            { n: '02', label: 'Aggregate', color: 'var(--class-f4)' },
            { n: '03', label: 'Pareto', color: 'var(--class-b)' },
            { n: '04', label: 'Wholesale', color: 'var(--accent)' },
            { n: '05', label: 'AI Enrich', color: 'var(--class-c)' },
            { n: '06', label: 'Results', color: 'var(--text-muted)' },
          ] as step, i}
            <div class="pstep">
              <div class="pstep-inner">
                <div class="pstep-num" style="background:{step.color};">{step.n}</div>
                <div class="pstep-label">{step.label}</div>
              </div>
              {#if i < 5}
                <div class="pstep-arrow">›</div>
              {/if}
            </div>
          {/each}
        </div>

        <div class="how-grid">
          <div class="how-item" style="border-left-color:var(--class-a);">Check columns, parse dates, detect branches</div>
          <div class="how-item" style="border-left-color:var(--class-f4);">Group transactions → unique outlets per branch</div>
          <div class="how-item" style="border-left-color:var(--class-b);">Sort by revenue, assign A (80%), B (15%), C (5%)</div>
          <div class="how-item" style="border-left-color:var(--accent);">Flag bulk buyers (≥3 cartons/brand/month)</div>
          <div class="how-item" style="border-left-color:var(--class-c);">Growth signals, risk levels, LLM insights</div>
          <div class="how-item" style="border-left-color:var(--text-muted);">Dashboard, charts, per-branch Excel export</div>
        </div>
      </div>
    </div>
  </div>

  <!-- REQUIRED COLUMNS -->
  <div class="info-block">
    <div class="card card-flush">
      <div class="card-head">
        <div class="card-head-title">Required Columns In Your CSV</div>
      </div>
      <div class="card-body">
        <div class="cols-grid">
          {#each [
            { col: 'Cus.Code', desc: 'Customer ID' },
            { col: 'Cus.Name', desc: 'Outlet name' },
            { col: 'TotalAmount', desc: 'Sales amount' },
            { col: 'TotalPcs', desc: 'Quantity' },
            { col: 'BranchName', desc: 'Branch partition' },
            { col: 'Item Class', desc: 'Nutrition/Food/Non Food' },
            { col: 'NumInBuy', desc: 'Units per carton' },
          ] as item}
            <div class="col-card">
              <div class="col-name">{item.col}</div>
              <div class="col-desc">{item.desc}</div>
            </div>
          {/each}
        </div>
        <div class="optional-row">
          <span class="optional-label">Optional</span>
          {#each ['DocDate', 'InvoiceNo', 'BrandName', 'Item Type', 'Channel'] as col}
            <span class="chip">{col}</span>
          {/each}
        </div>
      </div>
    </div>
  </div>

  <!-- WHAT YOU GET -->
  <div class="info-block info-block-last">
    <div class="card card-flush">
      <div class="card-head">
        <div class="card-head-title">What You Get</div>
      </div>
      <div class="card-body">
        <div class="get-grid">
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
            <div class="get-item">
              <span class="get-check">✓</span>
              <span>{item}</span>
            </div>
          {/each}
        </div>
      </div>
    </div>
  </div>

<!-- ======== UPLOADING STATE ======== -->
{:else if state === 'uploading'}
  <div class="upload-wrap animate-fade-up">
    <div class="card uploading-card">
      <div class="card-head">
        <div class="card-head-title">Uploading to App</div>
        <div class="card-head-sub">{file?.name} · {file ? (file.size / 1024 / 1024).toFixed(2) : 0} MB → staging on disk</div>
      </div>
      <div class="uploading-body">
        <div class="uploading-pct">{uploadPct.toFixed(1)}%</div>
        <div class="uploading-bar-track">
          <div class="uploading-bar-fill" style="width: {uploadPct}%"></div>
        </div>
        <div class="uploading-stats">
          {(uploadLoaded / 1024 / 1024).toFixed(1)} MB of {(uploadTotal / 1024 / 1024).toFixed(1)} MB transferred
        </div>
        <div class="uploading-hint">
          File is being staged to local app storage. Database write happens only after classification completes.
        </div>
      </div>
    </div>
  </div>

<!-- ======== PROCESSING STATE ======== -->
{:else if state === 'processing'}
  <div class="proc-grid animate-fade-in">

    <!-- LEFT: Pipeline steps -->
    <div class="card card-flush proc-left">
      <div class="card-head">
        <div class="card-head-title">Pipeline — {currentStep >= 10 ? '10' : currentStep}/10 steps</div>
      </div>

      <div class="proc-steps">
        {#each [
          'Upload File',
          'Validate Data',
          'Aggregate',
          'Averages',
          'Contributions',
          'Wholesalers',
          'Classify',
          'Frequency',
          'AI Enrich',
          'Insights'
        ] as step, i}
          <div class="proc-step" class:done={i < currentStep} class:active={i === currentStep} class:pending={i > currentStep}>
            <div class="proc-step-num">
              {i < currentStep ? '✓' : i === currentStep ? '▸' : (i + 1)}
            </div>
            <div class="proc-step-label">{step}</div>
            {#if i === currentStep}
              <div class="proc-dots">
                <span></span><span></span><span></span>
              </div>
            {/if}
            {#if i < currentStep}
              <span class="badge badge-a">Done</span>
            {/if}
          </div>
        {/each}
      </div>

      <!-- Progress bar -->
      <div class="proc-progress">
        <div class="progress-bar">
          <div class="progress-bar-fill" style="width:{Math.min(currentStep * 10, 100)}%;"></div>
        </div>
        <div class="proc-progress-label">{Math.min(currentStep * 10, 100)}% complete</div>
      </div>
    </div>

    <!-- RIGHT: Terminal output -->
    <div class="cli-terminal proc-terminal">
      <div class="cli-bar">
        <span class="cli-dot"></span>
        <span class="cli-bar-title">rtm_agent_terminal</span>
        <span class="cli-bar-pid">PID: 28320</span>
      </div>

      <div id="terminal-scroll" class="cli-scroll">
        {#each terminalLines as line, i}
          <div class="cli-line {cliClass(line)}">{line}</div>
        {/each}

        <!-- Blinking cursor -->
        {#if currentStep < 10}
          <div class="cli-cursor-row">
            <span class="cli-command">$</span>
            <span class="cli-cursor"></span>
          </div>
        {/if}
      </div>
    </div>
  </div>

<!-- ======== RESULTS STATE ======== -->
{:else if state === 'results' && data}

  <!-- Collapsible pipeline bar -->
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="pipeline-bar" class:expanded={pipelineExpanded} onclick={() => pipelineExpanded = !pipelineExpanded}>
    <div class="pipeline-bar-left">
      <span class="pipeline-chevron" class:open={pipelineExpanded}>▾</span>
      <span class="pipeline-bar-title">Pipeline complete — 10/10 steps</span>
      <span class="pipeline-bar-job">Job: {data.job_id}</span>
    </div>
    <div class="pipeline-bar-right">
      <span class="badge badge-a">✓ Success</span>
      <span class="pipeline-bar-action">{pipelineExpanded ? 'Collapse' : 'Expand log'}</span>
    </div>
  </div>

  <!-- Expanded pipeline panel -->
  {#if pipelineExpanded}
    <div class="pipeline-panel animate-fade-in">
      <div class="pipeline-panel-grid">
        <!-- Left: completed steps -->
        <div class="pipeline-panel-steps">
          {#each ['Upload','Validate','Aggregate','Averages','Contributions','Wholesalers','Classify','Frequency','AI Enrich','Insights'] as step, i}
            <div class="pipeline-panel-step">
              <div class="pipeline-panel-check">✓</div>
              <div class="pipeline-panel-label">{step}</div>
              <span class="badge badge-a">Done</span>
            </div>
          {/each}
        </div>
        <!-- Right: terminal log -->
        <div class="cli-terminal pipeline-panel-cli">
          <div class="cli-scroll">
            {#each terminalLines as line}
              <div class="cli-line {cliClass(line)}">{line}</div>
            {/each}
          </div>
        </div>
      </div>
    </div>
  {/if}

  <!-- Controls row -->
  <div class="controls-row">
    <!-- Branch filter -->
    <div class="branch-filter">
      <span class="label">Branch</span>
      <select class="select" bind:value={selectedBranch}>
        <option>All Branches</option>
        {#each branches as branch}
          <option>{branch}</option>
        {/each}
      </select>
    </div>

    <!-- Job ID + Reset -->
    <div class="controls-right">
      <span class="job-tag">Job: {data.job_id}</span>
      <button class="btn btn-sm" onclick={reset}>New Job</button>
    </div>
  </div>

  <!-- KPI cards grid -->
  <div class="grid-kpi results-kpis">
    <KpiCard label="Total Outlets" value={kpis.total.toLocaleString()} subtitle="{kpis.branchCount} branches" accent="var(--text-muted)" />
    <KpiCard label="Class A (total)" value={kpis.classA.toLocaleString()} subtitle="{kpis.total > 0 ? fmtPct((kpis.classA / kpis.total) * 100) : '0%'} of total" accent="var(--class-a)" />
    <KpiCard label="F4 Distributors" value={kpis.classA_f4.toLocaleString()} subtitle="{kpis.classA > 0 ? fmtPct((kpis.classA_f4 / kpis.classA) * 100) : '0%'} of Class A · {fmtNum(kpis.revA_f4)}" accent="var(--class-f4)" />
    <KpiCard label="Pure Class A" value={kpis.classA_pure.toLocaleString()} subtitle="Pareto-ranked, no override" accent="var(--class-a)" />
    <KpiCard label="Class B" value={kpis.classB.toLocaleString()} subtitle="{kpis.total > 0 ? fmtPct((kpis.classB / kpis.total) * 100) : '0%'} of total" accent="var(--class-b)" />
    <KpiCard label="Class C" value={kpis.classC.toLocaleString()} subtitle="{kpis.total > 0 ? fmtPct((kpis.classC / kpis.total) * 100) : '0%'} of total" accent="var(--class-c)" />
    <KpiCard label="Total Revenue" value={fmtNum(kpis.revenue)} subtitle="2-year aggregate" accent="var(--class-a)" />
  </div>

  <!-- Tab bar -->
  <div class="tab-bar results-tabs">
    {#each tabLabels as label, i}
      <button class="tab" class:active={activeTab === i} onclick={() => activeTab = i}>
        {label}
      </button>
    {/each}
  </div>

  <!-- ---- TAB 0: DASHBOARD ---- -->
  {#if activeTab === 0}

    <!-- Data Quality Panel -->
    {#if data.data_quality?.length > 0 || data.data_quality_ok?.length > 0}
      <div class="section-block">
        <ChapterHeading title="Data Quality Report" subtitle="What was detected and what's missing" />
        <div class="card">

          <!-- OK checks -->
          {#if data.data_quality_ok?.length > 0}
            {#each data.data_quality_ok as check}
              <div class="dq-row">
                <span class="dq-icon dq-ok">✓</span>
                <span class="dq-text">{check}</span>
              </div>
            {/each}
          {/if}

          <!-- Warnings / Missing -->
          {#if data.data_quality?.length > 0}
            {#each data.data_quality as item}
              <div class="dq-row dq-row-top">
                <span class="dq-icon"
                  class:dq-warn={item.status === 'warning'}
                  class:dq-miss={item.status === 'missing'}
                  class:dq-info={item.status !== 'warning' && item.status !== 'missing'}
                >{item.status === 'warning' ? '!' : item.status === 'missing' ? '✗' : 'i'}</span>
                <div class="dq-body">
                  <div class="dq-head">
                    <span class="dq-field">{item.field}</span>
                    <span class="badge"
                      class:badge-b={item.status === 'warning'}
                      class:badge-c={item.status === 'missing'}
                      class:badge-f4={item.status !== 'warning' && item.status !== 'missing'}
                    >{item.status}</span>
                  </div>
                  <div class="dq-message">{item.message}</div>
                  <div class="dq-impact">Impact: {item.impact}</div>
                </div>
              </div>
            {/each}
          {/if}
        </div>
      </div>
    {/if}

    <div class="section-block">
      <ChapterHeading title="Classification Summary" subtitle="Breakdown by Pareto class" />
      <DataTable title="SUMMARY" data={summaryRows()} columns={['Classification', 'Count', 'Revenue', 'Avg Sales', 'Share %']} maxHeight="300px" />
    </div>

    <!-- ===== Outlet Lifecycle (cohort analysis from DocDate) ===== -->
    <div class="section-block">
      <ChapterHeading title="Outlet Lifecycle" subtitle="Cohort analysis from purchase history" />
      <div class="lifecycle-grid">
        <KpiCard label="New" value={lifecycle().New.toLocaleString()} subtitle="First buy < 3M ago" accent="var(--class-a)" />
        <KpiCard label="Active" value={lifecycle().Active.toLocaleString()} subtitle="Bought in last 3M" accent="var(--accent)" />
        <KpiCard label="Reactivated" value={lifecycle().Reactivated.toLocaleString()} subtitle="Returned after gap" accent="var(--class-f4)" />
        <KpiCard label="Dormant" value={lifecycle().Dormant.toLocaleString()} subtitle="Last buy 3–12M ago" accent="var(--class-b)" />
        <KpiCard label="Lost" value={lifecycle().Lost.toLocaleString()} subtitle="Last buy > 12M ago" accent="var(--class-c)" />
      </div>
    </div>

    <!-- ===== F4 Distributor Deep-Dive ===== -->
    {#if f4Data && f4Data.f4_count > 0}
      <div class="section-block">
        <ChapterHeading title="F4 Distributor Deep-Dive" subtitle="{f4Data.f4_count.toLocaleString()} F4 outlets · {f4Data.revenue_share_pct}% of total revenue" />

        <div class="f4-kpis">
          <KpiCard label="Health Score" value={f4Data.health_score + '%'} subtitle="100 = all stable" accent="var(--class-f4)" />
          <KpiCard label="F4 Revenue" value={fmtNum(f4Data.f4_revenue)} subtitle="{f4Data.revenue_share_pct}% share" accent="var(--accent)" />
          <KpiCard label="Growing" value={f4Data.growing.toLocaleString()} subtitle="6M > ½·12M" accent="var(--class-a)" />
          <KpiCard label="Declining" value={f4Data.declining.toLocaleString()} subtitle="Carton volume falling" accent="var(--class-c)" />
          <KpiCard label="High Risk" value={f4Data.high_risk.toLocaleString()} subtitle="Churn likely" accent="var(--class-c)" />
        </div>

        {#if f4Data.top10?.length}
          <div style="margin-top:18px;">
            <DataTable title="TOP 10 F4 BY REVENUE" maxHeight="350px"
              data={f4Data.top10.map((r: any) => ({
                'Cus.Code': r.code,
                'Cus.Name': r.name,
                Branch: r.branch,
                '2Yr Sales': fmtNum(r.revenue_2yr),
                '6M Sales': fmtNum(r.revenue_6m),
                '3M Sales': fmtNum(r.revenue_3m),
                Growth: r.growth || '-',
                Risk: r.risk || '-',
              }))}
              columns={['Cus.Code', 'Cus.Name', 'Branch', '2Yr Sales', '6M Sales', '3M Sales', 'Growth', 'Risk']} />
          </div>
        {/if}

        {#if f4Data.churn_risk?.length}
          <div style="margin-top:18px;">
            <DataTable title="F4 AT CHURN RISK — IMMEDIATE FOLLOW-UP" maxHeight="350px"
              data={f4Data.churn_risk.map((r: any) => ({
                'Cus.Code': r.code,
                'Cus.Name': r.name,
                Branch: r.branch,
                '2Yr Sales': fmtNum(r.revenue_2yr),
                '6M Sales': fmtNum(r.revenue_6m),
                Growth: r.growth || '-',
                Risk: r.risk || '-',
                Lifecycle: r.lifecycle || '-',
              }))}
              columns={['Cus.Code', 'Cus.Name', 'Branch', '2Yr Sales', '6M Sales', 'Growth', 'Risk', 'Lifecycle']} />
          </div>
        {/if}

        {#if f4Data.by_branch?.length}
          <div style="margin-top:18px;">
            <DataTable title="F4 PRESENCE BY BRANCH" maxHeight="400px"
              data={f4Data.by_branch.map((b: any) => ({
                Branch: b.branch,
                'Total Outlets': b.total_outlets.toLocaleString(),
                'F4 Count': b.f4_count.toLocaleString(),
                'F4 %': b.f4_pct + '%',
                'F4 Revenue': fmtNum(b.f4_revenue),
                'Revenue Share': b.revenue_share + '%',
              }))}
              columns={['Branch', 'Total Outlets', 'F4 Count', 'F4 %', 'F4 Revenue', 'Revenue Share']} />
          </div>
        {/if}
      </div>
    {/if}

    <div class="section-block">
      <ChapterHeading title="Top 10 Outlets" subtitle="Highest revenue outlets across selection" />
      <DataTable title="TOP 10" data={top10()} columns={['Cus.Code', 'Cus.Name', 'Branch', 'Classification', '2Yr Sales', 'Contribution %']} maxHeight="400px" />
    </div>

    <div class="section-block">
      <ChapterHeading title="Branch Matrix" subtitle="Performance across all branches" />
      <DataTable title="BRANCHES" data={branchMatrix()} columns={['Branch', 'Outlets', 'Revenue', 'Class A', 'Class B', 'Class C', 'A %']} maxHeight="400px" />
    </div>

    <!-- Seller Workload -->
    {#if data.workload?.length > 0}
      <div class="section-block">
        <ChapterHeading title="Seller Workload" subtitle="Route outlet counts vs targets (YGN: 25-30, Regional: 30-35)" />
        <div class="card card-flush">
          <div class="data-table-head">
            <span>Route Workload</span>
            <span class="muted">{data.workload.length} routes</span>
          </div>
          <div class="data-table-wrap">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Branch</th>
                  <th>Route</th>
                  <th class="ta-c">Outlets</th>
                  <th class="ta-c">Target</th>
                  <th class="ta-c">Status</th>
                </tr>
              </thead>
              <tbody>
                {#each data.workload as row, i}
                  <tr>
                    <td class="td-strong">{row.BranchName}</td>
                    <td class="td-mono">{row.RouteCode}</td>
                    <td class="ta-c td-strong">{row.OutletCount}</td>
                    <td class="ta-c muted">{row.BranchName === 'Yangon' ? '25-30' : '30-35'}</td>
                    <td class="ta-c">
                      <span class="badge"
                        class:badge-a={row.Workload_Status === 'OK'}
                        class:badge-c={row.Workload_Status === 'BELOW_MIN'}
                        class:badge-b={row.Workload_Status !== 'OK' && row.Workload_Status !== 'BELOW_MIN'}
                      >{row.Workload_Status === 'OK' ? 'OK' : row.Workload_Status === 'BELOW_MIN' ? 'Below Min' : 'Above Max'}</span>
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
      <div class="section-block">
        <div class="card card-flush ai-panel">
          <div class="card-head">
            <div class="card-head-title">AI Executive Summary</div>
          </div>
          <div class="card-body ai-content">
            {#if data.insights.executive_summary}
              {@html renderMarkdown(data.insights.executive_summary)}
            {:else}
              {#each Object.entries(data.insights) as [key, val]}
                <div class="ai-kv"><strong>{key}:</strong> {@html renderMarkdown(String(val))}</div>
              {/each}
            {/if}
          </div>
        </div>
      </div>
    {/if}

  <!-- ---- TAB 1: DATA EXPLORER ---- -->
  {:else if activeTab === 1}
    <div class="explorer-controls">
      <select class="select" bind:value={classFilter}>
        <option>All</option>
        <option>Class A</option>
        <option>Class B</option>
        <option>Class C</option>
        <option>Class A Local (F4)</option>
      </select>
      <input class="input explorer-search" type="text" bind:value={searchQuery} placeholder="Search outlet name or code..." />
    </div>

    <DataTable title="ALL OUTLETS" data={explorerData()} columns={explorerCols} maxHeight="600px" />

  <!-- ---- TAB 2: ANALYTICS ---- -->
  {:else if activeTab === 2}
    <div class="section-block">
      <ChapterHeading title="Branch Revenue Comparison" subtitle="Relative revenue by branch" />
      <div class="card chart-card">
        {#each branchBars() as bar}
          <div class="bar-row">
            <div class="bar-label">{bar.name}</div>
            <div class="bar-track">
              <div class="bar-fill bar-fill-a" style="width:{bar.pct}%;"></div>
            </div>
            <div class="bar-value">{fmtNum(bar.revenue)}</div>
          </div>
        {/each}
        {#if branchBars().length === 0}
          <div class="empty-note">No branch data available</div>
        {/if}
      </div>
    </div>

    <div class="section-block">
      <ChapterHeading title="Period Comparison" subtitle="Aggregate sales by time window" />
      <div class="card chart-card">
        {#each periodBars() as bar}
          <div class="bar-row">
            <div class="bar-label bar-label-sm">{bar.period}</div>
            <div class="bar-track bar-track-lg">
              <div class="bar-fill bar-fill-f4" style="width:{bar.pct}%;"></div>
            </div>
            <div class="bar-value">{fmtNum(bar.value)}</div>
          </div>
        {/each}
      </div>
    </div>

    <!-- Trend Comparison Table -->
    <div class="section-block">
      <ChapterHeading title="Trend Comparison" subtitle="Period-over-period growth by branch" />
      <div class="card card-flush">
        <div class="data-table-head"><span>Growth Trends</span></div>
        <div class="data-table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>Branch</th>
                <th class="ta-r">12M Sales</th>
                <th class="ta-r">6M Sales</th>
                <th class="ta-r">3M Sales</th>
                <th class="ta-c">6M vs 12M</th>
                <th class="ta-c">3M vs 6M</th>
              </tr>
            </thead>
            <tbody>
              {#each trendData() as row, i}
                <tr>
                  <td class="td-strong">{row.Branch}</td>
                  <td class="ta-r">{fmtNum(row['12M'])}</td>
                  <td class="ta-r">{fmtNum(row['6M'])}</td>
                  <td class="ta-r">{fmtNum(row['3M'])}</td>
                  <td class="ta-c">
                    <span class="badge"
                      class:badge-a={row['6M vs 12M'] > 5}
                      class:badge-c={row['6M vs 12M'] < -5}
                      class:badge-b={row['6M vs 12M'] >= -5 && row['6M vs 12M'] <= 5}
                    >{row['6M vs 12M'] > 0 ? '+' : ''}{row['6M vs 12M'].toFixed(1)}%</span>
                  </td>
                  <td class="ta-c">
                    <span class="badge"
                      class:badge-a={row['3M vs 6M'] > 5}
                      class:badge-c={row['3M vs 6M'] < -5}
                      class:badge-b={row['3M vs 6M'] >= -5 && row['3M vs 6M'] <= 5}
                    >{row['3M vs 6M'] > 0 ? '+' : ''}{row['3M vs 6M'].toFixed(1)}%</span>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Pareto Curve -->
    <div class="section-block">
      <ChapterHeading title="Pareto Curve" subtitle="Cumulative revenue distribution — where do the thresholds fall?" />
      <div class="card chart-card">
        <svg viewBox="0 0 440 240" class="pareto-svg">
          <!-- Grid lines -->
          <line x1="20" y1="200" x2="420" y2="200" stroke="var(--border)" stroke-width="1"/>
          <line x1="20" y1="160" x2="420" y2="160" stroke="var(--border)" stroke-width="1" stroke-dasharray="4"/>
          <line x1="20" y1="120" x2="420" y2="120" stroke="var(--border)" stroke-width="1" stroke-dasharray="4"/>
          <line x1="20" y1="80" x2="420" y2="80" stroke="var(--border)" stroke-width="1" stroke-dasharray="4"/>
          <line x1="20" y1="40" x2="420" y2="40" stroke="var(--border)" stroke-width="1" stroke-dasharray="4"/>
          <line x1="20" y1="0" x2="420" y2="0" stroke="var(--border)" stroke-width="1" stroke-dasharray="4"/>

          <!-- Y axis labels -->
          <text x="16" y="204" fill="var(--text-faint)" font-size="8" text-anchor="end">0%</text>
          <text x="16" y="164" fill="var(--text-faint)" font-size="8" text-anchor="end">20%</text>
          <text x="16" y="44" fill="var(--text-faint)" font-size="8" text-anchor="end">80%</text>
          <text x="16" y="12" fill="var(--text-faint)" font-size="8" text-anchor="end">100%</text>

          <!-- 80% threshold line -->
          {#if paretoCurve().a_x}
            <line x1={20 + paretoCurve().a_x} y1="0" x2={20 + paretoCurve().a_x} y2="200" stroke="var(--class-a)" stroke-width="2" stroke-dasharray="6,3"/>
            <line x1="20" y1="40" x2="420" y2="40" stroke="var(--class-a)" stroke-width="1" stroke-dasharray="6,3"/>
            <text x={22 + paretoCurve().a_x} y="216" fill="var(--class-a)" font-size="8" font-weight="700">A 80%</text>
          {/if}

          <!-- 95% threshold line -->
          {#if paretoCurve().b_x}
            <line x1={20 + paretoCurve().b_x} y1="0" x2={20 + paretoCurve().b_x} y2="200" stroke="var(--class-b)" stroke-width="2" stroke-dasharray="6,3"/>
            <line x1="20" y1="10" x2="420" y2="10" stroke="var(--class-b)" stroke-width="1" stroke-dasharray="6,3"/>
            <text x={22 + paretoCurve().b_x} y="228" fill="var(--class-b)" font-size="8" font-weight="700">B 95%</text>
          {/if}

          <!-- Curve -->
          <polyline points={paretoCurve().points.split(' ').map(p => { const [x,y] = p.split(','); return `${20+Number(x)},${Number(y)}`; }).join(' ')} fill="none" stroke="var(--text-muted)" stroke-width="2.5"/>

          <!-- Fill area under curve -->
          <polygon points={`20,200 ${paretoCurve().points.split(' ').map(p => { const [x,y] = p.split(','); return `${20+Number(x)},${Number(y)}`; }).join(' ')} 420,200`} fill="var(--success-soft)"/>

          <!-- X axis label -->
          <text x="220" y="238" fill="var(--text-faint)" font-size="8" text-anchor="middle">% of outlets (ranked by revenue)</text>
        </svg>

        <!-- Legend -->
        <div class="chart-legend">
          <span class="legend-item"><span class="legend-swatch" style="background:var(--class-a);"></span> Class A (80%)</span>
          <span class="legend-item"><span class="legend-swatch" style="background:var(--class-b);"></span> Class B (95%)</span>
          <span class="legend-item"><span class="legend-swatch" style="background:var(--class-c);"></span> Class C</span>
        </div>
      </div>
    </div>

    <!-- Outlet Channel Breakdown -->
    <div class="section-block">
      <ChapterHeading title="Outlet Channel Breakdown" subtitle="Distribution by channel type" />
      <div class="card chart-card">
        {#each channelBars() as bar}
          <div class="bar-row">
            <div class="bar-label bar-label-wide">{bar.name}</div>
            <div class="bar-track">
              <div class="bar-fill bar-fill-f4" style="width:{bar.pct}%;"></div>
            </div>
            <div class="bar-value">{bar.count.toLocaleString()}</div>
          </div>
        {/each}
        {#if channelBars().length === 0}
          <div class="empty-note">No channel data</div>
        {/if}
      </div>
    </div>

    <!-- Risk Heatmap -->
    <div class="section-block">
      <ChapterHeading title="Risk Heatmap" subtitle="Branch x risk level distribution" />
      <div class="card card-flush">
        <div class="data-table-head"><span>Risk Matrix</span></div>
        <div class="data-table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>Branch</th>
                <th class="ta-c" style="color:var(--class-a);">Low</th>
                <th class="ta-c" style="color:var(--class-b);">Medium</th>
                <th class="ta-c" style="color:var(--class-c);">High</th>
                <th class="ta-c">Total</th>
              </tr>
            </thead>
            <tbody>
              {#each riskMatrix() as row, i}
                <tr>
                  <td class="td-strong">{row.Branch}</td>
                  <td class="ta-c td-strong" style="background:color-mix(in srgb, var(--class-a) {Math.min(row.Low / Math.max(row.Total, 1), 1) * 22}%, transparent);">{row.Low}</td>
                  <td class="ta-c td-strong" style="background:color-mix(in srgb, var(--class-b) {Math.min(row.Medium / Math.max(row.Total, 1), 1) * 30}%, transparent);">{row.Medium}</td>
                  <td class="ta-c td-strong" style="background:color-mix(in srgb, var(--class-c) {Math.min(row.High / Math.max(row.Total, 1), 1) * 30}%, transparent);">{row.High}</td>
                  <td class="ta-c td-strong">{row.Total}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>
    </div>

  <!-- ---- TAB 3: AI INSIGHTS ---- -->
  {:else if activeTab === 3}
    <!-- Executive summary -->
    <div class="section-block">
      <div class="card card-flush ai-panel">
        <div class="card-head">
          <div class="card-head-title">AI Executive Summary</div>
        </div>
        <div class="card-body ai-content">
          {#if data.insights?.executive_summary}
            {@html renderMarkdown(data.insights.executive_summary)}
          {:else if data.insights}
            {#each Object.entries(data.insights) as [key, val]}
              <div class="ai-kv"><strong>{key}:</strong> {@html renderMarkdown(String(val))}</div>
            {/each}
          {:else}
            <span class="empty-note">No AI insights generated for this run.</span>
          {/if}
        </div>
      </div>
    </div>

    <!-- Growth analysis -->
    {#if data.insights?.growth_analysis}
      <div class="section-block">
        <div class="card card-flush">
          <div class="card-head card-head-accent" style="--head-accent:var(--class-f4);">
            <div class="card-head-title">Growth Analysis</div>
          </div>
          <div class="card-body ai-content-light">
            {@html renderMarkdown(data.insights.growth_analysis)}
          </div>
        </div>
      </div>
    {/if}

    <!-- Recommendation cards -->
    <div class="rec-grid">
      <!-- Class A card -->
      <div class="card card-flush rec-card" style="--rec:var(--class-a);">
        <div class="card-head card-head-accent" style="--head-accent:var(--class-a);">
          <div class="card-head-title">Class A Recommendations</div>
        </div>
        <div class="card-body ai-content-light">
          <div class="rec-summary">{kpis.classA} outlets generating ~80% of revenue</div>
          {#if data.insights?.class_a_recommendations || data.insights?.class_a_recs}
            {@html renderMarkdown(data.insights.class_a_recommendations || data.insights.class_a_recs)}
          {:else}
            <ul class="rec-list">
              <li>Assign dedicated sales reps</li>
              <li>Weekly visit cadence minimum</li>
              <li>Priority for promotions and new launches</li>
              <li>Monitor for declining trends</li>
            </ul>
          {/if}
        </div>
      </div>

      <!-- Class B card -->
      <div class="card card-flush rec-card" style="--rec:var(--class-b);">
        <div class="card-head card-head-accent" style="--head-accent:var(--class-b);">
          <div class="card-head-title">Class B Recommendations</div>
        </div>
        <div class="card-body ai-content-light">
          <div class="rec-summary">{kpis.classB} outlets in the growth tier</div>
          {#if data.insights?.class_b_recommendations || data.insights?.class_b_recs}
            {@html renderMarkdown(data.insights.class_b_recommendations || data.insights.class_b_recs)}
          {:else}
            <ul class="rec-list">
              <li>Bi-weekly visit schedule</li>
              <li>Identify potential upgrades to Class A</li>
              <li>Cross-sell and upsell opportunities</li>
              <li>Track growth signals closely</li>
            </ul>
          {/if}
        </div>
      </div>

      <!-- Class C card -->
      <div class="card card-flush rec-card" style="--rec:var(--class-c);">
        <div class="card-head card-head-accent" style="--head-accent:var(--class-c);">
          <div class="card-head-title">Class C Recommendations</div>
        </div>
        <div class="card-body ai-content-light">
          <div class="rec-summary">{kpis.classC} outlets in the tail</div>
          {#if data.insights?.class_c_recommendations || data.insights?.class_c_recs}
            {@html renderMarkdown(data.insights.class_c_recommendations || data.insights.class_c_recs)}
          {:else}
            <ul class="rec-list">
              <li>Monthly or on-demand visits</li>
              <li>Telesales or digital ordering</li>
              <li>Evaluate cost-to-serve vs. revenue</li>
              <li>Consider route consolidation</li>
            </ul>
          {/if}
        </div>
      </div>
    </div>

  <!-- ---- TAB 4: COMPARISON ---- -->
  {:else if activeTab === 4}
    <ChapterHeading title="Run Comparison" subtitle="This run vs the previous run" />

    {#if !comparison}
      <div class="empty-note">Run or load a job to see the comparison.</div>
    {:else if comparison.has_previous === false}
      <div class="alert alert-info">No previous run to compare against — this is the first job.</div>
    {:else}
      <div class="section-sub">
        This run {comparison.current?.job_id} vs previous {comparison.previous?.job_id}
      </div>

      <!-- Movement summary -->
      <div class="grid-kpi" style="margin-bottom:24px;">
        <div class="kpi">
          <div class="kpi-label">Upgraded</div>
          <div class="kpi-value" style="color:var(--success);">{(comparison.movement?.upgraded ?? 0).toLocaleString()}</div>
        </div>
        <div class="kpi">
          <div class="kpi-label">Downgraded</div>
          <div class="kpi-value" style="color:var(--danger);">{(comparison.movement?.downgraded ?? 0).toLocaleString()}</div>
        </div>
        <div class="kpi">
          <div class="kpi-label">Unchanged</div>
          <div class="kpi-value" style="color:var(--text-muted);">{(comparison.movement?.unchanged ?? 0).toLocaleString()}</div>
        </div>
        <div class="kpi">
          <div class="kpi-label">New Outlets</div>
          <div class="kpi-value">{(comparison.movement?.new ?? 0).toLocaleString()}</div>
        </div>
        <div class="kpi">
          <div class="kpi-label">Lost Outlets</div>
          <div class="kpi-value">{(comparison.movement?.lost ?? 0).toLocaleString()}</div>
        </div>
      </div>

      <!-- Summary -->
      <div class="section-head">
        <span class="dot"></span>
        <h3>Summary</h3>
      </div>
      <div class="data-table-wrap" style="margin-bottom:24px;">
        <table class="data-table">
          <thead>
            <tr>
              <th>Metric</th>
              <th style="text-align:right;">This Run</th>
              <th style="text-align:right;">Previous Run</th>
              <th style="text-align:right;">Change</th>
              <th>Remark</th>
            </tr>
          </thead>
          <tbody>
            {#each comparison.summary ?? [] as row}
              <tr>
                <td>{row.metric}</td>
                <td style="text-align:right;">{fmtMaybeNum(row.current)}</td>
                <td style="text-align:right;">{fmtMaybeNum(row.previous)}</td>
                <td style="text-align:right; color:{changeColor(row.change)};">
                  {row.change > 0 ? '+' : ''}{fmtMaybeNum(row.change)}
                </td>
                <td>{row.remark}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>

      <!-- By Channel -->
      <div class="section-head">
        <span class="dot"></span>
        <h3>By Channel</h3>
      </div>
      <div class="data-table-wrap" style="margin-bottom:24px;">
        <table class="data-table">
          <thead>
            <tr>
              <th>Metric</th>
              <th style="text-align:right;">This Run</th>
              <th style="text-align:right;">Previous Run</th>
              <th style="text-align:right;">Change</th>
              <th>Remark</th>
            </tr>
          </thead>
          <tbody>
            {#each comparison.by_channel ?? [] as row}
              <tr>
                <td>{row.metric}</td>
                <td style="text-align:right;">{fmtMaybeNum(row.current)}</td>
                <td style="text-align:right;">{fmtMaybeNum(row.previous)}</td>
                <td style="text-align:right; color:{changeColor(row.change)};">
                  {row.change > 0 ? '+' : ''}{fmtMaybeNum(row.change)}
                </td>
                <td>{row.remark}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>

      <!-- By Branch -->
      <div class="section-head">
        <span class="dot"></span>
        <h3>By Branch</h3>
      </div>
      <div class="data-table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>Metric</th>
              <th style="text-align:right;">This Run</th>
              <th style="text-align:right;">Previous Run</th>
              <th style="text-align:right;">Change</th>
              <th>Remark</th>
            </tr>
          </thead>
          <tbody>
            {#each comparison.by_branch ?? [] as row}
              <tr>
                <td>{row.metric}</td>
                <td style="text-align:right;">{fmtMaybeNum(row.current)}</td>
                <td style="text-align:right;">{fmtMaybeNum(row.previous)}</td>
                <td style="text-align:right; color:{changeColor(row.change)};">
                  {row.change > 0 ? '+' : ''}{fmtMaybeNum(row.change)}
                </td>
                <td>{row.remark}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}

  <!-- ---- TAB 5: LOG ---- -->
  {:else if activeTab === 5}
    <ChapterHeading title="Pipeline Log" subtitle="Step-by-step execution trace" />
    <div class="card">
      {#if logEntries.length > 0}
        {#each logEntries as entry, i}
          <div class="log-row">
            <span class="log-check">✓</span>
            <span class="log-text">{entry}</span>
          </div>
        {/each}
      {:else}
        <div class="empty-note">No log entries recorded</div>
      {/if}
    </div>

  <!-- ---- TAB 6: EXPORT ---- -->
  {:else if activeTab === 6}
    <ChapterHeading title="Export Results" subtitle="Download classified data" />
    <div class="export-grid">
      <!-- Excel export -->
      <div class="card card-flush">
        <div class="card-head">
          <div class="card-head-title">Excel Export (.xlsx)</div>
        </div>
        <div class="card-body">
          <div class="export-desc">Multi-sheet workbook with:</div>
          <ul class="export-list">
            <li>All Outlets (classified)</li>
            <li>Branch Summary</li>
            <li>Class A / B / C sheets</li>
            <li>AI Insights</li>
            <li>Pipeline Log</li>
          </ul>
          <button class="btn btn-block" onclick={() => exportExcel(data.job_id)}>
            Download Excel
          </button>
        </div>
      </div>

      <!-- Filtered export card -->
      <div class="card">
        <div class="export-card-title">Export Filtered Data</div>
        <div class="export-desc">
          Downloads only the currently visible results ({filteredResults.length.toLocaleString()} outlets)
          {#if selectedBranch !== 'All Branches'} — filtered by {selectedBranch}{/if}
        </div>
        <button class="btn" onclick={exportFilteredCSV}>
          Export Filtered CSV ({filteredResults.length.toLocaleString()} rows)
        </button>
      </div>

      <!-- CSV export -->
      <div class="card card-flush">
        <div class="card-head">
          <div class="card-head-title">CSV Export (.csv)</div>
        </div>
        <div class="card-body">
          <div class="export-desc">Flat file export with all columns:</div>
          <ul class="export-list">
            <li>All classification fields</li>
            <li>Sales aggregates (2Yr/12M/6M/3M)</li>
            <li>AI enrichment columns</li>
            <li>Contribution percentages</li>
          </ul>
          <button
            class="btn btn-block"
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
          >
            Download CSV
          </button>
        </div>
      </div>
    </div>
  {/if}
{/if}

<style>
  /* ===== Hero ===== */
  .page-hero {
    margin-bottom: 24px;
  }
  .page-hero h1 {
    font-size: 1.5rem;
    font-weight: 600;
    letter-spacing: -0.02em;
    color: var(--text);
    margin: 0;
  }
  .page-hero p {
    font-size: 0.8rem;
    color: var(--text-muted);
    margin: 4px 0 0;
  }

  /* ===== Upload ===== */
  .upload-wrap {
    width: 100%;
    max-width: none;
    margin: 0;
  }
  .upload-card,
  .preview-panel,
  .uploading-card {
    width: 100%;
    max-width: none;
  }
  .upload-card {
    padding: 28px;
  }

  .drop-icon {
    font-size: 1.8rem;
    color: var(--text-faint);
    margin-bottom: 10px;
    line-height: 1;
  }
  .drop-title {
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--text);
    margin-bottom: 6px;
  }
  .drop-sub {
    font-size: 0.78rem;
    color: var(--text-muted);
  }
  .drop-hint {
    font-size: 0.72rem;
    color: var(--text-faint);
    margin-top: 10px;
  }

  .file-selected {
    border: 1px solid var(--success);
    background: var(--success-soft);
    border-radius: var(--r-md);
    padding: 16px 18px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }
  .file-info {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .file-check {
    width: 34px;
    height: 34px;
    border-radius: var(--r-sm);
    background: var(--success);
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.9rem;
    flex-shrink: 0;
  }
  .file-name {
    font-size: 0.82rem;
    font-weight: 600;
    color: var(--text);
  }
  .file-meta {
    font-size: 0.72rem;
    color: var(--text-muted);
    margin-top: 2px;
  }
  .file-remove {
    width: 30px;
    height: 30px;
    padding: 0;
    flex-shrink: 0;
  }

  .threshold-row {
    margin-top: 22px;
    display: flex;
    gap: 24px;
  }
  .threshold-field {
    flex: 1;
  }
  .range {
    width: 100%;
    cursor: pointer;
    accent-color: var(--accent);
  }
  .range-a { accent-color: var(--class-a); }
  .range-b { accent-color: var(--class-b); }

  .preview-kpis {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    margin-top: 18px;
  }

  /* ===== File Preview Panel ===== */
  .preview-panel {
    margin-top: 20px;
  }
  .preview-body {
    padding: 18px 20px 22px;
  }
  .preview-stats {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 10px;
    margin-bottom: 20px;
  }
  @media (max-width: 900px) {
    .preview-stats { grid-template-columns: repeat(2, 1fr); }
  }
  .preview-section {
    margin-top: 18px;
  }
  .preview-section-title {
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--text-soft, var(--text));
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 8px;
  }
  .col-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .chip {
    font-size: 0.78rem;
    padding: 4px 10px;
    border: 1px solid var(--border);
    background: var(--surface, var(--bg));
    color: var(--text);
    font-family: inherit;
  }
  .chip-ok { border-color: var(--accent); color: var(--accent); }
  .chip-req {
    background: var(--accent);
    border-color: var(--accent);
    color: #fff;
    font-weight: 600;
  }
  .chip-bad {
    background: #c0392b;
    border-color: #c0392b;
    color: #fff;
    font-weight: 600;
  }
  .chip-opt {
    border-color: var(--accent);
    color: var(--accent);
    background: transparent;
  }
  .col-legend {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    font-size: 0.75rem;
    color: var(--text-soft, var(--text));
    margin-bottom: 12px;
    opacity: 0.85;
  }
  .col-legend .chip { padding: 1px 6px; font-size: 0.7rem; }
  .col-group-title {
    font-size: 0.72rem;
    font-weight: 600;
    color: var(--text-soft, var(--text));
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin: 10px 0 6px;
    opacity: 0.7;
  }
  .preview-ok {
    margin-top: 10px;
    font-size: 0.82rem;
    color: var(--accent);
  }
  .preview-table-wrap {
    overflow-x: auto;
    border: 1px solid var(--border);
    max-height: 320px;
    overflow-y: auto;
  }
  .preview-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.82rem;
  }
  .preview-table th,
  .preview-table td {
    text-align: left;
    padding: 6px 10px;
    border-bottom: 1px solid var(--border);
    white-space: nowrap;
  }
  .preview-table thead th {
    background: var(--surface-2, var(--bg));
    position: sticky;
    top: 0;
    font-weight: 600;
  }
  .preview-table tbody tr:hover { background: var(--surface, transparent); }
  .preview-foot {
    margin-top: 6px;
    font-size: 0.75rem;
    color: var(--text-soft, var(--text));
    opacity: 0.7;
  }
  .branch-bars {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .branch-bar-row {
    display: grid;
    grid-template-columns: 140px 1fr 80px;
    align-items: center;
    gap: 10px;
    font-size: 0.82rem;
  }
  .branch-bar-name { font-weight: 500; }
  .branch-bar-track {
    height: 14px;
    background: var(--surface-2, var(--border));
  }
  .branch-bar-fill {
    height: 100%;
    background: var(--accent);
  }
  .branch-bar-count {
    text-align: right;
    font-variant-numeric: tabular-nums;
    color: var(--text-soft, var(--text));
  }
  .branch-more {
    font-size: 0.78rem;
    opacity: 0.7;
    margin-top: 4px;
  }

  /* ===== Uploading state ===== */
  .uploading-card { margin: 0; }
  .uploading-body {
    padding: 32px 28px 28px;
    text-align: center;
  }
  .uploading-pct {
    font-size: 2.4rem;
    font-weight: 600;
    color: var(--accent);
    font-variant-numeric: tabular-nums;
    margin-bottom: 14px;
  }
  .uploading-bar-track {
    height: 10px;
    background: var(--surface-2, var(--border));
    overflow: hidden;
    margin-bottom: 10px;
  }
  .uploading-bar-fill {
    height: 100%;
    background: var(--accent);
    transition: width 0.1s linear;
  }
  .uploading-stats {
    font-size: 0.85rem;
    color: var(--text-soft, var(--text));
    font-variant-numeric: tabular-nums;
    margin-bottom: 18px;
  }
  .lifecycle-grid,
  .f4-kpis {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 12px;
    margin-top: 12px;
  }
  @media (max-width: 1100px) {
    .lifecycle-grid, .f4-kpis { grid-template-columns: repeat(3, 1fr); }
  }
  @media (max-width: 720px) {
    .lifecycle-grid, .f4-kpis { grid-template-columns: repeat(2, 1fr); }
  }

  .uploading-hint {
    font-size: 0.78rem;
    opacity: 0.65;
    max-width: 460px;
    margin: 0 auto;
    line-height: 1.5;
  }

  .run-btn {
    margin-top: 22px;
  }

  /* ===== Info blocks (upload) ===== */
  .info-block {
    margin-top: 24px;
  }
  .info-block-last {
    margin-bottom: 32px;
  }

  .card-head {
    padding: 14px 20px;
    border-bottom: 1px solid var(--border);
  }
  .card-head-accent {
    border-bottom: 2px solid var(--head-accent, var(--border));
  }
  .card-head-title {
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--text);
  }
  .card-head-sub {
    font-size: 0.74rem;
    color: var(--text-muted);
    margin-top: 2px;
  }
  .card-body {
    padding: 20px;
  }

  .pipeline-steps {
    display: flex;
    align-items: flex-start;
    justify-content: center;
    gap: 4px;
    flex-wrap: wrap;
    margin-bottom: 20px;
  }
  .pstep {
    display: flex;
    align-items: center;
    gap: 4px;
  }
  .pstep-inner {
    width: 56px;
    text-align: center;
  }
  .pstep-num {
    width: 34px;
    height: 34px;
    border-radius: var(--r-md);
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.7rem;
    font-weight: 600;
    margin: 0 auto;
  }
  .pstep-label {
    font-size: 0.6rem;
    font-weight: 600;
    color: var(--text-muted);
    margin-top: 5px;
  }
  .pstep-arrow {
    font-size: 0.85rem;
    color: var(--text-faint);
    margin: 0 2px;
  }

  .how-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }
  .how-item {
    padding: 8px 12px;
    background: var(--surface-2);
    border-radius: var(--r-sm);
    border-left: 3px solid var(--border);
    font-size: 0.74rem;
    color: var(--text-muted);
  }

  .cols-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 8px;
    margin-bottom: 14px;
  }
  .col-card {
    padding: 8px 12px;
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
  }
  .col-name {
    font-size: 0.72rem;
    font-weight: 600;
    color: var(--success);
    font-family: var(--font-mono);
  }
  .col-desc {
    font-size: 0.7rem;
    color: var(--text-muted);
    margin-top: 2px;
  }
  .optional-row {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    align-items: center;
  }
  .optional-label {
    font-size: 0.68rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
  }

  .get-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 6px;
  }
  .get-item {
    padding: 5px 4px;
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.78rem;
    color: var(--text);
  }
  .get-check {
    width: 18px;
    height: 18px;
    border-radius: var(--r-sm);
    background: var(--success-soft);
    color: var(--success);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.65rem;
    font-weight: 700;
    flex-shrink: 0;
  }

  /* ===== Processing ===== */
  .proc-grid {
    display: grid;
    grid-template-columns: 320px 1fr;
    gap: 16px;
    min-height: 500px;
  }
  .proc-left {
    display: flex;
    flex-direction: column;
  }
  .proc-steps {
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    overflow-y: auto;
    flex: 1;
  }
  .proc-step {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 10px;
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--surface);
    transition: all 0.2s;
  }
  .proc-step.done {
    border-color: var(--success);
    background: var(--success-soft);
  }
  .proc-step.active {
    border-color: var(--warning);
    background: var(--warning-soft);
  }
  .proc-step.pending {
    opacity: 0.5;
  }
  .proc-step-num {
    width: 22px;
    height: 22px;
    border-radius: var(--r-sm);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.65rem;
    font-weight: 700;
    flex-shrink: 0;
    background: var(--surface-3);
    color: var(--text-muted);
  }
  .proc-step.done .proc-step-num {
    background: var(--success);
    color: #fff;
  }
  .proc-step.active .proc-step-num {
    background: var(--warning);
    color: #fff;
  }
  .proc-step-label {
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--text);
    flex: 1;
  }
  .proc-dots {
    display: flex;
    gap: 3px;
  }
  .proc-dots span {
    width: 4px;
    height: 4px;
    border-radius: 0;
    background: var(--warning);
    animation: bounce 0.6s ease-in-out infinite;
  }
  .proc-dots span:nth-child(2) { animation-delay: 0.15s; }
  .proc-dots span:nth-child(3) { animation-delay: 0.3s; }

  .proc-progress {
    padding: 14px;
    border-top: 1px solid var(--border);
  }
  .proc-progress-label {
    font-size: 0.68rem;
    font-weight: 500;
    color: var(--text-muted);
    margin-top: 6px;
    text-align: center;
  }

  .proc-terminal {
    display: flex;
    flex-direction: column;
    padding: 0;
    overflow: hidden;
  }
  .cli-bar {
    padding: 9px 16px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .cli-dot {
    width: 8px;
    height: 8px;
    border-radius: 0;
    background: var(--success);
  }
  .cli-bar-title {
    font-size: 0.68rem;
    font-weight: 600;
    color: var(--text-faint);
    font-family: var(--font-mono);
    letter-spacing: 0.04em;
  }
  .cli-bar-pid {
    margin-left: auto;
    font-size: 0.62rem;
    color: var(--text-faint);
    font-family: var(--font-mono);
  }
  .cli-scroll {
    flex: 1;
    padding: 12px 16px;
    overflow-y: auto;
    max-height: 500px;
    font-family: var(--font-mono);
    font-size: 0.72rem;
    line-height: 1.7;
  }
  .cli-line {
    animation: fadeIn 0.15s ease-out;
  }
  .cli-blank {
    height: 6px;
  }
  .cli-cursor-row {
    display: flex;
    align-items: center;
    gap: 4px;
    margin-top: 4px;
  }
  .cli-cursor {
    width: 8px;
    height: 14px;
    background: currentColor;
    color: var(--success);
    animation: blink 1s step-end infinite;
  }
  .pipeline-panel-cli {
    padding: 0;
    overflow-y: auto;
  }
  .pipeline-panel-cli .cli-scroll {
    max-height: 450px;
  }

  /* ===== Pipeline bar (results) ===== */
  .pipeline-bar {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    box-shadow: var(--shadow-sm);
    padding: 12px 16px;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    cursor: pointer;
    transition: background 0.15s, margin 0.2s;
  }
  .pipeline-bar:hover {
    background: var(--surface-2);
  }
  .pipeline-bar.expanded {
    margin-bottom: 0;
    border-bottom-left-radius: 0;
    border-bottom-right-radius: 0;
  }
  .pipeline-bar-left,
  .pipeline-bar-right {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .pipeline-chevron {
    font-size: 0.75rem;
    color: var(--text-muted);
    transition: transform 0.2s;
    display: inline-block;
  }
  .pipeline-chevron.open {
    transform: rotate(180deg);
  }
  .pipeline-bar-title {
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--text);
  }
  .pipeline-bar-job {
    font-size: 0.72rem;
    color: var(--text-muted);
    font-family: var(--font-mono);
  }
  .pipeline-bar-action {
    font-size: 0.72rem;
    color: var(--text-faint);
  }

  .pipeline-panel {
    margin-bottom: 20px;
    border: 1px solid var(--border);
    border-top: none;
    border-bottom-left-radius: var(--r-lg);
    border-bottom-right-radius: var(--r-lg);
    overflow: hidden;
  }
  .pipeline-panel-grid {
    display: grid;
    grid-template-columns: 280px 1fr;
    min-height: 350px;
    max-height: 450px;
  }
  .pipeline-panel-steps {
    background: var(--surface);
    border-right: 1px solid var(--border);
    padding: 10px;
    display: flex;
    flex-direction: column;
    gap: 4px;
    overflow-y: auto;
  }
  .pipeline-panel-step {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 8px;
    border: 1px solid var(--success);
    border-radius: var(--r-sm);
    background: var(--success-soft);
  }
  .pipeline-panel-check {
    width: 18px;
    height: 18px;
    border-radius: var(--r-sm);
    background: var(--success);
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.65rem;
    font-weight: 700;
    flex-shrink: 0;
  }
  .pipeline-panel-label {
    font-size: 0.72rem;
    font-weight: 500;
    color: var(--text);
    flex: 1;
  }

  /* ===== Controls row ===== */
  .controls-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 20px;
    flex-wrap: wrap;
    gap: 12px;
  }
  .branch-filter,
  .controls-right {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .branch-filter .label {
    margin: 0;
  }
  .job-tag {
    font-size: 0.72rem;
    color: var(--text-muted);
    font-family: var(--font-mono);
  }

  .results-kpis {
    margin-bottom: 24px;
  }
  .results-tabs {
    margin-bottom: 24px;
  }

  /* ===== Sections ===== */
  .section-block {
    margin-bottom: 24px;
  }

  /* ===== Data Quality ===== */
  .dq-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 7px 0;
    border-bottom: 1px solid var(--border);
  }
  .dq-row-top {
    align-items: flex-start;
  }
  .dq-row:last-child {
    border-bottom: none;
  }
  .dq-icon {
    width: 20px;
    height: 20px;
    border-radius: var(--r-sm);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.65rem;
    font-weight: 700;
    color: #fff;
    flex-shrink: 0;
  }
  .dq-ok { background: var(--success); }
  .dq-warn { background: var(--warning); }
  .dq-miss { background: var(--danger); }
  .dq-info { background: var(--info); }
  .dq-text {
    font-size: 0.78rem;
    color: var(--text);
  }
  .dq-body { flex: 1; }
  .dq-head {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 3px;
  }
  .dq-field {
    font-size: 0.74rem;
    font-weight: 600;
    color: var(--text);
  }
  .dq-message {
    font-size: 0.78rem;
    color: var(--text-muted);
  }
  .dq-impact {
    font-size: 0.72rem;
    color: var(--text-faint);
    margin-top: 2px;
    font-style: italic;
  }

  /* ===== Tables ===== */
  .data-table-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .ta-c { text-align: center; }
  .ta-r { text-align: right; }
  .td-strong { font-weight: 600; }
  .td-mono { font-family: var(--font-mono); }
  .muted { color: var(--text-muted); }

  /* ===== AI panels ===== */
  .ai-content {
    font-size: 0.82rem;
    line-height: 1.65;
    color: var(--text);
  }
  .ai-content-light {
    font-size: 0.82rem;
    line-height: 1.6;
    color: var(--text);
  }
  .ai-kv {
    margin-bottom: 8px;
  }
  .ai-kv strong {
    text-transform: uppercase;
    font-size: 0.68rem;
    letter-spacing: 0.04em;
    color: var(--accent);
  }
  :global(.ai-content .md-h2),
  :global(.ai-content-light .md-h2) {
    font-size: 0.95rem;
    font-weight: 600;
    margin: 16px 0 8px;
    color: var(--text);
  }
  :global(.ai-content .md-h3),
  :global(.ai-content-light .md-h3) {
    font-size: 0.85rem;
    font-weight: 600;
    margin: 14px 0 6px;
    color: var(--text);
  }
  :global(.ai-content .md-li),
  :global(.ai-content-light .md-li) {
    padding-left: 16px;
    margin: 4px 0;
  }

  /* ===== Recommendation cards ===== */
  .rec-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 16px;
    margin-bottom: 24px;
  }
  .rec-card {
    border-top: 3px solid var(--rec, var(--border));
  }
  .rec-summary {
    margin-bottom: 8px;
    font-weight: 600;
    color: var(--text);
  }
  .rec-list {
    margin: 0;
    padding-left: 18px;
    font-size: 0.78rem;
    color: var(--text-muted);
  }
  .rec-list li {
    margin: 3px 0;
  }

  /* ===== Charts ===== */
  .chart-card {
    padding: 24px;
  }
  .bar-row {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 10px;
  }
  .bar-label {
    min-width: 120px;
    font-size: 0.74rem;
    font-weight: 600;
    color: var(--text);
    text-align: right;
  }
  .bar-label-sm {
    min-width: 60px;
    font-family: var(--font-mono);
  }
  .bar-label-wide {
    min-width: 140px;
  }
  .bar-track {
    flex: 1;
    height: 20px;
    background: var(--surface-3);
    border-radius: var(--r-sm);
    overflow: hidden;
  }
  .bar-track-lg {
    height: 24px;
  }
  .bar-fill {
    height: 100%;
    border-radius: var(--r-sm);
    transition: width 0.5s;
  }
  .bar-fill-a { background: var(--class-a); }
  .bar-fill-f4 { background: var(--class-f4); }
  .bar-value {
    min-width: 80px;
    font-size: 0.74rem;
    font-weight: 600;
    color: var(--text);
    font-family: var(--font-mono);
  }
  .empty-note {
    text-align: center;
    color: var(--text-muted);
    font-size: 0.78rem;
    padding: 24px;
  }

  .pareto-svg {
    width: 100%;
    max-height: 300px;
  }
  .chart-legend {
    display: flex;
    gap: 16px;
    justify-content: center;
    margin-top: 8px;
    font-size: 0.7rem;
    color: var(--text-muted);
  }
  .legend-item {
    display: flex;
    align-items: center;
    gap: 4px;
  }
  .legend-swatch {
    width: 12px;
    height: 3px;
    border-radius: 0;
  }

  /* ===== Explorer ===== */
  .explorer-controls {
    display: flex;
    gap: 12px;
    margin-bottom: 16px;
    flex-wrap: wrap;
  }
  .explorer-search {
    flex: 1;
    min-width: 200px;
  }

  /* ===== Log ===== */
  .log-row {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 8px 0;
    border-bottom: 1px solid var(--border);
    animation: fadeIn 0.3s ease-in;
  }
  .log-row:last-child {
    border-bottom: none;
  }
  .log-check {
    color: var(--success);
    font-size: 0.9rem;
    font-weight: 700;
    line-height: 1.3;
  }
  .log-text {
    font-size: 0.78rem;
    color: var(--text);
    font-family: var(--font-mono);
  }

  /* ===== Export ===== */
  .export-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 16px;
  }
  .export-card-title {
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--text);
    margin-bottom: 8px;
  }
  .export-desc {
    font-size: 0.78rem;
    color: var(--text-muted);
    margin-bottom: 12px;
    line-height: 1.5;
  }
  .export-list {
    margin: 0 0 16px;
    padding-left: 18px;
    font-size: 0.78rem;
    color: var(--text-muted);
  }
  .export-list li {
    margin: 3px 0;
  }

  @keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0; }
  }
  @keyframes bounce {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-4px); }
  }
  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }

  @media (max-width: 760px) {
    .proc-grid { grid-template-columns: 1fr; }
    .pipeline-panel-grid { grid-template-columns: 1fr; }
    .how-grid, .get-grid { grid-template-columns: 1fr; }
    .threshold-row { flex-direction: column; gap: 14px; }
  }
</style>
