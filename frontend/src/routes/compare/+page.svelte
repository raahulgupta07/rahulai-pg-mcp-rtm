<script lang="ts">
  import { onMount } from 'svelte';
  import { getJobs, compareJobs } from '$lib/api';

  let jobs: any[] = $state([]);
  let job1: string = $state('');
  let job2: string = $state('');
  let loading: boolean = $state(false);
  let error: string = $state('');
  let result: any = $state(null);

  onMount(async () => {
    try {
      const data = await getJobs();
      jobs = data.filter((j: any) => j.status === 'completed' || j.total_outlets > 0);
    } catch (e: any) {
      error = 'Failed to load jobs';
    }
  });

  async function runCompare() {
    if (!job1 || !job2) {
      error = 'Select both jobs';
      return;
    }
    if (job1 === job2) {
      error = 'Select two different jobs';
      return;
    }
    error = '';
    loading = true;
    result = null;
    try {
      result = await compareJobs(job1, job2);
    } catch (e: any) {
      error = e.message || 'Comparison failed';
    } finally {
      loading = false;
    }
  }

  function fmt(n: number): string {
    if (n >= 1_000_000_000) return 'Ks ' + (n / 1_000_000_000).toFixed(1) + 'B';
    if (n >= 1_000_000) return 'Ks ' + (n / 1_000_000).toFixed(1) + 'M';
    if (n >= 1_000) return 'Ks ' + (n / 1_000).toFixed(1) + 'K';
    return 'Ks ' + n.toFixed(0);
  }

  function fmtNum(n: number): string {
    return n.toLocaleString();
  }

  function diffStr(a: number, b: number): string {
    const d = b - a;
    if (d === 0) return '0';
    return (d > 0 ? '+' : '') + fmtNum(d);
  }

  function diffRevStr(a: number, b: number): string {
    const d = b - a;
    if (d === 0) return 'Ks 0';
    const prefix = d > 0 ? '+' : '-';
    const abs = Math.abs(d);
    if (abs >= 1_000_000_000) return prefix + 'Ks ' + (abs / 1_000_000_000).toFixed(1) + 'B';
    if (abs >= 1_000_000) return prefix + 'Ks ' + (abs / 1_000_000).toFixed(1) + 'M';
    if (abs >= 1_000) return prefix + 'Ks ' + (abs / 1_000).toFixed(1) + 'K';
    return prefix + 'Ks ' + abs.toFixed(0);
  }

  function diffColor(a: number, b: number): string {
    if (b > a) return 'var(--success)';
    if (b < a) return 'var(--danger)';
    return 'var(--text-muted)';
  }
</script>

