<script lang="ts">
  import { getJobs, getJob, exportExcel, getUsersBasic, getJobShares, shareJob } from '$lib/api';
  import ChapterHeading from '$lib/components/ChapterHeading.svelte';
  import KpiCard from '$lib/components/KpiCard.svelte';
  import DataTable from '$lib/components/DataTable.svelte';
  import Badge from '$lib/components/Badge.svelte';

  interface JobRow {
    job_id: string;
    status: string;
    created: string;
    outlets: number;
    classA: number;
    classB: number;
    classC: number;
    revenue: number;
    revenueFmt: string;
    branches: string;
    thresholdA: string;
    thresholdB: string;
    llmCost: number;
    llmTokens: number;
  }

  let jobs = $state<JobRow[]>([]);
  let loading = $state(true);
  let error = $state('');

  // Detail view state
  let selectedJob = $state<any>(null);
  let selectedResults = $state<any[]>([]);
  let detailLoading = $state(false);
  let detailError = $state('');
  let activeTab = $state(0);
  let selectedBranch = $state('All Branches');
  let searchQuery = $state('');
  let classFilter = $state('All');

  // Share modal state
  let shareJobId = $state<string | null>(null);
  let shareUsers = $state<{ id: number; username: string; display_name: string }[]>([]);
  let shareSelectedIds = $state<number[]>([]);
  let shareLoading = $state(false);
  let shareSaving = $state(false);
  let shareError = $state('');

  $effect(() => {
    loadJobs();
  });

  async function openShare(jobId: string) {
    shareJobId = jobId;
    shareLoading = true;
    shareSaving = false;
    shareError = '';
    shareUsers = [];
    shareSelectedIds = [];
    try {
      const [users, shares] = await Promise.all([getUsersBasic(), getJobShares(jobId)]);
      shareUsers = Array.isArray(users) ? users : [];
      shareSelectedIds = Array.isArray(shares?.user_ids) ? [...shares.user_ids] : [];
    } catch (e: any) {
      shareError = e?.message || 'Failed to load share settings';
    } finally {
      shareLoading = false;
    }
  }

  function closeShare() {
    shareJobId = null;
    shareUsers = [];
    shareSelectedIds = [];
    shareLoading = false;
    shareSaving = false;
    shareError = '';
  }

  function toggleShareUser(userId: number) {
    shareSelectedIds = shareSelectedIds.includes(userId)
      ? shareSelectedIds.filter(id => id !== userId)
      : [...shareSelectedIds, userId];
  }

  async function saveShare() {
    if (!shareJobId) return;
    shareSaving = true;
    shareError = '';
    try {
      await shareJob(shareJobId, shareSelectedIds);
      closeShare();
    } catch (e: any) {
      shareError = e?.message || 'Failed to save share';
      shareSaving = false;
    }
  }

  function onShareKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') closeShare();
  }

  function fmtRevenue(n: number): string {
    if (n >= 1e9) return `Ks ${(n / 1e9).toFixed(1)}B`;
    if (n >= 1e6) return `Ks ${(n / 1e6).toFixed(1)}M`;
    if (n >= 1e3) return `Ks ${(n / 1e3).toFixed(1)}K`;
    return `Ks ${n.toLocaleString()}`;
  }

  function fmtNum(n: number): string {
    if (n >= 1e9) return `Ks ${(n / 1e9).toFixed(1)}B`;
    if (n >= 1e6) return `Ks ${(n / 1e6).toFixed(1)}M`;
    if (n >= 1e3) return `Ks ${(n / 1e3).toFixed(1)}K`;
    return `Ks ${n.toLocaleString()}`;
  }

  function fmtPct(n: number): string {
    return `${n.toFixed(1)}%`;
  }

  function fmtDate(dateStr: string): string {
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) +
        ' ' + d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    } catch {
      return dateStr || '--';
    }
  }

  function statusClass(status: string): string {
    switch (status) {
      case 'completed': return 'status-completed';
      case 'failed': return 'status-failed';
      case 'processing': return 'status-processing';
      default: return 'status-default';
    }
  }

  function renderMarkdown(text: string): string {
    if (!text) return '';
    return text
      .replace(/### (.*?)$/gm, '<h3 style="font-size:14px;font-weight:600;margin:16px 0 8px;color:var(--text);">$1</h3>')
      .replace(/## (.*?)$/gm, '<h2 style="font-size:16px;font-weight:600;margin:16px 0 8px;color:var(--text);">$1</h2>')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/^- (.*?)$/gm, '<div style="padding-left:16px;margin:4px 0;">$1</div>')
      .replace(/^\* (.*?)$/gm, '<div style="padding-left:16px;margin:4px 0;">$1</div>')
      .replace(/\n\n/g, '<br><br>')
      .replace(/\n/g, '<br>');
  }

  function badgeType(cls: string): string {
    if (!cls) return 'class-c';
    if (cls.includes('F4') || cls.includes('Local')) return 'class-f4';
    if (cls.includes('A')) return 'class-a';
    if (cls.includes('B')) return 'class-b';
    return 'class-c';
  }

  async function loadJobs() {
    loading = true;
    error = '';
    try {
      const raw = await getJobs();
      const list = Array.isArray(raw) ? raw : [];
      jobs = list.map(j => ({
        job_id: j.job_id ?? '--',
        status: j.status ?? 'unknown',
        created: j.created_at ?? '',
        outlets: j.total_outlets ?? 0,
        classA: j.class_a_count ?? 0,
        classB: j.class_b_count ?? 0,
        classC: j.class_c_count ?? 0,
        revenue: j.total_revenue ?? 0,
        revenueFmt: fmtRevenue(j.total_revenue ?? 0),
        branches: j.branches ? (Array.isArray(j.branches) ? j.branches.length : j.branches) : '--',
        thresholdA: `${j.threshold_a ?? 80}%`,
        thresholdB: `${j.threshold_b ?? 95}%`,
        llmCost: Number(j.llm_cost ?? 0),
        llmTokens: Number(j.llm_prompt_tokens ?? 0) + Number(j.llm_completion_tokens ?? 0),
      }));
    } catch (e: any) {
      error = e?.message || 'Failed to load jobs';
    } finally {
      loading = false;
    }
  }

  async function viewJob(jobId: string) {
    detailLoading = true;
    detailError = '';
    selectedJob = null;
    selectedResults = [];
    try {
      const data = await getJob(jobId);
      selectedJob = data.job;
      selectedResults = data.results || [];
      activeTab = 0;
      selectedBranch = 'All Branches';
      searchQuery = '';
      classFilter = 'All';
    } catch (e: any) {
      detailError = e?.message || 'Failed to load job';
    } finally {
      detailLoading = false;
    }
  }

  function backToList() {
    selectedJob = null;
    selectedResults = [];
    detailError = '';
    detailLoading = false;
    activeTab = 0;
    selectedBranch = 'All Branches';
    searchQuery = '';
    classFilter = 'All';
  }

  // Helper to get field with dot or underscore naming
  function getField(row: any, ...keys: string[]): any {
    for (const k of keys) {
      if (row[k] !== undefined && row[k] !== null) return row[k];
    }
    return '';
  }

  // Filtered results for detail view
  let filteredResults = $derived(
    selectedBranch !== 'All Branches'
      ? selectedResults.filter(r => getField(r, 'BranchName', 'Branch', 'branch_name') === selectedBranch || r.Cus_Township === selectedBranch)
      : selectedResults
  );

  let branches = $derived(
    [...new Set(selectedResults.map(r => getField(r, 'BranchName', 'Branch', 'branch_name') || r.Cus_Township).filter(Boolean))].sort()
  );

  let kpis = $derived({
    total: filteredResults.length,
    classA: filteredResults.filter(r => String(r.Classification || '').startsWith('Class A')).length,
    classB: filteredResults.filter(r => r.Classification === 'Class B').length,
    classC: filteredResults.filter(r => r.Classification === 'Class C').length,
    wholesalers: filteredResults.filter(r => r.Is_Wholesaler).length,
    revenue: filteredResults.reduce((s, r) => s + (r.TotalSales_2Yr || 0), 0),
    branchCount: new Set(filteredResults.map(r => getField(r, 'BranchName', 'Branch', 'branch_name')).filter(Boolean)).size,
  });

  // Summary rows for dashboard
  let summaryRows = $derived(() => {
    if (!filteredResults.length) return [];
    const totalRev = filteredResults.reduce((s: number, r: any) => s + (r.TotalSales_2Yr || 0), 0);
    const classA = filteredResults.filter(r => String(r.Classification || '').startsWith('Class A'));
    const classB = filteredResults.filter(r => r.Classification === 'Class B');
    const classC = filteredResults.filter(r => r.Classification === 'Class C');
    return [
      { label: 'Class A', outlets: classA },
      { label: 'Class B', outlets: classB },
      { label: 'Class C', outlets: classC },
    ].map(({ label, outlets }) => {
      const rev = outlets.reduce((s: number, r: any) => s + (r.TotalSales_2Yr || 0), 0);
      return {
        Classification: label,
        Count: outlets.length,
        Revenue: fmtNum(rev),
        'Avg Sales': fmtNum(outlets.length ? rev / outlets.length : 0),
        'Share %': fmtPct(totalRev ? (rev / totalRev * 100) : 0),
      };
    }).filter(r => r.Count > 0);
  });

  // Top 10 outlets
  let top10 = $derived(() => {
    return [...filteredResults]
      .sort((a, b) => (b.TotalSales_2Yr || 0) - (a.TotalSales_2Yr || 0))
      .slice(0, 10)
      .map(r => ({
        'Cus.Code': getField(r, 'Cus.Code', 'Cus_Code', 'CusCode'),
        'Cus.Name': getField(r, 'Cus.Name', 'Cus_Name', 'CusName'),
        Branch: getField(r, 'BranchName', 'Branch', 'branch_name'),
        Classification: r.Classification || '',
        '2Yr Sales': fmtNum(r.TotalSales_2Yr || 0),
        'Contribution %': fmtPct(r.Overall_Contribution_Pct || 0),
      }));
  });

  // Explorer data with search and class filter
  let explorerData = $derived(() => {
    let rows = filteredResults;
    if (classFilter !== 'All') {
      rows = rows.filter(r => r.Classification === classFilter);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      rows = rows.filter(r =>
        String(getField(r, 'Cus.Name', 'Cus_Name', 'CusName')).toLowerCase().includes(q) ||
        String(getField(r, 'Cus.Code', 'Cus_Code', 'CusCode')).toLowerCase().includes(q) ||
        String(getField(r, 'BranchName', 'Branch', 'branch_name')).toLowerCase().includes(q)
      );
    }
    return rows.map(r => ({
      ...r,
      'Cus.Code': getField(r, 'Cus.Code', 'Cus_Code', 'CusCode'),
      'Cus.Name': getField(r, 'Cus.Name', 'Cus_Name', 'CusName'),
      'BranchName': getField(r, 'BranchName', 'Branch', 'branch_name'),
      'OutletChannel': getField(r, 'OutletChannel', 'Outlet Channel'),
      'NonFood_Sales_2Yr': getField(r, 'NonFood_Sales_2Yr', 'Non Food_Sales_2Yr'),
    }));
  });

  const explorerCols = ['Cus.Code', 'Cus.Name', 'BranchName', 'Classification', 'TotalSales_2Yr', 'TotalSales_12M', 'TotalSales_6M', 'TotalSales_3M', 'TransactionCount', 'Overall_Contribution_Pct'];

  // Branch bars for analytics
  let branchBars = $derived(() => {
    if (!filteredResults.length) return [];
    const map = new Map<string, number>();
    for (const r of filteredResults) {
      const branch = getField(r, 'BranchName', 'Branch', 'branch_name') || 'Unknown';
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

  // Period bars for analytics
  let periodBars = $derived(() => {
    if (!filteredResults.length) return [];
    const totals: Record<string, number> = {
      '2Yr': filteredResults.reduce((s: number, r: any) => s + (r.TotalSales_2Yr || 0), 0),
      '12M': filteredResults.reduce((s: number, r: any) => s + (r.TotalSales_12M || 0), 0),
      '6M': filteredResults.reduce((s: number, r: any) => s + (r.TotalSales_6M || 0), 0),
      '3M': filteredResults.reduce((s: number, r: any) => s + (r.TotalSales_3M || 0), 0),
    };
    const maxVal = Math.max(...Object.values(totals), 1);
    return Object.entries(totals).map(([period, val]) => ({
      period,
      value: val,
      pct: (val / maxVal) * 100,
    }));
  });

  // Branch matrix
  let branchMatrix = $derived(() => {
    if (!selectedResults.length) return [];
    const map = new Map<string, { outlets: number; revenue: number; a: number; b: number; c: number }>();
    for (const r of selectedResults) {
      const branch = getField(r, 'BranchName', 'Branch', 'branch_name') || 'Unknown';
      if (!map.has(branch)) map.set(branch, { outlets: 0, revenue: 0, a: 0, b: 0, c: 0 });
      const m = map.get(branch)!;
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
        'A %': fmtPct(d.outlets ? (d.a / d.outlets * 100) : 0),
      }));
  });

  const tabLabels = ['Dashboard', 'Data Explorer', 'Analytics', 'Export'];
</script>

{#if selectedJob || detailLoading || detailError}
  <!-- ============================================================ -->
  <!-- DETAIL VIEW -->
  <!-- ============================================================ -->

  <!-- Back button -->
  <button class="btn-ghost btn-sm" style="margin-bottom:16px;" onclick={backToList}>
    ← Back to history
  </button>

  {#if detailLoading}
    <!-- Loading state -->
    <div class="page-head">
      <h1 class="page-title">Loading job…</h1>
    </div>
    <div class="loading-block">
      <div class="loading-dots">
        <span style="background:var(--class-a);"></span>
        <span style="background:var(--class-b);animation-delay:0.15s;"></span>
        <span style="background:var(--class-c);animation-delay:0.3s;"></span>
      </div>
      <div class="loading-text">Loading job results…</div>
    </div>

  {:else if detailError}
    <!-- Error state -->
    <div class="alert alert-danger">{detailError}</div>

  {:else if selectedJob}
    <!-- Hero with job ID -->
    <div class="page-head">
      <h1 class="page-title"><span class="mono">{selectedJob.job_id}</span></h1>
      <p class="page-sub">
        {fmtDate(selectedJob.created_at)} · Status: {(selectedJob.status || '').toUpperCase()} · {selectedResults.length} outlets
      </p>
    </div>

    <!-- Controls row -->
    <div class="controls-row">
      <!-- Branch filter -->
      <div class="control-group">
        <span class="label" style="margin:0;">Branch</span>
        <select class="select" style="width:auto;" bind:value={selectedBranch}>
          <option>All Branches</option>
          {#each branches as branch}
            <option>{branch}</option>
          {/each}
        </select>
      </div>

      <!-- Thresholds info -->
      <div class="threshold-info">
        Thresholds: A={selectedJob.threshold_a ?? 80}% / B={selectedJob.threshold_b ?? 95}%
      </div>
    </div>

    <!-- KPI cards grid -->
    <div class="grid-kpi" style="margin-bottom:24px;">
      <KpiCard label="Total Outlets" value={String(kpis.total)} subtitle="{kpis.branchCount} branches" accent="var(--text)" />
      <KpiCard label="Class A" value={String(kpis.classA)} subtitle="{kpis.total > 0 ? fmtPct((kpis.classA / kpis.total) * 100) : '0%'} of total" accent="var(--class-a)" />
      <KpiCard label="Class B" value={String(kpis.classB)} subtitle="{kpis.total > 0 ? fmtPct((kpis.classB / kpis.total) * 100) : '0%'} of total" accent="var(--class-b)" />
      <KpiCard label="Class C" value={String(kpis.classC)} subtitle="{kpis.total > 0 ? fmtPct((kpis.classC / kpis.total) * 100) : '0%'} of total" accent="var(--class-c)" />
      <KpiCard label="Wholesalers" value={String(kpis.wholesalers)} subtitle="F4 flagged" accent="var(--class-f4)" />
      <KpiCard label="Total Revenue" value={fmtNum(kpis.revenue)} subtitle="2-year aggregate" accent="var(--class-a)" />
    </div>

    <!-- Tab bar -->
    <div class="tab-bar" style="margin-bottom:24px;">
      {#each tabLabels as label, i}
        <button
          class="tab"
          class:active={activeTab === i}
          onclick={() => activeTab = i}
        >
          {label}
        </button>
      {/each}
    </div>

    <!-- ---- TAB 0: DASHBOARD ---- -->
    {#if activeTab === 0}
      <ChapterHeading title="Classification Summary" subtitle="Breakdown by Pareto class" />
      <DataTable title="SUMMARY" data={summaryRows()} columns={['Classification', 'Count', 'Revenue', 'Avg Sales', 'Share %']} maxHeight="300px" />

      <div style="margin-top:24px;"></div>
      <ChapterHeading title="Top 10 Outlets" subtitle="Highest revenue outlets across selection" />
      <DataTable title="TOP 10" data={top10()} columns={['Cus.Code', 'Cus.Name', 'Branch', 'Classification', '2Yr Sales', 'Contribution %']} maxHeight="400px" />

      <div style="margin-top:24px;"></div>
      <ChapterHeading title="Branch Matrix" subtitle="Performance across all branches" />
      <DataTable title="BRANCHES" data={branchMatrix()} columns={['Branch', 'Outlets', 'Revenue', 'Class A', 'Class B', 'Class C', 'A %']} maxHeight="400px" />

    <!-- ---- TAB 1: DATA EXPLORER ---- -->
    {:else if activeTab === 1}
      <div class="explorer-controls">
        <select class="select" style="width:auto;" bind:value={classFilter}>
          <option>All</option>
          <option>Class A</option>
          <option>Class B</option>
          <option>Class C</option>
          <option>Class A Local (F4)</option>
        </select>
        <input class="input" type="text" bind:value={searchQuery} placeholder="Search outlet name or code…" style="flex:1;min-width:200px;" />
        <div class="result-count">{explorerData().length} results</div>
      </div>

      <DataTable title="ALL OUTLETS" data={explorerData()} columns={explorerCols} maxHeight="600px" />

    <!-- ---- TAB 2: ANALYTICS ---- -->
    {:else if activeTab === 2}
      <ChapterHeading title="Branch Revenue Comparison" subtitle="Relative revenue by branch" />
      <div class="card chart-card">
        {#each branchBars() as bar}
          <div class="bar-row">
            <div class="bar-label">{bar.name}</div>
            <div class="bar-track">
              <div class="bar-fill" style="width:{bar.pct}%;background:var(--class-a);"></div>
            </div>
            <div class="bar-value">{fmtNum(bar.revenue)}</div>
          </div>
        {/each}
        {#if branchBars().length === 0}
          <div class="empty-chart">No branch data available</div>
        {/if}
      </div>

      <div style="margin-top:24px;"></div>
      <ChapterHeading title="Period Comparison" subtitle="Aggregate sales by time window" />
      <div class="card chart-card">
        {#each periodBars() as bar}
          <div class="bar-row">
            <div class="bar-label bar-label-period">{bar.period}</div>
            <div class="bar-track bar-track-tall">
              <div class="bar-fill" style="width:{bar.pct}%;background:var(--info);"></div>
            </div>
            <div class="bar-value">{fmtNum(bar.value)}</div>
          </div>
        {/each}
        {#if periodBars().length === 0}
          <div class="empty-chart">No period data available</div>
        {/if}
      </div>

      <!-- Class distribution breakdown -->
      <div style="margin-top:24px;"></div>
      <ChapterHeading title="Class Distribution" subtitle="Outlet count and revenue share by class" />
      <div class="card chart-card">
        {#each [
          { label: 'Class A', count: kpis.classA, color: 'var(--class-a)' },
          { label: 'Class B', count: kpis.classB, color: 'var(--class-b)' },
          { label: 'Class C', count: kpis.classC, color: 'var(--class-c)' },
        ] as cls}
          {@const pct = kpis.total > 0 ? (cls.count / kpis.total * 100) : 0}
          <div class="bar-row">
            <div class="bar-label bar-label-period" style="color:{cls.color};">{cls.label}</div>
            <div class="bar-track bar-track-tall">
              <div class="bar-fill" style="width:{pct}%;background:{cls.color};"></div>
            </div>
            <div class="bar-value">{cls.count} ({fmtPct(pct)})</div>
          </div>
        {/each}
      </div>

    <!-- ---- TAB 3: EXPORT ---- -->
    {:else if activeTab === 3}
      <ChapterHeading title="Export Results" subtitle="Download classified data" />
      <div class="export-grid">
        <!-- Excel export -->
        <div class="card export-card">
          <div class="export-head">Excel export (.xlsx)</div>
          <div class="export-body">
            <div class="export-desc">Multi-sheet workbook with:</div>
            <ul class="export-list">
              <li>All Outlets (classified)</li>
              <li>Branch Summary</li>
              <li>Class A / B / C sheets</li>
              <li>AI Insights</li>
              <li>Pipeline Log</li>
            </ul>
            <button class="btn btn-block" onclick={() => exportExcel(selectedJob.job_id)}>
              Download Excel
            </button>
          </div>
        </div>

        <!-- CSV export -->
        <div class="card export-card">
          <div class="export-head">CSV export (.csv)</div>
          <div class="export-body">
            <div class="export-desc">Flat file export with all columns:</div>
            <ul class="export-list">
              <li>All classification fields</li>
              <li>Sales aggregates (2Yr/12M/6M/3M)</li>
              <li>AI enrichment columns</li>
              <li>Contribution percentages</li>
            </ul>
            <button
              class="btn btn-ghost btn-block"
              onclick={() => {
                if (!selectedResults.length) return;
                const header = explorerCols.join(',');
                const rows = selectedResults.map(r => explorerCols.map(c => JSON.stringify(r[c] ?? '')).join(','));
                const csv = [header, ...rows].join('\n');
                const blob = new Blob([csv], { type: 'text/csv' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `RTM_${selectedJob.job_id}.csv`;
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

{:else}
  <!-- ============================================================ -->
  <!-- LIST VIEW -->
  <!-- ============================================================ -->

  <div class="page-head">
    <h1 class="page-title">Job History</h1>
    <p class="page-sub">Past classification runs — click any row to view results</p>
  </div>

  {#if loading}
    <div class="card-flush" style="overflow:hidden;">
      <div class="data-table-head">Jobs</div>
      {#each [1,2,3,4,5] as _}
        <div class="skeleton-row">
          {#each [120,80,60,50,80,60,70] as w}
            <div class="skeleton" style="height:14px;width:{w}px;"></div>
          {/each}
        </div>
      {/each}
    </div>
  {:else if error}
    <div class="alert alert-danger">{error}</div>
  {:else if jobs.length === 0}
    <div class="empty-state">
      <div class="empty-title">No jobs yet</div>
      <div class="empty-desc">Run a classification first to see results here.</div>
      <a href="/" class="btn" style="margin-top:16px;text-decoration:none;">
        Go to Classify
      </a>
    </div>
  {:else}
    <ChapterHeading title="All Runs" subtitle="{jobs.length} classification jobs on record" />

    <!-- Job table -->
    <div class="data-table-wrap">
      <div class="data-table-head">
        <span>Jobs</span>
        <span class="head-count">{jobs.length} rows</span>
      </div>
      <div class="table-scroll">
        <table class="data-table">
          <thead>
            <tr>
              <th>Job ID</th>
              <th>Date</th>
              <th>Status</th>
              <th style="text-align:right;">Outlets</th>
              <th style="text-align:center;">A / B / C</th>
              <th style="text-align:right;">LLM Cost</th>
              <th style="text-align:center;">Action</th>
            </tr>
          </thead>
          <tbody>
            {#each jobs as row, i}
              <tr class="job-row" onclick={() => window.location.href = `/?job=${row.job_id}`}>
                <!-- Job ID -->
                <td class="mono" style="white-space:nowrap;">{row.job_id}</td>
                <!-- Date -->
                <td style="white-space:nowrap;color:var(--text-muted);">{fmtDate(row.created)}</td>
                <!-- Status badge -->
                <td style="white-space:nowrap;">
                  <span class="status-badge {statusClass(row.status)}">{row.status}</span>
                </td>
                <!-- Outlets -->
                <td class="mono" style="text-align:right;white-space:nowrap;">{row.outlets.toLocaleString()}</td>
                <!-- A / B / C counts -->
                <td style="text-align:center;white-space:nowrap;" class="mono">
                  <span class="abc-a">{row.classA}</span>
                  <span class="abc-sep">/</span>
                  <span class="abc-b">{row.classB}</span>
                  <span class="abc-sep">/</span>
                  <span class="abc-c">{row.classC}</span>
                </td>
                <!-- LLM cost -->
                <td class="mono" style="text-align:right;white-space:nowrap;"
                    title="{row.llmTokens.toLocaleString()} tokens">
                  {row.llmCost > 0 ? '$' + row.llmCost.toFixed(4) : '—'}
                </td>
                <!-- View button -->
                <td style="text-align:center;white-space:nowrap;">
                  <div class="row-actions">
                    <span class="chip chip-accent">View results</span>
                    <button
                      class="btn-ghost btn-sm"
                      onclick={(e) => { e.stopPropagation(); openShare(row.job_id); }}
                    >
                      Share
                    </button>
                  </div>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </div>
  {/if}
{/if}

<!-- ============================================================ -->
<!-- SHARE MODAL -->
<!-- ============================================================ -->
{#if shareJobId}
  <div
    class="modal-backdrop"
    role="presentation"
    onclick={closeShare}
    onkeydown={onShareKeydown}
  >
    <div
      class="modal share-modal"
      role="dialog"
      aria-modal="true"
      aria-label="Share job"
      tabindex="-1"
      onclick={(e) => e.stopPropagation()}
      onkeydown={onShareKeydown}
    >
      <h2 class="share-title">Share Job — <span class="mono">{shareJobId}</span></h2>

      {#if shareError}
        <div class="alert alert-danger">{shareError}</div>
      {/if}

      {#if shareLoading}
        <div class="share-list">
          {#each [1,2,3,4] as _}
            <div class="skeleton" style="height:18px;width:100%;margin:8px 0;"></div>
          {/each}
        </div>
      {:else}
        <div class="share-list">
          {#if shareUsers.length === 0}
            <div class="share-empty">No users available.</div>
          {:else}
            {#each shareUsers as user}
              <label class="share-row">
                <input
                  type="checkbox"
                  checked={shareSelectedIds.includes(user.id)}
                  onchange={() => toggleShareUser(user.id)}
                />
                <span class="share-name">
                  {user.display_name || user.username}
                  <span class="share-username">@{user.username}</span>
                </span>
              </label>
            {/each}
          {/if}
        </div>
      {/if}

      <div class="share-actions">
        <button class="btn btn-ghost btn-sm" onclick={closeShare} disabled={shareSaving}>
          Cancel
        </button>
        <button class="btn btn-sm" onclick={saveShare} disabled={shareSaving || shareLoading}>
          {shareSaving ? 'Saving…' : 'Save'}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  /* ---- Page header ---- */
  .page-head {
    margin-bottom: 24px;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--border);
  }
  .page-title {
    font-size: 1.5rem;
    font-weight: 600;
    color: var(--text);
    margin: 0;
  }
  .page-sub {
    font-size: 0.8rem;
    color: var(--text-muted);
    margin: 6px 0 0;
  }
  .mono {
    font-family: var(--font-mono);
  }

  /* ---- Loading ---- */
  .loading-block {
    text-align: center;
    padding: 48px;
  }
  .loading-dots {
    display: flex;
    justify-content: center;
    gap: 6px;
    margin-bottom: 16px;
  }
  .loading-dots span {
    width: 8px;
    height: 8px;
    border-radius: var(--r-pill);
    animation: bounce 0.6s ease-in-out infinite;
  }
  .loading-text {
    font-size: 0.8rem;
    color: var(--text-muted);
  }
  @keyframes bounce {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-6px); }
  }

  /* ---- Controls row ---- */
  .controls-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 20px;
    flex-wrap: wrap;
    gap: 12px;
  }
  .control-group {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .threshold-info {
    font-size: 0.75rem;
    color: var(--text-muted);
    font-family: var(--font-mono);
  }

  /* ---- Explorer controls ---- */
  .explorer-controls {
    display: flex;
    gap: 12px;
    margin-bottom: 16px;
    flex-wrap: wrap;
    align-items: center;
  }
  .result-count {
    font-size: 0.78rem;
    color: var(--text-muted);
    display: flex;
    align-items: center;
  }

  /* ---- Charts ---- */
  .chart-card {
    padding: 24px;
  }
  .bar-row {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 10px;
  }
  .bar-row:last-child {
    margin-bottom: 0;
  }
  .bar-label {
    min-width: 120px;
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--text);
    text-align: right;
  }
  .bar-label-period {
    min-width: 70px;
    font-weight: 600;
  }
  .bar-track {
    flex: 1;
    height: 20px;
    background: var(--surface-3);
    border-radius: var(--r-sm);
    overflow: hidden;
  }
  .bar-track-tall {
    height: 24px;
  }
  .bar-fill {
    height: 100%;
    border-radius: var(--r-sm);
    transition: width 0.5s;
  }
  .bar-value {
    min-width: 90px;
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--text);
    font-family: var(--font-mono);
  }
  .empty-chart {
    text-align: center;
    color: var(--text-muted);
    font-size: 0.8rem;
    padding: 24px;
  }

  /* ---- Export ---- */
  .export-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 16px;
  }
  .export-card {
    padding: 0;
    overflow: hidden;
  }
  .export-head {
    padding: 12px 16px;
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--text);
    border-bottom: 1px solid var(--border);
    background: var(--surface-2);
  }
  .export-body {
    padding: 20px;
  }
  .export-desc {
    font-size: 0.8rem;
    color: var(--text);
    margin-bottom: 12px;
    line-height: 1.5;
  }
  .export-list {
    margin: 0 0 16px;
    padding-left: 18px;
    font-size: 0.8rem;
    color: var(--text-muted);
  }
  .export-list li {
    margin: 2px 0;
  }

  /* ---- List view ---- */
  .skeleton-row {
    display: flex;
    gap: 12px;
    padding: 12px 16px;
    border-bottom: 1px solid var(--border);
    background: var(--surface);
  }
  .skeleton-row:last-child {
    border-bottom: none;
  }

  .empty-state {
    text-align: center;
    padding: 48px;
  }
  .empty-title {
    font-size: 1rem;
    font-weight: 600;
    color: var(--text);
    margin-bottom: 8px;
  }
  .empty-desc {
    font-size: 0.8rem;
    color: var(--text-muted);
  }

  .table-scroll {
    max-height: 700px;
    overflow-y: auto;
  }
  .head-count {
    color: var(--text-faint);
    font-weight: 400;
  }

  .job-row {
    cursor: pointer;
    transition: background 0.12s;
  }
  .job-row:hover {
    background: var(--surface-2);
  }

  /* ---- Status badge ---- */
  .status-badge {
    display: inline-block;
    padding: 2px 10px;
    font-size: 0.68rem;
    font-weight: 600;
    border-radius: var(--r-pill);
    text-transform: capitalize;
  }
  .status-completed {
    background: var(--success-soft);
    color: var(--success);
  }
  .status-failed {
    background: var(--danger-soft);
    color: var(--danger);
  }
  .status-processing {
    background: var(--warning-soft);
    color: var(--warning);
  }
  .status-default {
    background: var(--surface-3);
    color: var(--text-muted);
  }

  /* ---- A/B/C counts ---- */
  .abc-a { color: var(--class-a); font-weight: 600; }
  .abc-b { color: var(--class-b); font-weight: 600; }
  .abc-c { color: var(--class-c); font-weight: 600; }
  .abc-sep { color: var(--text-faint); margin: 0 3px; }

  /* ---- Row actions ---- */
  .row-actions {
    display: inline-flex;
    align-items: center;
    gap: 8px;
  }

  /* ---- Share modal ---- */
  .share-modal {
    width: 420px;
    max-width: 92vw;
  }
  .share-title {
    font-size: 1rem;
    font-weight: 600;
    color: var(--text);
    margin: 0 0 16px;
  }
  .share-list {
    max-height: 300px;
    overflow-y: auto;
    border: 1px solid var(--border);
    background: var(--surface-2);
    margin-bottom: 16px;
  }
  .share-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 12px;
    border-bottom: 1px solid var(--border);
    cursor: pointer;
    font-size: 0.82rem;
    color: var(--text);
  }
  .share-row:last-child {
    border-bottom: none;
  }
  .share-row:hover {
    background: var(--surface);
  }
  .share-name {
    display: flex;
    align-items: baseline;
    gap: 8px;
  }
  .share-username {
    font-size: 0.72rem;
    color: var(--text-muted);
    font-family: var(--font-mono);
  }
  .share-empty {
    padding: 16px;
    text-align: center;
    font-size: 0.8rem;
    color: var(--text-muted);
  }
  .share-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
  }
</style>
