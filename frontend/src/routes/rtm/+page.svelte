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
    if (!n && n !== 0) return '$0';
    if (Math.abs(n) >= 1e9) return `$${(n/1e9).toFixed(1)}B`;
    if (Math.abs(n) >= 1e6) return `$${(n/1e6).toFixed(1)}M`;
    if (Math.abs(n) >= 1e3) return `$${(n/1e3).toFixed(1)}K`;
    return `$${n.toLocaleString()}`;
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
    }));
  });

  const columns = ['Cus.Code', 'Cus.Name', 'Branch', 'Classification', 'Visit Freq', '2Yr Sales', '12M Sales', '6M Sales', '3M Sales', 'Transactions', 'Contrib %', 'Growth', 'Risk', 'Priority'];

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
  <title>RTM DATA — MCP AGENT</title>
</svelte:head>

<!-- HERO BOX -->
<div style="background:#383832;color:#feffd6;padding:16px 24px;margin-bottom:24px;border-bottom:4px solid #383832;border-right:4px solid #383832;">
  <div style="font-size:1.5rem;font-weight:900;letter-spacing:-0.03em;">OUTLET DATA</div>
  <div style="font-size:11px;opacity:0.75;margin-top:4px;">ALL CLASSIFIED OUTLETS — FILTER & EXPORT</div>
</div>

