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
      error = 'SELECT BOTH JOBS';
      return;
    }
    if (job1 === job2) {
      error = 'SELECT TWO DIFFERENT JOBS';
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
    if (n >= 1_000_000_000) return '$' + (n / 1_000_000_000).toFixed(1) + 'B';
    if (n >= 1_000_000) return '$' + (n / 1_000_000).toFixed(1) + 'M';
    if (n >= 1_000) return '$' + (n / 1_000).toFixed(1) + 'K';
    return '$' + n.toFixed(0);
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
    if (d === 0) return '$0';
    const prefix = d > 0 ? '+' : '-';
    const abs = Math.abs(d);
    if (abs >= 1_000_000_000) return prefix + '$' + (abs / 1_000_000_000).toFixed(1) + 'B';
    if (abs >= 1_000_000) return prefix + '$' + (abs / 1_000_000).toFixed(1) + 'M';
    if (abs >= 1_000) return prefix + '$' + (abs / 1_000).toFixed(1) + 'K';
    return prefix + '$' + abs.toFixed(0);
  }

  function diffColor(a: number, b: number): string {
    if (b > a) return '#007518';
    if (b < a) return '#be2d06';
    return '#383832';
  }
</script>

<div style="
  padding: 80px 24px 40px;
  max-width: 1200px;
  margin: 0 auto;
  font-family: 'Space Grotesk', sans-serif;
