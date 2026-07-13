<script lang="ts">
  import { classify, classifyAsync, getJobStatus, getJobResult, exportExcel, exportExcelWithProgress, getJob, getJobComparison, getRuleConfig, getUploadPreview, uploadFile, deleteUpload, getF4Analysis } from '$lib/api';
  import { page } from '$app/stores';
  import KpiCard from '$lib/components/KpiCard.svelte';
  import DataTable from '$lib/components/DataTable.svelte';
  import Badge from '$lib/components/Badge.svelte';
  import MultiSelect from '$lib/components/MultiSelect.svelte';
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

  // Compute preview stats from parsed rows (header row + data rows as arrays).
  // Shared by both the CSV and Excel parse paths so the preview is identical.
  function finalizePreview(headers: string[], dataRows: string[][], scale: number, sampled: boolean) {
    const idx = (name: string) => headers.indexOf(name);
    const iBranch = idx('BranchName');
    const iCode = idx('Cus.Code');
    const iDate = idx('DocDate');

    const branchMap = new Map<string, number>();
    const outletSet = new Set<string>();
    let minDate = '', maxDate = '';
    for (const row of dataRows) {
      if (iBranch >= 0) {
        const b = row[iBranch] || '(none)';
        branchMap.set(b, (branchMap.get(b) || 0) + 1);
      }
      if (iCode >= 0 && iBranch >= 0) outletSet.add(`${row[iBranch]}|${row[iCode]}`);
      if (iDate >= 0 && row[iDate]) {
        const d = String(row[iDate]);
        if (!minDate || d < minDate) minDate = d;
        if (!maxDate || d > maxDate) maxDate = d;
      }
    }

    const branches = [...branchMap.entries()]
      .map(([name, count]) => ({ name, count: Math.round(count * scale) }))
      .sort((a, b) => b.count - a.count);

    // Columns the engine doesn't know about are silently dropped on the backend,
    // so a typo'd header (Cus_Code vs Cus.Code) fails quietly. Surface them.
    const known = new Set([...REQUIRED_COLS, ...OPTIONAL_COLS]);
    const unknownCols = headers.filter(h => h && !known.has(h));

    preview = {
      headers,
      rows: dataRows,                       // every parsed row — the table pages through these
      parsedRows: dataRows.length,          // what we actually hold (< totalRows if sampled)
      totalRows: Math.round(dataRows.length * scale),
      branches,
      outletCount: Math.round(outletSet.size * scale),
      dateRange: minDate && maxDate ? (minDate === maxDate ? minDate : `${minDate} → ${maxDate}`) : '—',
      requiredMissing: REQUIRED_COLS.filter(c => !headers.includes(c)),
      optionalPresent: OPTIONAL_COLS.filter(c => headers.includes(c)),
      unknownCols,
      sampled,
    };
    previewPage = 0;
    previewSearch = '';
  }

  // ── Preview table: search + paging over the parsed rows ──
  let previewParsing = $state(false);
  let previewError = $state('');
  let sheetWarning = $state('');
  let previewFallback = $state(false);   // preview came from the server
  let previewUploading = $state(false);
  let previewUploadPct = $state(0);
  let previewUploadId = $state('');      // staged upload, reused by handleClassify
  let previewPage = $state(0);
  let previewSearch = $state('');
  const PREVIEW_PAGE_SIZE = 25;

  let previewRows = $derived.by(() => {
    const rows = preview?.rows ?? [];
    const q = previewSearch.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter(r => r.some(c => String(c ?? '').toLowerCase().includes(q)));
  });

  let previewPageCount = $derived(Math.max(1, Math.ceil(previewRows.length / PREVIEW_PAGE_SIZE)));
  let previewPageRows = $derived(
    previewRows.slice(previewPage * PREVIEW_PAGE_SIZE, previewPage * PREVIEW_PAGE_SIZE + PREVIEW_PAGE_SIZE)
  );

  // A new search can leave us past the end
  $effect(() => {
    if (previewPage >= previewPageCount) previewPage = 0;
  });

  // Cap on rows parsed from a workbook. A 100 MB+ .xlsx decompresses to a huge
  // XML sheet; reading it whole locks the tab (or OOMs) and the preview never
  // appears. SheetJS's sheetRows stops early, and !fullref still reports the
  // real dimensions — so the counts stay honest.
  const EXCEL_ROW_CAP = 20000;

  async function buildPreview(f: File) {
    preview = null;
    previewError = '';
    sheetWarning = '';
    previewFallback = false;
    previewUploadId = '';
    previewParsing = true;
    const isExcel = /\.xlsx?$/i.test(f.name);
    try {
      if (isExcel) {
        // SheetJS parses the binary workbook. Loaded on demand to keep the
        // initial bundle light — only pulled in when an Excel file is picked.
        const XLSX = await import('xlsx');
        const buf = await f.arrayBuffer();
        const wb = XLSX.read(buf, {
          type: 'array',
          dense: true,             // far less memory on wide/long sheets
          sheetRows: EXCEL_ROW_CAP + 1,   // + header
          cellDates: false,
          cellStyles: false,
          cellFormula: false,
        });
        // Sheet 0 isn't always a worksheet — it can be a chart/macro sheet, or
        // just empty. Find the first sheet that actually holds cells.
        const names: string[] = wb.SheetNames ?? [];
        if (!names.length) throw new Error('the workbook contains no sheets at all');

        const sheetIdx = names.findIndex(n => {
          const s = wb.Sheets[n];
          return s && (s as any)['!ref'];
        });
        if (sheetIdx < 0) {
          throw new Error(`no sheet contains any data (sheets: ${names.join(', ')})`);
        }
        const sheetName = names[sheetIdx];
        const ws = wb.Sheets[sheetName];

        // header:1 → array-of-arrays; defval keeps blank cells aligned.
        const grid = XLSX.utils.sheet_to_json<string[]>(ws, { header: 1, defval: '', raw: false });
        if (grid.length < 2) throw new Error(`sheet "${sheetName}" has no data rows`);
        const headers = (grid[0] as any[]).map(c => String(c ?? '').trim());
        const dataRows = (grid.slice(1) as any[][]).map(r => r.map(c => String(c ?? '')));

        // The backend reads the FIRST sheet (pd.read_excel with no sheet_name).
        // If the data isn't on sheet 1, the run will not see what this preview shows.
        sheetWarning = sheetIdx > 0
          ? `Data found on sheet "${sheetName}" (sheet ${sheetIdx + 1} of ${names.length}). `
            + `The classifier reads the FIRST sheet ("${names[0]}") — move the data there, or the run will not match this preview.`
          : '';

        // When sheetRows truncates, !fullref holds the sheet's true range —
        // use it so the row/outlet counts reflect the whole file, not the slice.
        let scale = 1;
        let sampled = false;
        const fullref = (ws as any)['!fullref'];
        if (fullref) {
          const totalRows = XLSX.utils.decode_range(fullref).e.r; // 0-based end row = data rows (header at 0)
          if (totalRows > dataRows.length) {
            scale = totalRows / dataRows.length;
            sampled = true;
          }
        }
        finalizePreview(headers, dataRows, scale, sampled);
        return;
      }

      // CSV path — slice first 8 MB to keep parse fast on huge files
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
      if (lines.length < 2) throw new Error('the file has no data rows');
      const headers = parseCsvLine(lines[0]);
      const dataRows = lines.slice(1).map(parseCsvLine);
      // Estimate total rows from full file size if sliced
      const scale = isSliced ? f.size / SLICE : 1;
      finalizePreview(headers, dataRows, scale, isSliced);
    } catch (e: any) {
      // The browser gave up. Big workbooks hold one enormous sheet XML that
      // SheetJS must materialise as a single JS string — past ~512 MB that is
      // impossible in V8, no matter the row cap. The server streams it fine,
      // so stage the file and let the backend build the preview.
      await serverPreview(f, e?.message);
    } finally {
      previewParsing = false;
    }
  }

  // Preview by staging the file and reading it on the server. The upload is
  // needed for the classification anyway, so it is not wasted work — handleClassify
  // reuses this upload_id instead of sending the file twice.
  async function serverPreview(f: File, clientReason?: string) {
    try {
      previewFallback = true;
      previewUploading = true;
      previewUploadPct = 0;
      const up = await uploadFile(f, (pct) => { previewUploadPct = pct; });
      previewUploading = false;
      previewUploadId = up.upload_id;

      const p = await getUploadPreview(up.upload_id, 200);
      const headers = p.headers ?? [];
      const known = new Set([...REQUIRED_COLS, ...OPTIONAL_COLS]);

      preview = {
        headers,
        rows: p.rows ?? [],
        parsedRows: p.parsed_rows ?? 0,
        totalRows: p.total_rows ?? 0,
        branches: [],
        outletCount: null,
        dateRange: '',
        requiredMissing: REQUIRED_COLS.filter(c => !headers.includes(c)),
        optionalPresent: OPTIONAL_COLS.filter(c => headers.includes(c)),
        unknownCols: headers.filter(h => h && !known.has(h)),
        sampled: (p.total_rows ?? 0) > (p.parsed_rows ?? 0),
        serverSide: true,
        sheetNames: p.sheet_names ?? [],
      };
      previewPage = 0;
      previewSearch = '';
      previewError = '';
    } catch (err: any) {
      previewUploading = false;
      previewFallback = false;
      previewError = `Could not read this file: ${clientReason ?? ''}`.trim()
        + ` — and the server preview also failed (${err?.message ?? 'unknown error'}).`;
    }
  }
  let data = $state(null);
  let exporting = $state(false);
  let exportError = $state('');
  let exportPct = $state(0);
  let exportPhase = $state('building');
  let exportMsg = $state('');
  let exportFiltered = $state(true);
  let comparison = $state(null);
  let error = $state('');
  let logEntries = $state([]);
  // Persist the branch filter to localStorage
  $effect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('rtm_branch_filter', JSON.stringify(fBranch));
    }
  });

  // Restore it once the data (and so the branch list) is loaded
  let branchRestored = false;
  $effect(() => {
    if (branchRestored || typeof window === 'undefined') return;
    if (state !== 'results' || branches.length === 0) return;
    branchRestored = true;
    const raw = localStorage.getItem('rtm_branch_filter');
    if (!raw) return;
    try {
      // Older builds stored a single branch name, not an array
      const saved = raw.startsWith('[') ? JSON.parse(raw) : [raw];
      const valid = saved.filter(b => branches.includes(b));
      if (valid.length) fBranch = valid;
    } catch {
      /* corrupt value — ignore and start unfiltered */
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


  // Warn user before refresh/close during upload or processing.
  // Upload XHR is in-flight in browser memory — refresh cancels it irrecoverably.
  // Processing IS recoverable (job runs server-side), but warning still useful.
  $effect(() => {
    if (typeof window === 'undefined') return;
    const handler = (e: BeforeUnloadEvent) => {
      if (state === 'uploading' || state === 'processing') {
        e.preventDefault();
        e.returnValue = state === 'uploading'
          ? 'Upload in progress — leaving will cancel it. Continue?'
          : 'Classification still running. Refreshing will reattach to it.';
        return e.returnValue;
      }
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  });

  // Check if there's a job ID in URL params on mount.
  // If the job is still running, resume polling instead of loading from history.
  $effect(() => {
    const jobId = $page.url.searchParams.get('job')
                  || (typeof window !== 'undefined' ? localStorage.getItem('rtm_active_job') : null);
    if (jobId && !data) {
      resumeOrLoadJob(jobId);
    }
  });

  async function resumeOrLoadJob(jobId: string) {
    try {
      const st = await getJobStatus(jobId);
      if (st.status === 'completed' && st.ready) {
        try { localStorage.removeItem('rtm_active_job'); } catch {}
        loadJob(jobId);
        return;
      }
      if (st.status === 'failed' || st.error) {
        try { localStorage.removeItem('rtm_active_job'); } catch {}
        return;
      }
      // Still running — resume polling + reattach to terminal
      state = 'processing';
      currentStep = st.step || 0;
      terminalLines = [
        '[RTM AGENT] Resuming in-progress job after refresh...',
        `[RTM AGENT] Job ID: ${jobId}`,
        '',
        ...(st.log || [])
      ];
      let lastLogLen = (st.log || []).length;
      while (true) {
        await new Promise(r => setTimeout(r, 2000));
        const s = await getJobStatus(jobId);
        if (s.log && s.log.length > lastLogLen) {
          terminalLines = [...terminalLines, ...s.log.slice(lastLogLen)];
          lastLogLen = s.log.length;
          setTimeout(() => {
            const el = document.getElementById('terminal-scroll');
            if (el) el.scrollTop = el.scrollHeight;
          }, 50);
        }
        currentStep = s.step || currentStep;
        if (s.status === 'failed' || s.error) {
          throw new Error(s.error || s.message || 'Classification failed');
        }
        if (s.ready) break;
      }
      data = await getJobResult(jobId);
      try { localStorage.removeItem('rtm_active_job'); } catch {}
      logEntries = data.log || [];
      currentStep = 10;
      state = 'results';
      if (data?.job_id) {
        getF4Analysis(data.job_id).then(r => f4Data = r).catch(() => f4Data = null);
      }
    } catch (e: any) {
      try { localStorage.removeItem('rtm_active_job'); } catch {}
      error = e.message || 'Failed to resume job';
      state = 'upload';
    }
  }

  // Show the rules the engine will actually use (it always runs on the /rules config)
  let ruleCfg = $state(null);
  $effect(() => {
    getRuleConfig().then(c => { ruleCfg = c; }).catch(() => {});
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

  // ── Filters ──────────────────────────────────────────────────────────────
  // Every KPI card and every tab reads filteredResults, so this is the single
  // place that decides what the page is showing.
  // Each filter is a list of accepted values. Empty list = "All" — it never narrows.
  const ALL = 'All';
  let fBranch = $state([]);
  let fClass = $state([]);
  let fLifecycle = $state([]);
  let fRisk = $state([]);
  let fGrowth = $state([]);
  let fPriority = $state([]);
  let fCategory = $state([]);
  let fPrincipal = $state([]);
  let fTownship = $state([]);
  let fRoute = $state([]);
  let fRevMin = $state('');
  let fRevMax = $state('');
  let fGrowthMin = $state('');
  let fGrowthMax = $state('');
  let fSearch = $state('');
  let showMore = $state(false);

  const uniq = (rows, key) =>
    [...new Set(rows.map(r => r[key]).filter(v => v !== null && v !== undefined && v !== '' && String(v) !== 'nan'))]
      .sort((a, b) => String(a).localeCompare(String(b), undefined, { numeric: true }));

  let branches = $derived(data ? uniq(data.results, 'BranchName') : []);
  let classes = $derived(data ? uniq(data.results, 'Classification') : []);
  let lifecycles = $derived(data ? uniq(data.results, 'Lifecycle_Stage') : []);
  let risks = $derived(data ? uniq(data.results, 'AI_Risk_Level') : []);
  let growths = $derived(data ? uniq(data.results, 'AI_Growth_Signal') : []);
  let priorities = $derived(data ? uniq(data.results, 'AI_Visit_Priority') : []);
  let categories = $derived(data ? uniq(data.results, 'SalesGroup') : []);
  let principals = $derived(data ? uniq(data.results, 'Principal') : []);
  let townships = $derived(data ? uniq(data.results, 'Township') : []);
  let routes = $derived(data ? uniq(data.results, 'RouteCode') : []);

  const num = (v) => {
    const n = parseFloat(v);
    return Number.isFinite(n) ? n : null;
  };

  // Within one filter the selected values are OR'd; across filters they are AND'd.
  const pick = (rows, sel, key) =>
    sel.length ? rows.filter(r => sel.includes(r[key])) : rows;

  let filteredResults = $derived.by(() => {
    let rows = data?.results ?? [];
    rows = pick(rows, fBranch, 'BranchName');
    rows = pick(rows, fClass, 'Classification');
    rows = pick(rows, fLifecycle, 'Lifecycle_Stage');
    rows = pick(rows, fRisk, 'AI_Risk_Level');
    rows = pick(rows, fGrowth, 'AI_Growth_Signal');
    rows = pick(rows, fCategory, 'SalesGroup');
    rows = pick(rows, fPrincipal, 'Principal');
    rows = pick(rows, fTownship, 'Township');
    rows = pick(rows, fRoute, 'RouteCode');
    if (fPriority.length) {
      const want = fPriority.map(String);
      rows = rows.filter(r => want.includes(String(r.AI_Visit_Priority)));
    }

    const rmin = num(fRevMin), rmax = num(fRevMax);
    if (rmin !== null) rows = rows.filter(r => (r.TotalSales_2Yr ?? 0) >= rmin);
    if (rmax !== null) rows = rows.filter(r => (r.TotalSales_2Yr ?? 0) <= rmax);

    const gmin = num(fGrowthMin), gmax = num(fGrowthMax);
    if (gmin !== null) rows = rows.filter(r => (r.Growth_6M_vs_12M ?? 0) >= gmin);
    if (gmax !== null) rows = rows.filter(r => (r.Growth_6M_vs_12M ?? 0) <= gmax);

    const q = fSearch.trim().toLowerCase();
    if (q) {
      rows = rows.filter(r =>
        String(r['Cus.Code'] ?? '').toLowerCase().includes(q) ||
        String(r['Cus.Name'] ?? '').toLowerCase().includes(q)
      );
    }
    return rows;
  });

  // Active filters, as individually removable chips — one chip per selected value
  let activeChips = $derived.by(() => {
    const c = [];
    const add = (prefix, sel, drop) => {
      for (const v of sel) {
        c.push({ label: prefix ? `${prefix}: ${v}` : String(v), clear: () => drop(v) });
      }
    };
    add('', fBranch, v => (fBranch = fBranch.filter(x => x !== v)));
    add('', fClass, v => (fClass = fClass.filter(x => x !== v)));
    add('Lifecycle', fLifecycle, v => (fLifecycle = fLifecycle.filter(x => x !== v)));
    add('Risk', fRisk, v => (fRisk = fRisk.filter(x => x !== v)));
    add('Growth', fGrowth, v => (fGrowth = fGrowth.filter(x => x !== v)));
    add('Priority', fPriority, v => (fPriority = fPriority.filter(x => x !== v)));
    add('', fCategory, v => (fCategory = fCategory.filter(x => x !== v)));
    add('', fPrincipal, v => (fPrincipal = fPrincipal.filter(x => x !== v)));
    add('', fTownship, v => (fTownship = fTownship.filter(x => x !== v)));
    add('Route', fRoute, v => (fRoute = fRoute.filter(x => x !== v)));

    if (num(fRevMin) !== null) c.push({ label: `Rev ≥ ${fmtCompact(num(fRevMin))}`, clear: () => (fRevMin = '') });
    if (num(fRevMax) !== null) c.push({ label: `Rev ≤ ${fmtCompact(num(fRevMax))}`, clear: () => (fRevMax = '') });
    if (num(fGrowthMin) !== null) c.push({ label: `Growth ≥ ${fGrowthMin}%`, clear: () => (fGrowthMin = '') });
    if (num(fGrowthMax) !== null) c.push({ label: `Growth ≤ ${fGrowthMax}%`, clear: () => (fGrowthMax = '') });
    if (fSearch.trim()) c.push({ label: `"${fSearch.trim()}"`, clear: () => (fSearch = '') });
    return c;
  });

  // Count of filters hidden behind the "More" popover
  let moreCount = $derived(
    [fGrowth, fPriority, fCategory, fPrincipal, fTownship, fRoute].filter(a => a.length).length
    + [fRevMin, fRevMax, fGrowthMin, fGrowthMax].filter(v => num(v) !== null).length
    + (fSearch.trim() ? 1 : 0)
  );

  function clearFilters() {
    fBranch = []; fClass = []; fLifecycle = []; fRisk = [];
    fGrowth = []; fPriority = []; fCategory = [];
    fPrincipal = []; fTownship = []; fRoute = [];
    fRevMin = fRevMax = fGrowthMin = fGrowthMax = '';
    fSearch = '';
  }

  function fmtCompact(n) {
    if (n >= 1e9) return (n / 1e9).toFixed(1) + 'B';
    if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
    if (n >= 1e3) return (n / 1e3).toFixed(0) + 'K';
    return String(n);
  }

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
    if (previewUploadId) {
      // The server-side preview already staged this exact file — don't send it twice.
      uploaded = { upload_id: previewUploadId };
      uploadId = previewUploadId;
      uploadPct = 100;
      uploadLoaded = file.size;
    } else {
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

    function scrollTerminal() {
      setTimeout(() => {
        const el = document.getElementById('terminal-scroll');
        if (el) el.scrollTop = el.scrollHeight;
      }, 50);
    }

    // Real backend log streams via polling — no fake hardcoded animation.
    // (Kept stepInterval var as no-op so existing clearInterval calls are safe.)
    const stepInterval = setInterval(() => {}, 60000);

    const typeInterval = 0; // unused, kept for clearInterval compat

    try {
      // Kick off async background job — returns instantly
      const { job_id } = await classifyAsync(uploaded.upload_id);
      // Persist job_id so a refresh resumes polling instead of losing state
      try {
        localStorage.setItem('rtm_active_job', job_id);
        const url = new URL(window.location.href);
        url.searchParams.set('job', job_id);
        window.history.replaceState({}, '', url);
      } catch {}
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
      try { localStorage.removeItem('rtm_active_job'); } catch {}
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
    // Validate: must be .csv, .xlsx or .xls
    if (!/\.(csv|xlsx|xls)$/i.test(selected.name)) {
      fileError = 'Invalid file type — only .csv, .xlsx and .xls files accepted';
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
    clearFilters();
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

  // Full-dataset CSV — all rows, all columns (union of keys across rows),
  // RFC-4180 escaping. Mirrors the Excel "All Results" sheet in flat form.
  async function downloadExcel() {
    if (!data?.job_id) { exportError = 'No job loaded.'; return; }
    exporting = true;
    exportError = '';
    exportPct = 0;
    exportPhase = 'building';
    exportMsg = 'Starting…';
    try {
      const codes = exportFiltered && activeChips.length
        ? filteredResults.map(r => String(r['Cus.Code']))
        : null;
      await exportExcelWithProgress(data.job_id, (p) => {
        exportPhase = p.phase;
        exportPct = p.percent;
        exportMsg = p.phase === 'downloading' && p.total
          ? `Downloading — ${fmtMB(p.loaded)} / ${fmtMB(p.total)} MB`
          : p.message;
      }, codes);
    } catch (e) {
      exportError = e?.message === 'Session expired'
        ? 'Session expired — sign in again.'
        : `Export failed: ${e?.message ?? 'unknown error'}`;
    } finally {
      exporting = false;
    }
  }

  function fmtMB(bytes) {
    return ((bytes ?? 0) / 1024 / 1024).toFixed(1);
  }

  function exportFullCSV() {
    const rows = exportFiltered && activeChips.length ? filteredResults : (data?.results ?? []);
    if (!rows.length) return;
    const cols = [...new Set(rows.flatMap(r => Object.keys(r)))];
    const esc = (v: any) => {
      if (v === null || v === undefined) return '';
      const s = String(v);
      return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };
    const csv = [cols.join(','), ...rows.map(r => cols.map(c => esc(r[c])).join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `RTM_${data?.job_id ?? 'export'}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
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
      accept=".csv,.xlsx,.xls"
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
          <div class="drop-title">Upload Sales Data</div>
          <div class="drop-sub">Click to browse or drag &amp; drop your file</div>
          <div class="drop-hint">CSV or Excel (.csv, .xlsx, .xls)</div>
        </div>
      {:else}
        <!-- File selected state -->
        <div class="file-selected">
          <div class="file-info">
            <div class="file-check">✓</div>
            <div>
              <div class="file-name">{file.name}</div>
              <div class="file-meta">{file.size > 1024 * 1024 ? (file.size / 1024 / 1024).toFixed(1) + ' MB' : (file.size / 1024).toFixed(0) + ' KB'} · {file.name.toLowerCase().endsWith('.csv') ? 'CSV file' : 'Excel file'}</div>
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

      <!-- Active rules — read-only. The engine always runs on the /rules config,
           so showing anything editable here would be a lie. -->
      {#if ruleCfg}
        <div class="active-rules">
          <div class="ar-head">
            <span class="ar-title">Active rules</span>
            <a class="ar-link" href="/rules">Edit in Rules →</a>
          </div>
          <div class="ar-body">
            <span class="ar-item"><b>Pareto</b> {ruleCfg.pareto?.class_a_cutoff}&thinsp;/&thinsp;{ruleCfg.pareto?.class_b_cutoff}</span>
            <span class="ar-sep">·</span>
            <span class="ar-item">
              <b>F4</b>
              {#if ruleCfg.wholesaler?.enabled}
                ≥ {ruleCfg.wholesaler?.cartons_per_brand_month} cartons/brand/month ({ruleCfg.wholesaler?.item_type})
              {:else}
                off
              {/if}
            </span>
            <span class="ar-sep">·</span>
            <span class="ar-item">
              <b>Category override</b>
              {ruleCfg.category_override?.enabled ? `≥ ${ruleCfg.category_override?.contribution_cutoff}%` : 'off'}
            </span>
          </div>
          <div class="ar-note">These apply to every run.</div>
        </div>
      {/if}

      <!-- Preview KPI cards -->
      {#if file && ruleCfg}
        {@const a = ruleCfg.pareto?.class_a_cutoff ?? 80}
        {@const b = ruleCfg.pareto?.class_b_cutoff ?? 95}
        <div class="preview-kpis">
          <KpiCard label="Class A" value="{a}%" subtitle="top revenue" accent="var(--class-a)" />
          <KpiCard label="Class B" value="{b - a}%" subtitle="middle tier" accent="var(--class-b)" />
          <KpiCard label="Class C" value="{100 - b}%" subtitle="remaining" accent="var(--class-c)" />
        </div>
      {/if}

      <!-- CTA Button -->
      <button class="btn btn-block run-btn" onclick={handleClassify} disabled={!file || (preview && preview.requiredMissing.length > 0)}>
        Run Classification
      </button>
    </div>

    <!-- Preview is still parsing (a big workbook takes a few seconds) -->
    {#if file && previewParsing}
      <div class="card preview-panel animate-fade-up">
        <div class="preview-loading">
          <span class="spinner"></span>
          {#if previewUploading}
            Too large to read in the browser — sending to the server… {previewUploadPct}%
          {:else}
            Reading {file.name}…
          {/if}
        </div>
        {#if previewUploading}
          <div class="export-progress" style="padding: 0 18px 16px;">
            <div class="export-bar"><div class="export-bar-fill" style="width:{previewUploadPct}%"></div></div>
          </div>
        {/if}
      </div>
    {/if}

    <!-- Preview could not be built — say so instead of showing nothing -->
    {#if file && !previewParsing && previewError}
      <div class="card preview-panel animate-fade-up">
        <div class="alert alert-danger">{previewError}</div>
        <div class="preview-foot">
          You can still run the classification — the server parses the file independently.
        </div>
      </div>
    {/if}

    <!-- File Preview Panel -->
    {#if file && preview}
      <div class="card preview-panel animate-fade-up">
        <div class="card-head">
          <div class="card-head-title">File Preview</div>
          <div class="card-head-sub">
            {file.name} · {file.size > 1024 * 1024 ? (file.size / 1024 / 1024).toFixed(1) + ' MB' : (file.size / 1024).toFixed(0) + ' KB'}
            {#if preview.serverSide}
              · read on the server (too large for the browser)
            {:else if preview.sampled}
              · sampled — stats scaled from {preview.parsedRows.toLocaleString()} parsed rows
            {/if}
          </div>
        </div>
        <div class="preview-body">
          <!-- KPI strip. Branch/outlet/date need a full pass over the file (~40s on a
               743k-row workbook), so the server path shows only what it knows exactly. -->
          <div class="preview-stats">
            <KpiCard label="Rows" value={preview.totalRows.toLocaleString()} />
            <KpiCard label="Columns" value={preview.headers.length.toString()} />
            {#if preview.serverSide}
              <KpiCard label="Sheet" value={preview.sheetNames?.[0] ?? '—'} subtitle="first sheet" />
              <KpiCard label="Outlets" value="—" subtitle="counted at classify" />
              <KpiCard label="Date Range" value="—" subtitle="counted at classify" />
            {:else}
              <KpiCard label="Branches" value={preview.branches.length.toString()} />
              <KpiCard label="Outlets" value={preview.outletCount?.toLocaleString() ?? '—'} />
              <KpiCard label="Date Range" value={preview.dateRange || '—'} />
            {/if}
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

            {#if sheetWarning}
              <div class="alert alert-danger" style="margin-top:10px;">⚠ {sheetWarning}</div>
            {/if}

            {#if preview.unknownCols.length > 0}
              <div class="preview-warn">
                ⚠ {preview.unknownCols.length} unrecognised column{preview.unknownCols.length > 1 ? 's' : ''} — ignored by the engine:
                <span class="warn-cols">{preview.unknownCols.join(', ')}</span>
                <div class="warn-hint">Check for a typo if one of these was meant to be a required column.</div>
              </div>
            {/if}
          </div>

          <!-- Browsable data table -->
          <div class="preview-section">
            <div class="preview-table-head">
              <div class="preview-section-title">Uploaded data</div>
              <input
                class="input input-sm preview-search"
                placeholder="Search any column…"
                bind:value={previewSearch}
              />
              <div class="preview-pager">
                <button
                  class="btn btn-sm btn-ghost"
                  disabled={previewPage === 0}
                  onclick={() => (previewPage -= 1)}
                >◀</button>
                <span class="preview-range">
                  {#if previewRows.length}
                    {(previewPage * PREVIEW_PAGE_SIZE + 1).toLocaleString()}–{Math.min((previewPage + 1) * PREVIEW_PAGE_SIZE, previewRows.length).toLocaleString()}
                    of {previewRows.length.toLocaleString()}
                  {:else}
                    no matches
                  {/if}
                </span>
                <button
                  class="btn btn-sm btn-ghost"
                  disabled={previewPage >= previewPageCount - 1}
                  onclick={() => (previewPage += 1)}
                >▶</button>
              </div>
            </div>

            <div class="preview-table-wrap">
              <table class="preview-table">
                <thead>
                  <tr>
                    <th class="rownum">#</th>
                    {#each preview.headers as h}
                      <th class:unknown-col={preview.unknownCols.includes(h)}>{h}</th>
                    {/each}
                  </tr>
                </thead>
                <tbody>
                  {#each previewPageRows as row, ri}
                    <tr>
                      <td class="rownum">{previewPage * PREVIEW_PAGE_SIZE + ri + 1}</td>
                      {#each preview.headers as _, ci}
                        <td>{row[ci] ?? ''}</td>
                      {/each}
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>

            <div class="preview-foot">
              {#if previewSearch.trim()}
                {previewRows.length.toLocaleString()} matching of {preview.parsedRows.toLocaleString()} rows
              {:else}
                {preview.parsedRows.toLocaleString()} rows loaded
              {/if}
              {#if preview.sampled}
                · previewing the first {preview.parsedRows.toLocaleString()} — full file has ~{preview.totalRows.toLocaleString()} rows
              {/if}
            </div>
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
    <div class="filter-bar">
      <MultiSelect label="Branch" options={branches} bind:selected={fBranch} placeholder="All branches" />
      <MultiSelect label="Class" options={classes} bind:selected={fClass} />
      <MultiSelect label="Lifecycle" options={lifecycles} bind:selected={fLifecycle} />
      <MultiSelect label="Risk" options={risks} bind:selected={fRisk} />

      <button
        class="btn btn-sm btn-ghost"
        class:btn-active={showMore || moreCount > 0}
        onclick={() => (showMore = !showMore)}
      >
        More{moreCount ? ` (${moreCount})` : ''}
      </button>
    </div>

    <!-- Job ID + Reset -->
    <div class="controls-right">
      <span class="filter-count">
        {#if activeChips.length}
          <strong>{filteredResults.length.toLocaleString()}</strong> of {data.results.length.toLocaleString()} outlets
        {:else}
          {data.results.length.toLocaleString()} outlets
        {/if}
      </span>
      <span class="job-tag">Job: {data.job_id}</span>
      <button class="btn btn-sm" onclick={reset}>New Job</button>
    </div>
  </div>

  {#if showMore}
    <div class="more-panel">
      <MultiSelect label="Growth signal" options={growths} bind:selected={fGrowth} />
      <MultiSelect label="Visit priority" options={priorities} bind:selected={fPriority} />
      <MultiSelect label="Category" options={categories} bind:selected={fCategory} />
      <MultiSelect label="Principal" options={principals} bind:selected={fPrincipal} />
      <MultiSelect label="Township" options={townships} bind:selected={fTownship} />
      <MultiSelect label="Route" options={routes} bind:selected={fRoute} />
      <label class="f-item f-range">
        <span class="f-label">Revenue (Ks)</span>
        <input class="input input-sm" type="number" placeholder="min" bind:value={fRevMin} />
        <span class="f-dash">–</span>
        <input class="input input-sm" type="number" placeholder="max" bind:value={fRevMax} />
      </label>
      <label class="f-item f-range">
        <span class="f-label">Growth 6M/12M (%)</span>
        <input class="input input-sm" type="number" placeholder="min" bind:value={fGrowthMin} />
        <span class="f-dash">–</span>
        <input class="input input-sm" type="number" placeholder="max" bind:value={fGrowthMax} />
      </label>
      <label class="f-item f-wide">
        <span class="f-label">Outlet</span>
        <input class="input input-sm" placeholder="Search code or name…" bind:value={fSearch} />
      </label>
    </div>
  {/if}

  {#if activeChips.length}
    <div class="chip-row">
      {#each activeChips as chip}
        <button class="chip" onclick={chip.clear} title="Remove filter">
          {chip.label} <span class="chip-x">✕</span>
        </button>
      {/each}
      <button class="chip-reset" onclick={clearFilters}>Reset all</button>
    </div>
  {/if}

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
    <ChapterHeading title="Export Results" subtitle="Download the classified dataset" />

    {#if activeChips.length}
      <label class="export-scope">
        <input type="checkbox" bind:checked={exportFiltered} />
        <span>
          Apply current filters —
          <strong>{filteredResults.length.toLocaleString()}</strong> of
          {data.results.length.toLocaleString()} outlets
          {#if !exportFiltered}<em>(exporting everything)</em>{/if}
        </span>
      </label>
    {/if}

    <div class="export-grid">
      <!-- Excel — full multi-sheet report -->
      <div class="card card-flush">
        <div class="card-head">
          <div class="card-head-title">Excel Export (.xlsx)</div>
        </div>
        <div class="card-body">
          <div class="export-desc">
            One workbook — every outlet, every field. The <strong>All Results</strong> sheet
            is the full dataset; the rest are ready-made views:
          </div>
          <ul class="export-list">
            <li>All Results — every outlet × every column (incl. AI enrichment)</li>
            <li>Overall + Branch Summary</li>
            <li>Per-branch sheets + Top 50</li>
            <li>AI Action Plan</li>
            <li>Run Comparison vs previous run</li>
            <li>Run Info — who ran it, rule version, LLM cost</li>
          </ul>
          <button class="btn btn-block" disabled={exporting} onclick={downloadExcel}>
            {exporting ? `${exportPhase === 'downloading' ? 'Downloading' : 'Building workbook'}… ${exportPct}%` : 'Download Excel'}
          </button>
          {#if exporting}
            <div class="export-progress">
              <div class="export-bar"><div class="export-bar-fill" style="width:{exportPct}%"></div></div>
              <div class="export-status">{exportMsg}</div>
            </div>
          {/if}
          {#if exportError}
            <div class="export-error">{exportError}</div>
          {/if}
        </div>
      </div>

      <!-- CSV — flat full dataset, all rows + all columns -->
      <div class="card card-flush">
        <div class="card-head">
          <div class="card-head-title">CSV Export (.csv)</div>
        </div>
        <div class="card-body">
          <div class="export-desc">
            Flat single file — same data as the Excel <strong>All Results</strong> sheet:
            every outlet, every column. For import into other tools.
          </div>
          <ul class="export-list">
            <li>{(exportFiltered && activeChips.length ? filteredResults.length : (data?.results?.length ?? 0)).toLocaleString()} outlets{exportFiltered && activeChips.length ? ' (filtered)' : ''}</li>
            <li>Every column — classification, sales, contributions, AI</li>
            <li>No formatting / no extra sheets</li>
          </ul>
          <button class="btn btn-block" onclick={exportFullCSV}>
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

  .preview-loading {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 18px;
    font-size: 0.85rem;
    color: var(--text-muted);
  }
  .spinner {
    width: 14px;
    height: 14px;
    border: 2px solid var(--border);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
  }
  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .preview-table-head {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 8px;
  }
  .preview-table-head .preview-section-title {
    margin: 0;
    flex: 1;
  }
  .preview-search {
    min-width: 200px;
  }
  .preview-pager {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .preview-range {
    font-size: 0.74rem;
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  .preview-table th.unknown-col {
    color: var(--text-faint);
    text-decoration: line-through;
  }
  .preview-table .rownum {
    color: var(--text-faint);
    font-variant-numeric: tabular-nums;
    text-align: right;
    width: 1%;
    white-space: nowrap;
  }
  .preview-warn {
    margin-top: 10px;
    padding: 8px 12px;
    font-size: 0.78rem;
    color: var(--text);
    background: var(--warn-bg, #FEF9C3);
    border: 1px solid var(--warn-border, #E6D57A);
    border-radius: var(--r-sm, 6px);
  }
  .warn-cols {
    font-family: var(--font-mono, monospace);
    font-size: 0.74rem;
  }
  .warn-hint {
    margin-top: 4px;
    font-size: 0.72rem;
    color: var(--text-muted);
  }

  .active-rules {
    margin-top: 22px;
    padding: 12px 14px;
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: var(--r-md, 8px);
  }
  .ar-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 6px;
  }
  .ar-title {
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--text-muted);
  }
  .ar-link {
    font-size: 0.75rem;
    color: var(--accent);
    text-decoration: none;
  }
  .ar-link:hover { text-decoration: underline; }
  .ar-body {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
    font-size: 0.82rem;
    color: var(--text);
  }
  .ar-item b {
    font-weight: 600;
  }
  .ar-sep { color: var(--text-faint); }
  .ar-note {
    margin-top: 6px;
    font-size: 0.72rem;
    color: var(--text-muted);
  }

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

  /* ===== Filter bar ===== */
  .filter-bar {
    display: flex;
    align-items: flex-end;
    gap: 10px;
    flex-wrap: wrap;
  }
  .f-item {
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 0;
  }
  .f-label {
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--text-muted);
  }
  .select-sm,
  .input-sm {
    height: 32px;
    padding: 0 8px;
    font-size: 0.8rem;
    min-width: 128px;
  }
  .f-range {
    flex-direction: column;
  }
  .f-range .input-sm {
    min-width: 92px;
  }
  .f-range {
    display: grid;
    grid-template-areas: "l l l" "a d b";
    grid-template-columns: auto auto auto;
    align-items: center;
    gap: 4px 6px;
  }
  .f-range .f-label { grid-area: l; }
  .f-dash { grid-area: d; color: var(--text-faint); }
  .f-wide .input-sm { min-width: 220px; }
  .btn-active {
    border-color: var(--accent);
    color: var(--accent);
  }
  .more-panel {
    display: flex;
    flex-wrap: wrap;
    gap: 14px;
    padding: 14px 16px;
    margin-bottom: 14px;
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: var(--r-md, 8px);
  }
  .filter-count {
    font-size: 0.75rem;
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
  }
  .filter-count strong { color: var(--text); }
  .chip-row {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 16px;
  }
  .chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 3px 10px;
    font-size: 0.74rem;
    color: var(--text);
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: var(--r-pill);
    cursor: pointer;
  }
  .chip:hover { border-color: var(--accent); color: var(--accent); }
  .chip-x { font-size: 0.66rem; opacity: 0.6; }
  .chip-reset {
    padding: 3px 4px;
    font-size: 0.74rem;
    color: var(--text-muted);
    background: none;
    border: none;
    text-decoration: underline;
    cursor: pointer;
  }
  .chip-reset:hover { color: var(--accent); }
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
  .export-single {
    max-width: 520px;
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
  .export-error {
    font-size: 0.78rem;
    color: var(--danger, #C0392B);
    margin-top: 8px;
  }
  .export-scope {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 16px;
    padding: 10px 14px;
    font-size: 0.8rem;
    color: var(--text);
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: var(--r-md, 8px);
    cursor: pointer;
  }
  .export-scope em {
    color: var(--text-muted);
    font-style: normal;
  }
  .export-progress {
    margin-top: 10px;
  }
  .export-bar {
    height: 6px;
    background: var(--border);
    border-radius: var(--r-pill);
    overflow: hidden;
  }
  .export-bar-fill {
    height: 100%;
    background: var(--accent);
    border-radius: var(--r-pill);
    transition: width 0.25s ease;
  }
  .export-status {
    margin-top: 6px;
    font-size: 0.72rem;
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
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
    .ar-body { flex-direction: column; align-items: flex-start; gap: 4px; }
    .ar-sep { display: none; }
  }
</style>