{#if loading}
  <!-- loading dots -->
  <div style="text-align:center;padding:48px;">
    <div style="display:flex;justify-content:center;gap:6px;margin-bottom:16px;">
      <span style="width:8px;height:8px;background:#007518;animation:bounce 0.6s ease-in-out infinite;"></span>
      <span style="width:8px;height:8px;background:#ff9d00;animation:bounce 0.6s ease-in-out infinite;animation-delay:0.15s;"></span>
      <span style="width:8px;height:8px;background:#be2d06;animation:bounce 0.6s ease-in-out infinite;animation-delay:0.3s;"></span>
    </div>
    <div style="font-size:11px;font-weight:700;color:#828179;">LOADING DATA...</div>
  </div>

{:else if error}
  <div style="padding:16px;background:#be2d06;color:white;font-size:12px;font-weight:700;border:2px solid #383832;">ERROR: {error}</div>

{:else if allResults.length === 0}
  <div style="text-align:center;padding:48px;">
    <div style="font-size:14px;font-weight:900;color:#383832;margin-bottom:8px;">NO DATA AVAILABLE</div>
    <div style="font-size:11px;color:#828179;">Run a classification first to generate outlet data.</div>
    <a href="/" style="display:inline-block;margin-top:16px;padding:10px 24px;font-size:11px;font-weight:900;letter-spacing:0.1em;background:#00fc40;color:#383832;border:2px solid #383832;box-shadow:3px 3px 0 #383832;text-decoration:none;">GO TO CLASSIFY</a>
  </div>

{:else}
  <!-- FILTER BAR -->
  <div style="background:white;border:3px solid #383832;box-shadow:4px 4px 0 #383832;padding:16px 20px;margin-bottom:20px;">
    <div style="display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end;">

      <!-- Job selector -->
      <div style="min-width:200px;">
        <div style="font-size:9px;font-weight:900;letter-spacing:0.08em;color:#383832;margin-bottom:4px;display:inline-block;background:#383832;color:#feffd6;padding:1px 6px;">JOB</div>
        <select onchange={handleJobChange} style="width:100%;padding:6px 10px;font-size:11px;font-weight:700;border:2px solid #383832;background:#f6f4e9;color:#383832;cursor:pointer;font-family:'Space Grotesk',sans-serif;">
          {#each jobs as j}
            <option value={j.job_id} selected={j.job_id === selectedJob}>{j.job_id} ({j.total_outlets} outlets)</option>
          {/each}
        </select>
      </div>

      <!-- Branch filter -->
      <div style="min-width:150px;">
        <div style="font-size:9px;font-weight:900;letter-spacing:0.08em;display:inline-block;background:#383832;color:#feffd6;padding:1px 6px;margin-bottom:4px;">BRANCH</div>
        <select bind:value={selectedBranch} style="width:100%;padding:6px 10px;font-size:11px;font-weight:700;border:2px solid #383832;background:#f6f4e9;color:#383832;cursor:pointer;font-family:'Space Grotesk',sans-serif;">
          <option>All</option>
          {#each branches as b}
            <option>{b}</option>
          {/each}
        </select>
      </div>

      <!-- Class filter -->
      <div style="min-width:140px;">
        <div style="font-size:9px;font-weight:900;letter-spacing:0.08em;display:inline-block;background:#383832;color:#feffd6;padding:1px 6px;margin-bottom:4px;">CLASS</div>
        <select bind:value={selectedClass} style="width:100%;padding:6px 10px;font-size:11px;font-weight:700;border:2px solid #383832;background:#f6f4e9;color:#383832;cursor:pointer;font-family:'Space Grotesk',sans-serif;">
          <option>All</option>
          {#each classes as c}
            <option>{c}</option>
          {/each}
        </select>
      </div>

      <!-- Search -->
      <div style="flex:1;min-width:180px;">
        <div style="font-size:9px;font-weight:900;letter-spacing:0.08em;display:inline-block;background:#383832;color:#feffd6;padding:1px 6px;margin-bottom:4px;">SEARCH</div>
        <input type="text" bind:value={searchQuery} placeholder="Name, code, or branch..."
          style="width:100%;padding:6px 10px;font-size:11px;font-weight:700;border:2px solid #383832;background:#f6f4e9;color:#383832;font-family:'Space Grotesk',sans-serif;box-sizing:border-box;" />
      </div>

      <!-- Reset -->
      <button onclick={resetFilters}
        style="padding:6px 14px;font-size:10px;font-weight:900;letter-spacing:0.08em;background:#383832;color:#feffd6;border:2px solid #383832;cursor:pointer;box-shadow:2px 2px 0 #383832;font-family:'Space Grotesk',sans-serif;"
        onmousedown={(e) => { e.currentTarget.style.transform='translate(1px,1px)'; e.currentTarget.style.boxShadow='1px 1px 0 #383832'; }}
        onmouseup={(e) => { e.currentTarget.style.transform='translate(0,0)'; e.currentTarget.style.boxShadow='2px 2px 0 #383832'; }}
      >RESET</button>
    </div>

    <!-- Result count + export buttons -->
    <div style="display:flex;align-items:center;justify-content:space-between;margin-top:12px;padding-top:12px;border-top:1px solid #ebe8dd;">
      <span style="font-size:10px;font-weight:900;letter-spacing:0.06em;display:inline-block;background:#383832;color:#feffd6;padding:2px 8px;">
        {filteredResults().length.toLocaleString()} OF {allResults.length.toLocaleString()} RESULTS
      </span>
      <div style="display:flex;gap:6px;">
        {#if selectedJob}
          <button onclick={() => exportExcel(selectedJob)}
            style="padding:6px 14px;font-size:10px;font-weight:900;letter-spacing:0.08em;background:#00fc40;color:#383832;border:2px solid #383832;cursor:pointer;box-shadow:2px 2px 0 #383832;font-family:'Space Grotesk',sans-serif;"
            onmousedown={(e) => { e.currentTarget.style.transform='translate(1px,1px)'; e.currentTarget.style.boxShadow='1px 1px 0 #383832'; }}
            onmouseup={(e) => { e.currentTarget.style.transform='translate(0,0)'; e.currentTarget.style.boxShadow='2px 2px 0 #383832'; }}
          >EXPORT EXCEL</button>
        {/if}
        <button onclick={exportCSV}
          style="padding:6px 14px;font-size:10px;font-weight:900;letter-spacing:0.08em;background:#007518;color:white;border:2px solid #383832;cursor:pointer;box-shadow:2px 2px 0 #383832;font-family:'Space Grotesk',sans-serif;"
          onmousedown={(e) => { e.currentTarget.style.transform='translate(1px,1px)'; e.currentTarget.style.boxShadow='1px 1px 0 #383832'; }}
          onmouseup={(e) => { e.currentTarget.style.transform='translate(0,0)'; e.currentTarget.style.boxShadow='2px 2px 0 #383832'; }}
        >EXPORT CSV</button>
      </div>
    </div>
  </div>

  <!-- DATA TABLE -->
  <DataTable title="RTM DATA" data={tableData()} columns={columns} maxHeight="600px" />
{/if}