">
  <!-- Page title -->
  <div style="
    background: #383832; color: #00fc40;
    padding: 10px 20px; font-weight: 900; font-size: 1.1rem;
    letter-spacing: 0.08em; margin-bottom: 24px;
    border: 2px solid #383832; box-shadow: 4px 4px 0 #383832;
    display: inline-block;
  ">
    JOB COMPARISON // OUTLET MOVEMENT TRACKER
  </div>

  <!-- Job selectors -->
  <div style="
    display: grid; grid-template-columns: 1fr 1fr; gap: 20px;
    margin-bottom: 20px;
  ">
    <!-- Job 1 -->
    <div style="
      border: 3px solid #383832; padding: 16px;
      background: #feffd6; box-shadow: 4px 4px 0 #383832;
    ">
      <div style="
        background: #006f7c; color: white; padding: 6px 12px;
        font-weight: 900; font-size: 11px; letter-spacing: 0.12em;
        margin-bottom: 12px; display: inline-block;
        border: 2px solid #383832;
      ">
        JOB 1 (BASELINE)
      </div>
      <select
        bind:value={job1}
        style="
          width: 100%; padding: 10px 12px; font-family: 'Space Grotesk', monospace;
          font-size: 13px; font-weight: 700;
          border: 2px solid #383832; background: white; color: #383832;
          cursor: pointer; appearance: auto;
        "
      >
        <option value="">-- SELECT BASELINE JOB --</option>
        {#each jobs as j}
          <option value={j.job_id}>{j.job_id} ({j.total_outlets || '?'} outlets)</option>
        {/each}
      </select>
    </div>

    <!-- Job 2 -->
    <div style="
      border: 3px solid #383832; padding: 16px;
      background: #feffd6; box-shadow: 4px 4px 0 #383832;
    ">
      <div style="
        background: #9d4867; color: white; padding: 6px 12px;
        font-weight: 900; font-size: 11px; letter-spacing: 0.12em;
        margin-bottom: 12px; display: inline-block;
        border: 2px solid #383832;
      ">
        JOB 2 (CURRENT)
      </div>
      <select
        bind:value={job2}
        style="
          width: 100%; padding: 10px 12px; font-family: 'Space Grotesk', monospace;
          font-size: 13px; font-weight: 700;
          border: 2px solid #383832; background: white; color: #383832;
          cursor: pointer; appearance: auto;
        "
      >
        <option value="">-- SELECT CURRENT JOB --</option>
        {#each jobs as j}
          <option value={j.job_id}>{j.job_id} ({j.total_outlets || '?'} outlets)</option>
        {/each}
      </select>
    </div>
  </div>

  <!-- Compare button -->
  <div style="text-align: center; margin-bottom: 32px;">
    <button
      onclick={runCompare}
      disabled={loading}
      style="
        padding: 14px 48px; background: {loading ? '#999' : '#00fc40'};
        color: #383832; border: 3px solid #383832;
        font-family: 'Space Grotesk', sans-serif;
        font-size: 14px; font-weight: 900; letter-spacing: 0.12em;
        cursor: {loading ? 'wait' : 'pointer'};
        box-shadow: 4px 4px 0 #383832;
        transition: transform 0.1s, box-shadow 0.1s;
      "
      onmousedown={(e) => {
        e.currentTarget.style.transform = 'translate(2px, 2px)';
        e.currentTarget.style.boxShadow = '2px 2px 0 #383832';
      }}
      onmouseup={(e) => {
        e.currentTarget.style.transform = 'translate(0, 0)';
        e.currentTarget.style.boxShadow = '4px 4px 0 #383832';
      }}
    >
      {loading ? 'COMPARING...' : 'COMPARE'}
    </button>
  </div>

  <!-- Error -->
  {#if error}
    <div style="
      background: #be2d06; color: white; padding: 12px 16px;
      font-weight: 900; font-size: 12px; letter-spacing: 0.08em;
      border: 2px solid #383832; margin-bottom: 24px;
      box-shadow: 3px 3px 0 #383832;
    ">
      ERROR: {error}
    </div>
  {/if}

  <!-- Results -->
  {#if result}
    <!-- Movement Summary KPIs -->
    <div style="
      display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px;
      margin-bottom: 28px;
    ">
      <!-- Upgraded -->
      <div style="
        border: 3px solid #383832; padding: 16px; background: #feffd6;
        box-shadow: 4px 4px 0 #383832; text-align: center;
      ">
        <div style="
          background: #007518; color: white; padding: 4px 10px;
          font-size: 10px; font-weight: 900; letter-spacing: 0.12em;
          display: inline-block; border: 2px solid #383832; margin-bottom: 10px;
        ">UPGRADED</div>
        <div style="font-size: 2.2rem; font-weight: 900; color: #007518; line-height: 1;">
          {result.summary.upgraded}
        </div>
        <div style="font-size: 10px; color: #666; font-weight: 700; margin-top: 4px; letter-spacing: 0.05em;">
          OUTLETS MOVED UP
        </div>
      </div>

      <!-- Downgraded -->
      <div style="
        border: 3px solid #383832; padding: 16px; background: #feffd6;
        box-shadow: 4px 4px 0 #383832; text-align: center;
      ">
        <div style="
          background: #be2d06; color: white; padding: 4px 10px;
          font-size: 10px; font-weight: 900; letter-spacing: 0.12em;
          display: inline-block; border: 2px solid #383832; margin-bottom: 10px;
        ">DOWNGRADED</div>
        <div style="font-size: 2.2rem; font-weight: 900; color: #be2d06; line-height: 1;">
          {result.summary.downgraded}
        </div>
        <div style="font-size: 10px; color: #666; font-weight: 700; margin-top: 4px; letter-spacing: 0.05em;">
          OUTLETS MOVED DOWN
        </div>
      </div>

      <!-- New -->
      <div style="
        border: 3px solid #383832; padding: 16px; background: #feffd6;
        box-shadow: 4px 4px 0 #383832; text-align: center;
      ">
        <div style="
          background: #006f7c; color: white; padding: 4px 10px;
          font-size: 10px; font-weight: 900; letter-spacing: 0.12em;
          display: inline-block; border: 2px solid #383832; margin-bottom: 10px;
        ">NEW</div>
        <div style="font-size: 2.2rem; font-weight: 900; color: #006f7c; line-height: 1;">
          {result.summary.new_outlets}
        </div>
        <div style="font-size: 10px; color: #666; font-weight: 700; margin-top: 4px; letter-spacing: 0.05em;">
          NEW OUTLETS
        </div>
      </div>

      <!-- Lost -->
      <div style="
        border: 3px solid #383832; padding: 16px; background: #feffd6;
        box-shadow: 4px 4px 0 #383832; text-align: center;
      ">
        <div style="
          background: #ff9d00; color: #383832; padding: 4px 10px;
          font-size: 10px; font-weight: 900; letter-spacing: 0.12em;
          display: inline-block; border: 2px solid #383832; margin-bottom: 10px;
        ">LOST</div>
        <div style="font-size: 2.2rem; font-weight: 900; color: #ff9d00; line-height: 1;">
          {result.summary.lost_outlets}
        </div>
        <div style="font-size: 10px; color: #666; font-weight: 700; margin-top: 4px; letter-spacing: 0.05em;">
          OUTLETS REMOVED
        </div>
      </div>
    </div>

    <!-- Side-by-side stats table -->
    <div style="
      border: 3px solid #383832; background: #feffd6;
      box-shadow: 4px 4px 0 #383832; margin-bottom: 28px;
    ">
      <div style="
        background: #383832; color: #feffd6; padding: 10px 16px;
        font-weight: 900; font-size: 12px; letter-spacing: 0.1em;
      ">
        SIDE-BY-SIDE STATISTICS
      </div>
      <div style="overflow-x: auto;">
        <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
          <thead>
            <tr style="background: #383832; color: #feffd6;">
              <th style="padding: 10px 16px; text-align: left; font-weight: 900; font-size: 11px; letter-spacing: 0.08em; border-right: 2px solid #555;">METRIC</th>
              <th style="padding: 10px 16px; text-align: right; font-weight: 900; font-size: 11px; letter-spacing: 0.08em; border-right: 2px solid #555;">JOB 1 (BASELINE)</th>
              <th style="padding: 10px 16px; text-align: right; font-weight: 900; font-size: 11px; letter-spacing: 0.08em; border-right: 2px solid #555;">JOB 2 (CURRENT)</th>
              <th style="padding: 10px 16px; text-align: right; font-weight: 900; font-size: 11px; letter-spacing: 0.08em;">CHANGE</th>
            </tr>
          </thead>
          <tbody>
            <tr style="border-bottom: 2px solid #e0e0c0;">
              <td style="padding: 10px 16px; font-weight: 900; letter-spacing: 0.05em;">TOTAL OUTLETS</td>
              <td style="padding: 10px 16px; text-align: right; font-family: monospace; font-weight: 700;">{fmtNum(result.job1.stats.total)}</td>
              <td style="padding: 10px 16px; text-align: right; font-family: monospace; font-weight: 700;">{fmtNum(result.job2.stats.total)}</td>
              <td style="padding: 10px 16px; text-align: right; font-family: monospace; font-weight: 900; color: {diffColor(result.job1.stats.total, result.job2.stats.total)};">
                {diffStr(result.job1.stats.total, result.job2.stats.total)}
              </td>
            </tr>
            <tr style="border-bottom: 2px solid #e0e0c0;">
              <td style="padding: 10px 16px; font-weight: 900; letter-spacing: 0.05em;">CLASS A</td>
              <td style="padding: 10px 16px; text-align: right; font-family: monospace; font-weight: 700;">{fmtNum(result.job1.stats.class_a)}</td>
              <td style="padding: 10px 16px; text-align: right; font-family: monospace; font-weight: 700;">{fmtNum(result.job2.stats.class_a)}</td>
              <td style="padding: 10px 16px; text-align: right; font-family: monospace; font-weight: 900; color: {diffColor(result.job1.stats.class_a, result.job2.stats.class_a)};">
                {diffStr(result.job1.stats.class_a, result.job2.stats.class_a)}
              </td>
            </tr>
            <tr style="border-bottom: 2px solid #e0e0c0;">
              <td style="padding: 10px 16px; font-weight: 900; letter-spacing: 0.05em;">CLASS B</td>
              <td style="padding: 10px 16px; text-align: right; font-family: monospace; font-weight: 700;">{fmtNum(result.job1.stats.class_b)}</td>
              <td style="padding: 10px 16px; text-align: right; font-family: monospace; font-weight: 700;">{fmtNum(result.job2.stats.class_b)}</td>
              <td style="padding: 10px 16px; text-align: right; font-family: monospace; font-weight: 900; color: {diffColor(result.job1.stats.class_b, result.job2.stats.class_b)};">
                {diffStr(result.job1.stats.class_b, result.job2.stats.class_b)}
              </td>
            </tr>
            <tr style="border-bottom: 2px solid #e0e0c0;">
              <td style="padding: 10px 16px; font-weight: 900; letter-spacing: 0.05em;">CLASS C</td>
              <td style="padding: 10px 16px; text-align: right; font-family: monospace; font-weight: 700;">{fmtNum(result.job1.stats.class_c)}</td>
              <td style="padding: 10px 16px; text-align: right; font-family: monospace; font-weight: 700;">{fmtNum(result.job2.stats.class_c)}</td>
              <td style="padding: 10px 16px; text-align: right; font-family: monospace; font-weight: 900; color: {diffColor(result.job1.stats.class_c, result.job2.stats.class_c)};">
                {diffStr(result.job1.stats.class_c, result.job2.stats.class_c)}
              </td>
            </tr>
            <tr>
              <td style="padding: 10px 16px; font-weight: 900; letter-spacing: 0.05em;">REVENUE</td>
              <td style="padding: 10px 16px; text-align: right; font-family: monospace; font-weight: 700;">{fmt(result.job1.stats.revenue)}</td>
              <td style="padding: 10px 16px; text-align: right; font-family: monospace; font-weight: 700;">{fmt(result.job2.stats.revenue)}</td>
              <td style="padding: 10px 16px; text-align: right; font-family: monospace; font-weight: 900; color: {diffColor(result.job1.stats.revenue, result.job2.stats.revenue)};">
                {diffRevStr(result.job1.stats.revenue, result.job2.stats.revenue)}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Movement detail table -->
    {#if result.movements.length > 0}
      <div style="
        border: 3px solid #383832; background: #feffd6;
        box-shadow: 4px 4px 0 #383832; margin-bottom: 28px;
      ">
        <div style="
          background: #383832; color: #feffd6; padding: 10px 16px;
          font-weight: 900; font-size: 12px; letter-spacing: 0.1em;
          display: flex; justify-content: space-between; align-items: center;
        ">
          <span>OUTLET MOVEMENT DETAILS</span>
          <span style="font-size: 10px; color: #aaa; font-weight: 700;">
            {result.movements.length} MOVEMENTS {result.movements.length >= 500 ? '(CAPPED AT 500)' : ''}
          </span>
        </div>
        <div style="overflow-x: auto; max-height: 500px; overflow-y: auto;">
          <table style="width: 100%; border-collapse: collapse; font-size: 12px;">
            <thead>
              <tr style="background: #383832; color: #feffd6; position: sticky; top: 0;">
                <th style="padding: 8px 12px; text-align: left; font-weight: 900; font-size: 10px; letter-spacing: 0.08em; border-right: 1px solid #555;">CODE</th>
                <th style="padding: 8px 12px; text-align: left; font-weight: 900; font-size: 10px; letter-spacing: 0.08em; border-right: 1px solid #555;">NAME</th>
                <th style="padding: 8px 12px; text-align: left; font-weight: 900; font-size: 10px; letter-spacing: 0.08em; border-right: 1px solid #555;">BRANCH</th>
                <th style="padding: 8px 12px; text-align: center; font-weight: 900; font-size: 10px; letter-spacing: 0.08em; border-right: 1px solid #555;">FROM</th>
                <th style="padding: 8px 12px; text-align: center; font-weight: 900; font-size: 10px; letter-spacing: 0.08em; border-right: 1px solid #555;">TO</th>
                <th style="padding: 8px 12px; text-align: center; font-weight: 900; font-size: 10px; letter-spacing: 0.08em;">STATUS</th>
              </tr>
            </thead>
            <tbody>
              {#each result.movements as m, i}
                <tr style="border-bottom: 1px solid #e0e0c0; background: {i % 2 === 0 ? '#feffd6' : '#f8f8d0'};">
                  <td style="padding: 8px 12px; font-family: monospace; font-weight: 700; font-size: 11px;">{m.code}</td>
                  <td style="padding: 8px 12px; font-size: 11px; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{m.name}</td>
                  <td style="padding: 8px 12px; font-size: 11px;">{m.branch}</td>
                  <td style="padding: 8px 12px; text-align: center;">
                    <span style="
                      display: inline-block; padding: 2px 8px;
                      font-size: 10px; font-weight: 900; letter-spacing: 0.05em;
                      border: 2px solid #383832; background: #e0e0c0;
                    ">{m.from}</span>
                  </td>
                  <td style="padding: 8px 12px; text-align: center;">
                    <span style="
                      display: inline-block; padding: 2px 8px;
                      font-size: 10px; font-weight: 900; letter-spacing: 0.05em;
                      border: 2px solid #383832; background: #e0e0c0;
                    ">{m.to}</span>
                  </td>
                  <td style="padding: 8px 12px; text-align: center;">
                    <span style="
                      display: inline-block; padding: 3px 10px;
                      font-size: 10px; font-weight: 900; letter-spacing: 0.08em;
                      border: 2px solid #383832;
                      background: {m.status === 'UPGRADED' ? '#007518' : '#be2d06'};
                      color: white;
                      box-shadow: 2px 2px 0 #383832;
                    ">{m.status}</span>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>
    {:else}
      <div style="
        border: 3px solid #383832; padding: 24px; background: #feffd6;
        box-shadow: 4px 4px 0 #383832; text-align: center;
        font-weight: 900; font-size: 13px; letter-spacing: 0.08em; color: #666;
      ">
        NO CLASSIFICATION MOVEMENTS DETECTED BETWEEN THESE JOBS
      </div>
    {/if}

    <!-- Unchanged count -->
    <div style="
      text-align: center; margin-top: 16px;
      font-size: 11px; font-weight: 700; color: #999; letter-spacing: 0.08em;
    ">
      {fmtNum(result.summary.unchanged)} OUTLETS UNCHANGED // {fmtNum(result.summary.total_changes)} TOTAL CHANGES
    </div>
  {/if}
</div>
