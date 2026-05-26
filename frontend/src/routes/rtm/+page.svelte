<script lang="ts">
  import { getRtmData, exportExcel } from '$lib/api';
  import DataTable from '$lib/components/DataTable.svelte';

  let data = $state<any>(null);
  let loading = $state(true);
  let error = $state('');

  // Filters
  let selectedJob = $state('');
  let selectedBranch = $state('All');
  let selectedClass = $state('All');
  let searchQuery = $state('');

  // Persist branch filter to localStorage
  $effect(() => {
    if (selectedBranch && typeof window !== 'undefined') {
      localStorage.setItem('rtm_branch_filter', selectedBranch);
    }
  });

  // Restore branch filter from localStorage after data is loaded
  $effect(() => {
    if (typeof window !== 'undefined' && !loading && branches.length > 0) {
      const saved = localStorage.getItem('rtm_branch_filter');
      if (saved && saved !== 'All' && saved !== 'All Branches' && branches.includes(saved)) {
        selectedBranch = saved;
      }
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

  // Derived: unique branches from results
  let branches = $derived(
    [...new Set(allResults.map(r => getField(r, 'BranchName', 'Branch', 'branch_name')).filter(Boolean))].sort()
  );

  // Derived: unique classifications
  let classes = $derived(
    [...new Set(allResults.map(r => r.Classification).filter(Boolean))].sort()
  );

  // Derived: filtered results
  let filteredResults = $derived(() => {
    let rows = allResults;

    // Branch filter
    if (selectedBranch !== 'All') {
      rows = rows.filter(r => getField(r, 'BranchName', 'Branch', 'branch_name') === selectedBranch);
    }

    // Class filter
    if (selectedClass !== 'All') {
      if (selectedClass === 'Class A') {
        rows = rows.filter(r => String(r.Classification || '').startsWith('Class A'));
      } else if (selectedClass === 'F4 Distributor') {
        rows = rows.filter(r => /F4/i.test(String(r.Classification || '')));
      } else if (selectedClass === 'Pure A') {
        rows = rows.filter(r => r.Classification === 'Class A');
      } else {
        rows = rows.filter(r => r.Classification === selectedClass);
      }
    }

    // Search filter
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

  // Formatted table data
  let tableData = $derived(() => {
    return filteredResults().map(r => ({
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

  // CSV export from filtered data
  function exportCSV() {
    const rows = filteredResults();
    if (!rows.length) return;
    const keys = Object.keys(rows[0]);
    const csv = [keys.join(','), ...rows.map(r => keys.map(k => {
      const v = r[k];
      return typeof v === 'string' && v.includes(',') ? `"${v}"` : v ?? '';
    }).join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `RTM_${selectedJob || 'data'}_filtered.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function resetFilters() {
    selectedBranch = 'All';
    selectedClass = 'All';
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

        <!-- Branch filter -->
        <div class="filter-field branch-field">
          <label class="label" for="rtm-branch">Branch</label>
          <select id="rtm-branch" class="select" bind:value={selectedBranch}>
            <option>All</option>
            {#each branches as b}
              <option>{b}</option>
            {/each}
          </select>
        </div>

        <!-- Class filter -->
        <div class="filter-field class-field">
          <label class="label" for="rtm-class">Class</label>
          <select id="rtm-class" class="select" bind:value={selectedClass}>
            <option>All</option>
            <option>Class A</option>
            <option>F4 Distributor</option>
            <option>Pure A</option>
            <option>Class B</option>
            <option>Class C</option>
            {#each classes.filter((c: string) => !['Class A','Class B','Class C','Class A Local (F4)'].includes(c)) as c}
              <option>{c}</option>
            {/each}
          </select>
        </div>

        <!-- Search -->
        <div class="filter-field search-field">
          <label class="label" for="rtm-search">Search</label>
          <input id="rtm-search" type="text" class="input" bind:value={searchQuery} placeholder="Name, code, or branch…" />
        </div>

        <!-- Reset -->
        <button class="btn-ghost reset-btn" onclick={resetFilters}>Reset</button>
      </div>

      <!-- Result count + export buttons -->
      <div class="filter-footer">
        <span class="chip chip-accent">
          {filteredResults().length.toLocaleString()} of {allResults.length.toLocaleString()} results
        </span>
        <div class="export-actions">
          {#if selectedJob}
            <button class="btn btn-sm" onclick={() => exportExcel(selectedJob)}>Export Excel</button>
          {/if}
          <button class="btn-ghost btn-sm" onclick={exportCSV}>Export CSV</button>
        </div>
      </div>
    </div>

    <!-- DATA TABLE -->
    <DataTable title="RTM Data" data={tableData()} columns={columns} maxHeight="600px" />
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
  .branch-field { min-width: 160px; }
  .class-field { min-width: 150px; }
  .search-field { flex: 1; min-width: 200px; }

  .reset-btn {
    height: 38px;
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