<div class="page">
  <!-- Page title -->
  <div class="section-head">
    <span class="dot"></span>
    <div>
      <h2>Job Comparison</h2>
      <div class="section-sub">Outlet movement tracker between two classification runs</div>
    </div>
  </div>

  <!-- Job selectors -->
  <div class="selector-grid">
    <!-- Job 1 -->
    <div class="card">
      <span class="badge badge-f4">Job 1 · Baseline</span>
      <label class="label" for="job1-select">Select baseline job</label>
      <select id="job1-select" class="select" bind:value={job1}>
        <option value="">— Select baseline job —</option>
        {#each jobs as j}
          <option value={j.job_id}>{j.job_id} ({j.total_outlets || '?'} outlets)</option>
        {/each}
      </select>
    </div>

    <!-- Job 2 -->
    <div class="card">
      <span class="badge badge-c">Job 2 · Current</span>
      <label class="label" for="job2-select">Select current job</label>
      <select id="job2-select" class="select" bind:value={job2}>
        <option value="">— Select current job —</option>
        {#each jobs as j}
          <option value={j.job_id}>{j.job_id} ({j.total_outlets || '?'} outlets)</option>
        {/each}
      </select>
    </div>
  </div>

  <!-- Compare button -->
  <div class="compare-action">
    <button class="btn" onclick={runCompare} disabled={loading}>
      {loading ? 'Comparing…' : 'Compare'}
    </button>
  </div>

  <!-- Error -->
  {#if error}
    <div class="alert alert-danger">{error}</div>
  {/if}

  <!-- Results -->
  {#if result}
    <!-- Movement Summary KPIs -->
    <div class="grid-kpi">
      <div class="kpi">
        <span class="kpi-label">Upgraded</span>
        <span class="kpi-value" style="color:var(--success);">{result.summary.upgraded}</span>
        <span class="kpi-sub">Outlets moved up</span>
      </div>
      <div class="kpi">
        <span class="kpi-label">Downgraded</span>
        <span class="kpi-value" style="color:var(--danger);">{result.summary.downgraded}</span>
        <span class="kpi-sub">Outlets moved down</span>
      </div>
      <div class="kpi">
        <span class="kpi-label">New</span>
        <span class="kpi-value" style="color:var(--info);">{result.summary.new_outlets}</span>
        <span class="kpi-sub">New outlets</span>
      </div>
      <div class="kpi">
        <span class="kpi-label">Lost</span>
        <span class="kpi-value" style="color:var(--warning);">{result.summary.lost_outlets}</span>
        <span class="kpi-sub">Outlets removed</span>
      </div>
    </div>

    <!-- Side-by-side stats table -->
    <div class="data-table-wrap">
      <div class="data-table-head">
        <span class="title">Side-by-side statistics</span>
      </div>
      <div class="table-scroll">
        <table class="data-table">
          <thead>
            <tr>
              <th>Metric</th>
              <th class="num-col">Job 1 · Baseline</th>
              <th class="num-col">Job 2 · Current</th>
              <th class="num-col">Change</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td class="metric-cell">Total outlets</td>
              <td class="num">{fmtNum(result.job1.stats.total)}</td>
              <td class="num">{fmtNum(result.job2.stats.total)}</td>
              <td class="num change" style="color:{diffColor(result.job1.stats.total, result.job2.stats.total)};">
                {diffStr(result.job1.stats.total, result.job2.stats.total)}
              </td>
            </tr>
            <tr>
              <td class="metric-cell">Class A</td>
              <td class="num">{fmtNum(result.job1.stats.class_a)}</td>
              <td class="num">{fmtNum(result.job2.stats.class_a)}</td>
              <td class="num change" style="color:{diffColor(result.job1.stats.class_a, result.job2.stats.class_a)};">
                {diffStr(result.job1.stats.class_a, result.job2.stats.class_a)}
              </td>
            </tr>
            <tr>
              <td class="metric-cell">Class B</td>
              <td class="num">{fmtNum(result.job1.stats.class_b)}</td>
              <td class="num">{fmtNum(result.job2.stats.class_b)}</td>
              <td class="num change" style="color:{diffColor(result.job1.stats.class_b, result.job2.stats.class_b)};">
                {diffStr(result.job1.stats.class_b, result.job2.stats.class_b)}
              </td>
            </tr>
            <tr>
              <td class="metric-cell">Class C</td>
              <td class="num">{fmtNum(result.job1.stats.class_c)}</td>
              <td class="num">{fmtNum(result.job2.stats.class_c)}</td>
              <td class="num change" style="color:{diffColor(result.job1.stats.class_c, result.job2.stats.class_c)};">
                {diffStr(result.job1.stats.class_c, result.job2.stats.class_c)}
              </td>
            </tr>
            <tr>
              <td class="metric-cell">Revenue</td>
              <td class="num">{fmt(result.job1.stats.revenue)}</td>
              <td class="num">{fmt(result.job2.stats.revenue)}</td>
              <td class="num change" style="color:{diffColor(result.job1.stats.revenue, result.job2.stats.revenue)};">
                {diffRevStr(result.job1.stats.revenue, result.job2.stats.revenue)}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Movement detail table -->
    {#if result.movements.length > 0}
      <div class="data-table-wrap">
        <div class="data-table-head">
          <span class="title">Outlet movement details</span>
          <span class="meta">
            {result.movements.length} movements {result.movements.length >= 500 ? '(capped at 500)' : ''}
          </span>
        </div>
        <div class="table-scroll movement-scroll">
          <table class="data-table">
            <thead>
              <tr>
                <th>Code</th>
                <th>Name</th>
                <th>Branch</th>
                <th class="center-col">From</th>
                <th class="center-col">To</th>
                <th class="center-col">Status</th>
              </tr>
            </thead>
            <tbody>
              {#each result.movements as m}
                <tr>
                  <td class="num">{m.code}</td>
                  <td class="name-cell">{m.name}</td>
                  <td>{m.branch}</td>
                  <td class="center-col">
                    <span class="badge badge-neutral">{m.from}</span>
                  </td>
                  <td class="center-col">
                    <span class="badge badge-neutral">{m.to}</span>
                  </td>
                  <td class="center-col">
                    <span class="badge {m.status === 'UPGRADED' ? 'badge-a' : 'badge-c'}">
                      {m.status === 'UPGRADED' ? 'Upgraded' : 'Downgraded'}
                    </span>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>
    {:else}
      <div class="alert alert-info">No classification movements detected between these jobs.</div>
    {/if}

    <!-- Unchanged count -->
    <div class="footnote">
      {fmtNum(result.summary.unchanged)} outlets unchanged · {fmtNum(result.summary.total_changes)} total changes
    </div>
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

  .selector-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-bottom: 16px;
  }

  .selector-grid .card {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .selector-grid .badge {
    align-self: flex-start;
  }

  .selector-grid .label {
    margin: 0;
  }

  .compare-action {
    display: flex;
    justify-content: center;
    margin: 8px 0 28px;
  }

  .compare-action .btn {
    min-width: 220px;
    justify-content: center;
  }

  .alert {
    margin-bottom: 24px;
  }

  .grid-kpi {
    margin-bottom: 24px;
  }

  .data-table-wrap {
    margin-bottom: 24px;
  }

  .table-scroll {
    overflow-x: auto;
  }

  .movement-scroll {
    max-height: 500px;
    overflow-y: auto;
  }

  .num-col,
  .num {
    text-align: right;
  }

  .center-col {
    text-align: center;
  }

  .num {
    font-family: var(--font-mono);
  }

  .change {
    font-weight: 600;
  }

  .metric-cell {
    font-weight: 600;
  }

  .name-cell {
    max-width: 220px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .footnote {
    text-align: center;
    margin-top: 4px;
    font-size: 12px;
    color: var(--text-faint);
  }

  @media (max-width: 720px) {
    .selector-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
