<script lang="ts">
  import { getRtmData, exportExcelWithProgress } from '$lib/api';
  import DataTable from '$lib/components/DataTable.svelte';
  import MultiSelect from '$lib/components/MultiSelect.svelte';

  let data = $state<any>(null);
  let loading = $state(true);
  let error = $state('');

  // Filters — each is a list of accepted values; empty = "All"
  let selectedJob = $state('');
  let searchQuery = $state('');
  let fBranch = $state<any[]>([]);
  let fClass = $state<any[]>([]);
  let fLifecycle = $state<any[]>([]);
  let fRisk = $state<any[]>([]);
  let fGrowth = $state<any[]>([]);
  let fPriority = $state<any[]>([]);
  let fCategory = $state<any[]>([]);
  let fPrincipal = $state<any[]>([]);
  let fTownship = $state<any[]>([]);
  let fRoute = $state<any[]>([]);
  let fRevMin = $state('');
  let fRevMax = $state('');
  let fGrowthMin = $state('');
  let fGrowthMax = $state('');
  let showMore = $state(false);

  // Export state
  let exporting = $state(false);
  let exportPct = $state(0);
  let exportPhase = $state('building');
  let exportMsg = $state('');
  let exportError = $state('');
  let exportFiltered = $state(true);

  // Persist the branch filter to localStorage (shared key with Classify)
  $effect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('rtm_branch_filter', JSON.stringify(fBranch));
    }
  });

  let branchRestored = false;
  $effect(() => {
    if (branchRestored || typeof window === 'undefined') return;
    if (loading || branches.length === 0) return;
    branchRestored = true;
    const raw = localStorage.getItem('rtm_branch_filter');
    if (!raw) return;
    try {
      // Older builds stored a single branch name, not an array
      const saved = raw.startsWith('[') ? JSON.parse(raw) : [raw];
      const valid = saved.filter((b: string) => branches.includes(b));
      if (valid.length) fBranch = valid;
    } catch {
      /* corrupt value — start unfiltered */
    }
  });

  // All available options
  let jobs = $state<any[]>([]);
  let allResults = $state<any[]>([]);

  $effect(() => {
    loadData();
  });

  async function loadData(jobId?: string) {
    loading = true;
    error = '';
    try {
      const resp = await getRtmData(jobId);
      allResults = resp.results || [];
      jobs = resp.jobs || [];
      if (!selectedJob && resp.job_id) selectedJob = resp.job_id;
      data = resp;
    } catch (e: any) {
      error = e.message || 'Failed to load data';
    } finally {
      loading = false;
    }
  }

  function handleJobChange(e: Event) {
    const val = (e.target as HTMLSelectElement).value;
    selectedJob = val;
    loadData(val);
  }

  // Helper for field names (db uses underscore, api uses dot)
  function getField(row: any, ...keys: string[]): any {
    for (const k of keys) {
      if (row[k] !== undefined && row[k] !== null) return row[k];
    }
    return '';
  }

  function fmtNum(n: number): string {
    if (!n && n !== 0) return 'Ks 0';
    if (Math.abs(n) >= 1e9) return `Ks ${(n/1e9).toFixed(1)}B`;
    if (Math.abs(n) >= 1e6) return `Ks ${(n/1e6).toFixed(1)}M`;
    if (Math.abs(n) >= 1e3) return `Ks ${(n/1e3).toFixed(1)}K`;
    return `Ks ${n.toLocaleString()}`;
  }

  // ── Filters ── same engine as Classify: within a filter values OR, across filters AND.
  // An empty selection means "All" and never narrows.
  const uniq = (key: string) =>
    [...new Set(allResults.map(r => r[key]).filter(v => v !== null && v !== undefined && v !== '' && String(v) !== 'nan'))]
      .sort((a, b) => String(a).localeCompare(String(b), undefined, { numeric: true }));

  let branches = $derived(
    [...new Set(allResults.map(r => getField(r, 'BranchName', 'Branch', 'branch_name')).filter(Boolean))].sort()
  );
  let classes = $derived(uniq('Classification'));
  let lifecycles = $derived(uniq('Lifecycle_Stage'));
  let risks = $derived(uniq('AI_Risk_Level'));
  let growths = $derived(uniq('AI_Growth_Signal'));
  let priorities = $derived(uniq('AI_Visit_Priority'));
  let categories = $derived(uniq('SalesGroup'));
  let principals = $derived(uniq('Principal'));
  let townships = $derived(uniq('Township'));
  let routes = $derived(uniq('RouteCode'));

  const num = (v: any) => {
    const n = parseFloat(v);
    return Number.isFinite(n) ? n : null;
  };
  const pick = (rows: any[], sel: any[], key: string) =>
    sel.length ? rows.filter(r => sel.includes(r[key])) : rows;

  let filteredResults = $derived.by(() => {
    let rows = allResults;
    if (fBranch.length) {
      rows = rows.filter(r => fBranch.includes(getField(r, 'BranchName', 'Branch', 'branch_name')));
    }
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

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      rows = rows.filter(r =>
        String(getField(r, 'Cus.Name', 'Cus_Name')).toLowerCase().includes(q) ||
        String(getField(r, 'Cus.Code', 'Cus_Code')).toLowerCase().includes(q) ||
        String(getField(r, 'BranchName', 'Branch')).toLowerCase().includes(q)
      );
    }
    return rows;
  });

  const fmtCompact = (n: number) => {
    if (n >= 1e9) return (n / 1e9).toFixed(1) + 'B';
    if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
    if (n >= 1e3) return (n / 1e3).toFixed(0) + 'K';
    return String(n);
  };

  let activeChips = $derived.by(() => {
    const c: any[] = [];
    const add = (prefix: string, sel: any[], drop: (v: any) => void) => {
      for (const v of sel) c.push({ label: prefix ? `${prefix}: ${v}` : String(v), clear: () => drop(v) });
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
    if (num(fRevMin) !== null) c.push({ label: `Rev ≥ ${fmtCompact(num(fRevMin)!)}`, clear: () => (fRevMin = '') });
    if (num(fRevMax) !== null) c.push({ label: `Rev ≤ ${fmtCompact(num(fRevMax)!)}`, clear: () => (fRevMax = '') });
    if (num(fGrowthMin) !== null) c.push({ label: `Growth ≥ ${fGrowthMin}%`, clear: () => (fGrowthMin = '') });
    if (num(fGrowthMax) !== null) c.push({ label: `Growth ≤ ${fGrowthMax}%`, clear: () => (fGrowthMax = '') });
    if (searchQuery.trim()) c.push({ label: `"${searchQuery.trim()}"`, clear: () => (searchQuery = '') });
    return c;
  });

  let moreCount = $derived(
    [fGrowth, fPriority, fCategory, fPrincipal, fTownship, fRoute].filter(a => a.length).length
    + [fRevMin, fRevMax, fGrowthMin, fGrowthMax].filter(v => num(v) !== null).length
  );

  // Formatted table data
  let tableData = $derived.by(() => {
    return filteredResults.map(r => ({
      'Cus.Code': getField(r, 'Cus.Code', 'Cus_Code'),
      'Cus.Name': getField(r, 'Cus.Name', 'Cus_Name'),
      Branch: getField(r, 'BranchName', 'Branch', 'branch_name'),
      Classification: r.Classification || '',
      'Visit Freq': r.Visit_Frequency || '-',
      '2Yr Sales': fmtNum(r.TotalSales_2Yr || 0),
      '12M Sales': fmtNum(r.TotalSales_12M || 0),
      '6M Sales': fmtNum(r.TotalSales_6M || 0),
      '3M Sales': fmtNum(r.TotalSales_3M || 0),
      Transactions: (r.TransactionCount || 0).toLocaleString(),
      'Contrib %': ((r.Overall_Contribution_Pct || 0)).toFixed(2) + '%',
      Growth: r.AI_Growth_Signal || '-',
      Risk: r.AI_Risk_Level || '-',
      Priority: r.AI_Visit_Priority || '-',
      Township: r.Township || '-',
      Lifecycle: r.Lifecycle_Stage || '-',
      Contact: r.CntctPrsn || '-',
      Phone: r.Phone1 || '-',
      Address: r.Address || '-',
    }));
  });

  const columns = ['Cus.Code', 'Cus.Name', 'Branch', 'Township', 'Classification', 'Lifecycle', 'Visit Freq', '2Yr Sales', '12M Sales', '6M Sales', '3M Sales', 'Transactions', 'Contrib %', 'Growth', 'Risk', 'Priority', 'Contact', 'Phone', 'Address'];

  // CSV export
  function exportCSV() {
    const rows = exportFiltered && activeChips.length ? filteredResults : allResults;
    if (!rows.length) return;
    const keys = [...new Set(rows.flatMap(r => Object.keys(r)))];
    const esc = (v: any) => {
      if (v === null || v === undefined) return '';
      const s = String(v);
      return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };
    const csv = [keys.join(','), ...rows.map(r => keys.map(k => esc(r[k])).join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `RTM_${selectedJob || 'data'}${exportFiltered && activeChips.length ? '_filtered' : ''}.csv`;
    // The anchor must be in the document, and revoking in the same tick kills
    // an in-flight download of a large blob.
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  }

  async function downloadExcel() {
    if (!selectedJob) return;
    exporting = true;
    exportError = '';
    exportPct = 0;
    exportPhase = 'building';
    exportMsg = 'Starting…';
    try {
      const codes = exportFiltered && activeChips.length
        ? filteredResults.map(r => String(getField(r, 'Cus.Code', 'Cus_Code')))
        : null;
      await exportExcelWithProgress(selectedJob, (p) => {
        exportPhase = p.phase;
        exportPct = p.percent;
        exportMsg = p.phase === 'downloading' && p.total
          ? `Downloading — ${((p.loaded ?? 0) / 1048576).toFixed(1)} / ${((p.total ?? 0) / 1048576).toFixed(1)} MB`
          : p.message;
      }, codes);
    } catch (e: any) {
      exportError = e?.message === 'Session expired'
        ? 'Session expired — sign in again.'
        : `Export failed: ${e?.message ?? 'unknown error'}`;
    } finally {
      exporting = false;
    }
  }

  function resetFilters() {
    fBranch = []; fClass = []; fLifecycle = []; fRisk = [];
    fGrowth = []; fPriority = []; fCategory = [];
    fPrincipal = []; fTownship = []; fRoute = [];
    fRevMin = fRevMax = fGrowthMin = fGrowthMax = '';
    searchQuery = '';
  }
</script>

<svelte:head>
  <title>RTM Data — RTM Agent</title>
</svelte:head>

<div class="page">
  <!-- HEADER -->
  <div class="section-head">
    <span class="dot"></span>
    <div>
      <h2>Outlet Data</h2>
      <div class="section-sub">All classified outlets — filter and export</div>
    </div>
  </div>

  {#if loading}
    <div class="card-flush">
      <div class="data-table-head">
        <span class="skeleton" style="height:16px;width:140px;"></span>
      </div>
      {#each [1,2,3,4,5] as _}
        <div class="skeleton-row">
          {#each [120,80,60,50,80,70] as w}
            <span class="skeleton" style="height:14px;width:{w}px;"></span>
          {/each}
        </div>
      {/each}
    </div>

  {:else if error}
    <div class="alert alert-danger">{error}</div>

  {:else if allResults.length === 0}
    <div class="empty-state">
      <div class="empty-title">No data available</div>
      <div class="empty-sub">Run a classification first to generate outlet data.</div>
      <a href="/" class="btn">Go to Classify</a>
    </div>

  {:else}
    <!-- FILTER BAR -->
    <div class="card filter-bar">
      <div class="filter-row">
        <!-- Job selector -->
        <div class="filter-field job-field">
          <label class="label" for="rtm-job">Job</label>
          <select id="rtm-job" class="select" onchange={handleJobChange}>
            {#each jobs as j}
              <option value={j.job_id} selected={j.job_id === selectedJob}>{j.job_id} ({j.total_outlets} outlets)</option>
            {/each}
          </select>
        </div>

        <MultiSelect label="Branch" options={branches} bind:selected={fBranch} />
        <MultiSelect label="Class" options={classes} bind:selected={fClass} />
        <MultiSelect label="Lifecycle" options={lifecycles} bind:selected={fLifecycle} />
        <MultiSelect label="Risk" options={risks} bind:selected={fRisk} />

        <!-- Search -->
        <div class="filter-field search-field">
          <label class="label" for="rtm-search">Search</label>
          <input id="rtm-search" type="text" class="input" bind:value={searchQuery} placeholder="Name, code, or branch…" />
        </div>

        <button
          class="btn btn-sm btn-ghost more-btn"
          class:btn-active={showMore || moreCount > 0}
          onclick={() => (showMore = !showMore)}
        >
          More{moreCount ? ` (${moreCount})` : ''}
        </button>

        <!-- Reset -->
        <button class="btn-ghost reset-btn" onclick={resetFilters}>Reset</button>
      </div>

      {#if showMore}
        <div class="more-panel">
          <MultiSelect label="Growth signal" options={growths} bind:selected={fGrowth} />
          <MultiSelect label="Visit priority" options={priorities} bind:selected={fPriority} />
          <MultiSelect label="Category" options={categories} bind:selected={fCategory} />
          <MultiSelect label="Principal" options={principals} bind:selected={fPrincipal} />
          <MultiSelect label="Township" options={townships} bind:selected={fTownship} />
          <MultiSelect label="Route" options={routes} bind:selected={fRoute} />
          <label class="f-range">
            <span class="f-label">Revenue (Ks)</span>
            <input class="input input-sm" type="number" placeholder="min" bind:value={fRevMin} />
            <span class="f-dash">–</span>
            <input class="input input-sm" type="number" placeholder="max" bind:value={fRevMax} />
          </label>
          <label class="f-range">
            <span class="f-label">Growth 6M/12M (%)</span>
            <input class="input input-sm" type="number" placeholder="min" bind:value={fGrowthMin} />
            <span class="f-dash">–</span>
            <input class="input input-sm" type="number" placeholder="max" bind:value={fGrowthMax} />
          </label>
        </div>
      {/if}

      {#if activeChips.length}
        <div class="chip-row">
          {#each activeChips as chip}
            <button class="chip chip-filter" onclick={chip.clear} title="Remove filter">
              {chip.label} <span class="chip-x">✕</span>
            </button>
          {/each}
          <button class="chip-reset" onclick={resetFilters}>Reset all</button>
        </div>
      {/if}

      <!-- Result count + export buttons -->
      <div class="filter-footer">
        <span class="chip chip-accent">
          {filteredResults.length.toLocaleString()} of {allResults.length.toLocaleString()} results
        </span>
        <div class="export-actions">
          {#if activeChips.length}
            <label class="scope-toggle">
              <input type="checkbox" bind:checked={exportFiltered} />
              Apply filters
            </label>
          {/if}
          {#if selectedJob}
            <button class="btn btn-sm" disabled={exporting} onclick={downloadExcel}>
              {exporting
                ? `${exportPhase === 'downloading' ? 'Downloading' : 'Building workbook'}… ${exportPct}%`
                : 'Export Excel'}
            </button>
          {/if}
          <button class="btn-ghost btn-sm" disabled={exporting} onclick={exportCSV}>Export CSV</button>
        </div>
      </div>

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

    <!-- DATA TABLE -->
    <DataTable title="RTM Data" data={tableData} columns={columns} maxHeight="600px" />
  {/if}
</div>

<style>
  .page {
    width: 100%;
    margin: 0;
    padding: 24px;
  }

  .section-head h2 {
    font-size: 1.25rem;
    font-weight: 600;
    letter-spacing: -0.01em;
  }

  /* Filter bar */
  .filter-bar {
    margin-bottom: 20px;
  }

  .filter-row {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    align-items: flex-end;
  }

  .filter-field {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .filter-field .label {
    margin: 0;
  }

  .job-field { min-width: 220px; }
  .search-field { flex: 1; min-width: 200px; }

  .reset-btn,
  .more-btn {
    height: 32px;
  }
  .btn-active {
    border-color: var(--accent);
    color: var(--accent);
  }

  /* More filters panel */
  .more-panel {
    display: flex;
    flex-wrap: wrap;
    gap: 14px;
    margin-top: 14px;
    padding: 14px 16px;
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: var(--r-md, 8px);
  }
  .f-label {
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--text-muted);
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
  .input-sm {
    height: 32px;
    padding: 0 8px;
    font-size: 0.8rem;
    min-width: 92px;
  }

  /* Filter chips */
  .chip-row {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 14px;
  }
  .chip-filter {
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
  .chip-filter:hover { border-color: var(--accent); color: var(--accent); }
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

  /* Export scope + progress */
  .scope-toggle {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.76rem;
    color: var(--text-muted);
    cursor: pointer;
  }
  .export-progress {
    margin-top: 12px;
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
  .export-error {
    margin-top: 10px;
    font-size: 0.78rem;
    color: var(--danger, #C0392B);
  }

  .filter-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 12px;
    margin-top: 14px;
    padding-top: 14px;
    border-top: 1px solid var(--border);
  }

  .export-actions {
    display: flex;
    gap: 8px;
  }

  /* Empty state */
  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    text-align: center;
    padding: 56px 24px;
  }

  .empty-title {
    font-size: 15px;
    font-weight: 600;
    color: var(--text);
  }

  .empty-sub {
    font-size: 13px;
    color: var(--text-muted);
  }

  .empty-state .btn {
    margin-top: 12px;
  }

  /* Loading skeleton */
  .skeleton-row {
    display: flex;
    gap: 12px;
    padding: 12px 16px;
    border-bottom: 1px solid var(--border);
  }
</style>
