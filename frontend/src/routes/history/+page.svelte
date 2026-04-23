<script lang="ts">
  import { getJobs, getJob, exportExcel } from '$lib/api';
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

  $effect(() => {
    loadJobs();
  });

  function fmtRevenue(n: number): string {
    if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
    if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
    if (n >= 1e3) return `$${(n / 1e3).toFixed(1)}K`;
    return `$${n.toLocaleString()}`;
  }

  function fmtNum(n: number): string {
    if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
    if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
    if (n >= 1e3) return `$${(n / 1e3).toFixed(1)}K`;
    return `$${n.toLocaleString()}`;
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

  function statusColor(status: string): { bg: string; text: string } {
    switch (status) {
      case 'completed': return { bg: '#007518', text: '#ffffff' };
      case 'failed': return { bg: '#be2d06', text: '#ffffff' };
      case 'processing': return { bg: '#ff9d00', text: '#383832' };
      default: return { bg: '#828179', text: '#ffffff' };
    }
  }

  function renderMarkdown(text: string): string {
    if (!text) return '';
    return text
      .replace(/### (.*?)$/gm, '<h3 style="font-size:14px;font-weight:900;margin:16px 0 8px;color:#383832;">$1</h3>')
      .replace(/## (.*?)$/gm, '<h2 style="font-size:16px;font-weight:900;margin:16px 0 8px;color:#383832;">$1</h2>')
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

  const tabLabels = ['DASHBOARD', 'DATA EXPLORER', 'ANALYTICS', 'EXPORT'];
</script>

{#if selectedJob || detailLoading || detailError}
  <!-- ============================================================ -->
  <!-- DETAIL VIEW -->
  <!-- ============================================================ -->

  <!-- Back button -->
  <button
    onclick={backToList}
    style="margin-bottom:16px;padding:8px 20px;font-size:11px;font-weight:900;letter-spacing:0.08em;background:#383832;color:#feffd6;border:2px solid #383832;box-shadow:3px 3px 0 #383832;cursor:pointer;transition:all 0.15s;"
    onmouseenter={(e) => { e.currentTarget.style.background = '#00fc40'; e.currentTarget.style.color = '#383832'; }}
    onmouseleave={(e) => { e.currentTarget.style.background = '#383832'; e.currentTarget.style.color = '#feffd6'; }}
  >
    &larr; BACK TO HISTORY
  </button>

  {#if detailLoading}
    <!-- Loading state -->
    <div style="background:#383832;color:#feffd6;padding:16px 24px;margin-bottom:24px;border-bottom:4px solid #383832;border-right:4px solid #383832;">
      <div style="font-size:1.5rem;font-weight:900;letter-spacing:-0.03em;">LOADING JOB...</div>
    </div>
    <div style="text-align:center;padding:48px;">
      <div style="display:flex;justify-content:center;gap:6px;margin-bottom:16px;">
        <span style="width:8px;height:8px;background:#007518;animation:bounce 0.6s ease-in-out infinite;"></span>
        <span style="width:8px;height:8px;background:#ff9d00;animation:bounce 0.6s ease-in-out infinite;animation-delay:0.15s;"></span>
        <span style="width:8px;height:8px;background:#be2d06;animation:bounce 0.6s ease-in-out infinite;animation-delay:0.3s;"></span>
      </div>
      <div style="font-size:11px;font-weight:700;color:#828179;letter-spacing:0.08em;">LOADING JOB RESULTS...</div>
    </div>

  {:else if detailError}
    <!-- Error state -->
    <div style="padding:16px;background:#be2d06;color:white;font-size:12px;font-weight:700;border:2px solid #383832;">
      ERROR: {detailError}
    </div>

  {:else if selectedJob}
    <!-- Hero with job ID -->
    <div style="background:#383832;color:#feffd6;padding:16px 24px;margin-bottom:24px;border-bottom:4px solid #383832;border-right:4px solid #383832;">
      <div style="font-size:1.5rem;font-weight:900;letter-spacing:-0.03em;">JOB: {selectedJob.job_id}</div>
      <div style="font-size:11px;opacity:0.75;margin-top:4px;">
        {fmtDate(selectedJob.created_at)} &mdash; STATUS: {(selectedJob.status || '').toUpperCase()} &mdash; {selectedResults.length} OUTLETS
      </div>
    </div>

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

      <!-- Thresholds info -->
      <div style="display:flex;align-items:center;gap:12px;">
        <span style="font-size:10px;font-weight:700;color:#828179;letter-spacing:0.06em;">
          THRESHOLDS: A={selectedJob.threshold_a ?? 80}% / B={selectedJob.threshold_b ?? 95}%
        </span>
      </div>
    </div>

    <!-- KPI cards grid -->
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:24px;">
      <KpiCard label="Total Outlets" value={String(kpis.total)} subtitle="{kpis.branchCount} branches" accent="#383832" />
      <KpiCard label="Class A" value={String(kpis.classA)} subtitle="{kpis.total > 0 ? fmtPct((kpis.classA / kpis.total) * 100) : '0%'} of total" accent="#007518" />
      <KpiCard label="Class B" value={String(kpis.classB)} subtitle="{kpis.total > 0 ? fmtPct((kpis.classB / kpis.total) * 100) : '0%'} of total" accent="#ff9d00" />
      <KpiCard label="Class C" value={String(kpis.classC)} subtitle="{kpis.total > 0 ? fmtPct((kpis.classC / kpis.total) * 100) : '0%'} of total" accent="#be2d06" />
      <KpiCard label="Wholesalers" value={String(kpis.wholesalers)} subtitle="F4 flagged" accent="#006f7c" />
      <KpiCard label="Total Revenue" value={fmtNum(kpis.revenue)} subtitle="2-year aggregate" accent="#007518" />
    </div>

    <!-- Tab bar -->
    <div style="display:flex;gap:0;margin-bottom:24px;border-bottom:3px solid #383832;flex-wrap:wrap;">
      {#each tabLabels as label, i}
        <button
          onclick={() => activeTab = i}
          style="padding:10px 20px;font-size:10px;font-weight:900;letter-spacing:0.1em;text-transform:uppercase;border:none;cursor:pointer;transition:all 0.15s;
            {activeTab === i
              ? 'background:#383832;color:#feffd6;'
              : 'background:transparent;color:#65655e;'}"
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
        <div style="font-size:10px;font-weight:800;color:#828179;letter-spacing:0.06em;display:flex;align-items:center;">
          {explorerData().length} RESULTS
        </div>
      </div>

      <DataTable title="ALL OUTLETS" data={explorerData()} columns={explorerCols} maxHeight="600px" />

    <!-- ---- TAB 2: ANALYTICS ---- -->
    {:else if activeTab === 2}
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

      <div style="margin-top:24px;"></div>
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
        {#if periodBars().length === 0}
          <div style="text-align:center;color:#828179;font-size:11px;padding:24px;">No period data available</div>
        {/if}
      </div>

      <!-- Class distribution breakdown -->
      <div style="margin-top:24px;"></div>
      <ChapterHeading title="Class Distribution" subtitle="Outlet count and revenue share by class" />
      <div style="background:white;border:3px solid #383832;box-shadow:4px 4px 0 #383832;padding:24px;">
        {#each [
          { label: 'CLASS A', count: kpis.classA, color: '#007518' },
          { label: 'CLASS B', count: kpis.classB, color: '#ff9d00' },
          { label: 'CLASS C', count: kpis.classC, color: '#be2d06' },
        ] as cls}
          {@const pct = kpis.total > 0 ? (cls.count / kpis.total * 100) : 0}
          <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px;">
            <div style="min-width:80px;font-size:11px;font-weight:900;letter-spacing:0.06em;color:{cls.color};text-align:right;">{cls.label}</div>
            <div style="flex:1;height:24px;background:#ebe8dd;">
              <div style="height:100%;width:{pct}%;background:{cls.color};transition:width 0.5s;"></div>
            </div>
            <div style="min-width:100px;font-size:10px;font-weight:700;color:#383832;">{cls.count} ({fmtPct(pct)})</div>
          </div>
        {/each}
      </div>

    <!-- ---- TAB 3: EXPORT ---- -->
    {:else if activeTab === 3}
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
              onclick={() => exportExcel(selectedJob.job_id)}
              style="width:100%;padding:10px;font-size:11px;font-weight:900;letter-spacing:0.1em;background:#00fc40;color:#383832;border:2px solid #383832;box-shadow:3px 3px 0 #383832;cursor:pointer;transition:all 0.15s;"
              onmouseenter={(e) => { e.currentTarget.style.boxShadow = '1px 1px 0 #383832'; e.currentTarget.style.transform = 'translate(2px,2px)'; }}
              onmouseleave={(e) => { e.currentTarget.style.boxShadow = '3px 3px 0 #383832'; e.currentTarget.style.transform = 'translate(0,0)'; }}
            >
              DOWNLOAD EXCEL
            </button>
          </div>
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
              style="width:100%;padding:10px;font-size:11px;font-weight:900;letter-spacing:0.1em;background:#006f7c;color:white;border:2px solid #383832;box-shadow:3px 3px 0 #383832;cursor:pointer;transition:all 0.15s;"
              onmouseenter={(e) => { e.currentTarget.style.boxShadow = '1px 1px 0 #383832'; e.currentTarget.style.transform = 'translate(2px,2px)'; }}
              onmouseleave={(e) => { e.currentTarget.style.boxShadow = '3px 3px 0 #383832'; e.currentTarget.style.transform = 'translate(0,0)'; }}
            >
              DOWNLOAD CSV
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

  <!-- HERO BOX -->
  <div style="background:#383832;color:#feffd6;padding:16px 24px;margin-bottom:24px;border-bottom:4px solid #383832;border-right:4px solid #383832;">
    <div style="font-size:1.5rem;font-weight:900;letter-spacing:-0.03em;">JOB HISTORY</div>
    <div style="font-size:11px;opacity:0.75;margin-top:4px;">PAST CLASSIFICATION RUNS &mdash; CLICK ANY ROW TO VIEW RESULTS</div>
  </div>

  {#if loading}
    <div style="margin-bottom:24px;">
      <!-- Skeleton title bar -->
      <div style="height:44px;background:#383832;margin-bottom:0;"></div>
      <!-- Skeleton rows -->
      {#each [1,2,3,4,5] as _}
        <div style="display:flex;gap:12px;padding:12px 16px;border-bottom:1px solid #ebe8dd;background:white;">
          {#each [120,80,60,50,80,70] as w}
            <div style="height:14px;width:{w}px;background:#ebe8dd;animation:skeleton-pulse 1.5s ease-in-out infinite;"></div>
          {/each}
        </div>
      {/each}
    </div>
  {:else if error}
    <div style="padding:16px;background:#be2d06;color:white;font-size:12px;font-weight:700;border:2px solid #383832;">
      ERROR: {error}
    </div>
  {:else if jobs.length === 0}
    <div style="text-align:center;padding:48px;">
      <div style="font-size:14px;font-weight:900;color:#383832;letter-spacing:0.06em;margin-bottom:8px;">NO JOBS YET</div>
      <div style="font-size:11px;color:#828179;">Run a classification first to see results here.</div>
      <a href="/" style="display:inline-block;margin-top:16px;padding:10px 24px;font-size:11px;font-weight:900;letter-spacing:0.1em;background:#00fc40;color:#383832;border:2px solid #383832;box-shadow:3px 3px 0 #383832;text-decoration:none;">
        GO TO CLASSIFY
      </a>
    </div>
  {:else}
    <ChapterHeading title="All Runs" subtitle="{jobs.length} classification jobs on record" />

    <!-- Job cards / table -->
    <div style="border:3px solid #383832;box-shadow:4px 4px 0 #383832;overflow:hidden;">
      <div style="padding:8px 12px;background:#383832;color:#feffd6;font-size:10px;font-weight:900;letter-spacing:0.1em;display:flex;justify-content:space-between;">
        <span>JOBS</span>
        <span style="opacity:0.7;">{jobs.length} ROWS</span>
      </div>
      <div style="max-height:700px;overflow-y:auto;">
        <table style="width:100%;border-collapse:collapse;font-size:12px;">
          <thead>
            <tr>
              <th style="position:sticky;top:0;background:#ebe8dd;padding:8px 12px;text-align:left;font-size:10px;font-weight:800;letter-spacing:0.08em;text-transform:uppercase;color:#383832;border-bottom:2px solid #383832;white-space:nowrap;">JOB ID</th>
              <th style="position:sticky;top:0;background:#ebe8dd;padding:8px 12px;text-align:left;font-size:10px;font-weight:800;letter-spacing:0.08em;text-transform:uppercase;color:#383832;border-bottom:2px solid #383832;white-space:nowrap;">DATE</th>
              <th style="position:sticky;top:0;background:#ebe8dd;padding:8px 12px;text-align:left;font-size:10px;font-weight:800;letter-spacing:0.08em;text-transform:uppercase;color:#383832;border-bottom:2px solid #383832;white-space:nowrap;">STATUS</th>
              <th style="position:sticky;top:0;background:#ebe8dd;padding:8px 12px;text-align:right;font-size:10px;font-weight:800;letter-spacing:0.08em;text-transform:uppercase;color:#383832;border-bottom:2px solid #383832;white-space:nowrap;">OUTLETS</th>
              <th style="position:sticky;top:0;background:#ebe8dd;padding:8px 12px;text-align:center;font-size:10px;font-weight:800;letter-spacing:0.08em;text-transform:uppercase;color:#383832;border-bottom:2px solid #383832;white-space:nowrap;">A / B / C</th>
              <th style="position:sticky;top:0;background:#ebe8dd;padding:8px 12px;text-align:center;font-size:10px;font-weight:800;letter-spacing:0.08em;text-transform:uppercase;color:#383832;border-bottom:2px solid #383832;white-space:nowrap;">ACTION</th>
            </tr>
          </thead>
          <tbody>
            {#each jobs as row, i}
              {@const sc = statusColor(row.status)}
              <tr
                onclick={() => window.location.href = `/?job=${row.job_id}`}
                style="background:{i % 2 === 0 ? 'white' : '#fcf9ef'};cursor:pointer;border-bottom:1px solid #ebe8dd;transition:background 0.15s;"
                onmouseenter={(e) => e.currentTarget.style.background = '#e8ffd0'}
                onmouseleave={(e) => e.currentTarget.style.background = i % 2 === 0 ? 'white' : '#fcf9ef'}
              >
                <!-- Job ID -->
                <td style="padding:10px 12px;font-size:11px;font-weight:700;color:#383832;white-space:nowrap;font-family:monospace;">
                  {row.job_id}
                </td>
                <!-- Date -->
                <td style="padding:10px 12px;font-size:11px;font-weight:600;color:#65655e;white-space:nowrap;">
                  {fmtDate(row.created)}
                </td>
                <!-- Status badge -->
                <td style="padding:10px 12px;white-space:nowrap;">
                  <span style="display:inline-block;padding:3px 10px;font-size:9px;font-weight:900;letter-spacing:0.1em;text-transform:uppercase;background:{sc.bg};color:{sc.text};">
                    {row.status}
                  </span>
                </td>
                <!-- Outlets -->
                <td style="padding:10px 12px;font-size:11px;font-weight:700;color:#383832;text-align:right;white-space:nowrap;">
                  {row.outlets.toLocaleString()}
                </td>
                <!-- A / B / C counts -->
                <td style="padding:10px 12px;text-align:center;white-space:nowrap;">
                  <span style="font-size:10px;font-weight:800;color:#007518;">{row.classA}</span>
                  <span style="font-size:10px;color:#828179;margin:0 3px;">/</span>
                  <span style="font-size:10px;font-weight:800;color:#ff9d00;">{row.classB}</span>
                  <span style="font-size:10px;color:#828179;margin:0 3px;">/</span>
                  <span style="font-size:10px;font-weight:800;color:#be2d06;">{row.classC}</span>
                </td>
                <!-- View button -->
                <td style="padding:10px 12px;text-align:center;white-space:nowrap;">
                  <span style="display:inline-block;padding:4px 12px;font-size:9px;font-weight:900;letter-spacing:0.1em;background:#00fc40;color:#383832;border:2px solid #383832;box-shadow:2px 2px 0 #383832;cursor:pointer;">
                    VIEW RESULTS
                  </span>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </div>
  {/if}
{/if}
