<script lang="ts">
  import { onMount } from 'svelte';
  import { auth } from '$lib/stores/auth.svelte';
  import { getAnalytics, getAuditFiltered, setUserDisabled, getCockpit } from '$lib/api';

  // ── state ───────────────────────────────────────────────
  let data = $state<any>(null);
  let loading = $state(true);
  let error = $state('');

  // active tab — key-based so chip order is independent of render order
  const TABS = [
    { key: 'pulse',   label: 'Pulse' },
    { key: 'trends',  label: 'Trends' },
    { key: 'users',   label: 'Users' },
    { key: 'actions', label: 'Actions' },
    { key: 'audit',   label: 'Audit Log' },
  ];
  let activeTab = $state('pulse');

  // ── Pulse (live cockpit) ────────────────────────────────
  let ck = $state<any>(null);
  let ckDays = $state(7);
  const CK_RANGES = [{ v: 1, l: '24h' }, { v: 7, l: '7 days' }, { v: 30, l: '30 days' }];
  async function loadCockpit() { try { ck = await getCockpit(ckDays); } catch { /* ignore */ } }
  function ckRange(v: number) { ckDays = v; loadCockpit(); }
  function kfmt(n: number): string {
    if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
    if (n >= 1e3) return (n / 1e3).toFixed(1) + 'k';
    return String(n ?? 0);
  }
  function usd(n: number): string { return '$' + (n ?? 0).toFixed(2); }
  function rel(s: string): string {
    if (!s) return '';
    const m = Math.floor((Date.now() - new Date(s).getTime()) / 60000);
    if (m < 1) return 'just now';
    if (m < 60) return `${m}m ago`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h}h ago`;
    return `${Math.floor(h / 24)}d ago`;
  }
  function ckAvatar(l: string) { return l === 'error' ? '✕' : l === 'warn' ? '!' : l === 'info' ? '→' : 'OK'; }
  const ckTrendMax = $derived(Math.max(1, ...((ck?.cost_trend ?? []).map((t: any) => t.cost))));
  const ckTokTotal = $derived(((ck?.tokens?.prompt ?? 0) + (ck?.tokens?.completion ?? 0)) || 1);

  // user table sort
  let userSortCol = $state<string>('login_count');
  let userSortDir = $state<'asc' | 'desc'>('desc');
  let togglingId = $state<number | null>(null);

  // audit explorer
  let fUsername = $state('');
  let fAction = $state('');
  let fDateFrom = $state('');
  let fDateTo = $state('');
  let fQuery = $state('');
  let auditRows = $state<any[]>([]);
  let auditLoading = $state(false);
  let auditError = $state('');

  // ── load ────────────────────────────────────────────────
  onMount(() => {
    if (!auth.hasPerm('analytics')) {
      loading = false;
      return;
    }
    loadAnalytics();
    loadAudit();
    loadCockpit();
    const iv = setInterval(loadCockpit, 30000);
    return () => clearInterval(iv);
  });

  async function loadAnalytics() {
    loading = true;
    error = '';
    try {
      data = await getAnalytics();
    } catch (e: any) {
      error = e?.message || 'Failed to load analytics';
    } finally {
      loading = false;
    }
  }

  async function loadAudit() {
    auditLoading = true;
    auditError = '';
    try {
      const params: Record<string, string> = {};
      if (fUsername.trim()) params.username = fUsername.trim();
      if (fAction) params.action = fAction;
      if (fDateFrom) params.date_from = fDateFrom;
      if (fDateTo) params.date_to = fDateTo;
      if (fQuery.trim()) params.q = fQuery.trim();
      params.limit = '200';
      auditRows = await getAuditFiltered(params);
    } catch (e: any) {
      auditError = e?.message || 'Failed to load audit log';
    } finally {
      auditLoading = false;
    }
  }

  async function toggleUser(u: any) {
    togglingId = u.id;
    try {
      await setUserDisabled(u.id, !u.disabled);
      await loadAnalytics();
    } catch (e: any) {
      error = e?.message || 'Failed to update user';
    } finally {
      togglingId = null;
    }
  }

  // ── formatting helpers ──────────────────────────────────
  function fmtDate(v: string | null): string {
    if (!v) return '—';
    const d = new Date(v);
    return isNaN(d.getTime()) ? v : d.toLocaleString();
  }
  function fmtNum(n: number | null | undefined): string {
    return (n ?? 0).toLocaleString();
  }
  function fmtHour(h: number | null): string {
    if (h === null || h === undefined) return '—';
    const ampm = h < 12 ? 'AM' : 'PM';
    const hr = h % 12 === 0 ? 12 : h % 12;
    return `${hr}:00 ${ampm}`;
  }

  // ── overview derived ────────────────────────────────────
  let monthDelta = $derived(
    data ? (data.overview.jobs_this_month - data.overview.jobs_last_month) : 0
  );

  // ── user table sort ─────────────────────────────────────
  function toggleUserSort(col: string) {
    if (userSortCol === col) {
      userSortDir = userSortDir === 'asc' ? 'desc' : 'asc';
    } else {
      userSortCol = col;
      userSortDir = 'desc';
    }
  }

  let sortedUsers = $derived.by(() => {
    if (!data?.users) return [];
    const rows = [...data.users];
    const col = userSortCol;
    return rows.sort((a: any, b: any) => {
      let av = a[col];
      let bv = b[col];
      if (col === 'last_login' || col === 'last_active') {
        av = av ? new Date(av).getTime() : 0;
        bv = bv ? new Date(bv).getTime() : 0;
      }
      if (typeof av === 'string' && typeof bv === 'string') {
        return userSortDir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av);
      }
      av = av ?? 0;
      bv = bv ?? 0;
      return userSortDir === 'asc' ? av - bv : bv - av;
    });
  });

  const userCols = [
    { key: 'username', label: 'User' },
    { key: 'role', label: 'Role' },
    { key: 'source', label: 'Source' },
    { key: 'last_login', label: 'Last Login' },
    { key: 'login_count', label: 'Logins' },
    { key: 'jobs_run', label: 'Jobs' },
    { key: 'exports', label: 'Exports' },
    { key: 'last_active', label: 'Last Active' },
  ];

  // ── trend chart geometry ────────────────────────────────
  const CW = 700, CH = 220;
  const M = { top: 16, right: 16, bottom: 30, left: 40 };
  const plotW = CW - M.left - M.right;
  const plotH = CH - M.top - M.bottom;

  let trendChart = $derived.by(() => {
    const t = data?.trend ?? [];
    if (!t.length) return null;
    const maxY = Math.max(
      1,
      ...t.map((d: any) => Math.max(d.logins, d.jobs, d.actions))
    );
    const n = t.length;
    const x = (i: number) => M.left + (n === 1 ? plotW / 2 : (i / (n - 1)) * plotW);
    const y = (v: number) => M.top + plotH - (v / maxY) * plotH;
    const line = (key: string) =>
      t.map((d: any, i: number) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(d[key]).toFixed(1)}`).join(' ');
    // x-axis labels: ~5 evenly spaced
    const labelIdx: number[] = [];
    const step = Math.max(1, Math.floor((n - 1) / 4));
    for (let i = 0; i < n; i += step) labelIdx.push(i);
    if (labelIdx[labelIdx.length - 1] !== n - 1) labelIdx.push(n - 1);
    const xLabels = labelIdx.map((i) => ({
      x: x(i),
      label: (t[i].date || '').slice(5), // MM-DD
    }));
    return {
      maxY,
      logins: line('logins'),
      jobs: line('jobs'),
      actions: line('actions'),
      xLabels,
      baselineY: M.top + plotH,
    };
  });

  // ── action breakdown bar chart ──────────────────────────
  let actionChart = $derived.by(() => {
    const a = data?.actions ?? [];
    if (!a.length) return null;
    const maxC = Math.max(1, ...a.map((d: any) => d.count));
    const rowH = 26;
    const labelW = 130;
    const barMax = 460;
    const height = a.length * rowH + 10;
    return {
      rows: a.map((d: any, i: number) => ({
        action: d.action,
        count: d.count,
        y: 5 + i * rowH,
        w: (d.count / maxC) * barMax,
      })),
      height,
      rowH,
      labelW,
      barMax,
    };
  });

  // ── auth ratio ──────────────────────────────────────────
  let authRatio = $derived.by(() => {
    if (!data?.auth) return { local: 0, ldap: 0 };
    const l = data.auth.local_logins || 0;
    const d = data.auth.ldap_logins || 0;
    const tot = l + d;
    return {
      local: tot ? (l / tot) * 100 : 0,
      ldap: tot ? (d / tot) * 100 : 0,
    };
  });

  // ── audit badge class ───────────────────────────────────
  function actionBadge(action: string): string {
    if (action === 'LOGIN') return 'badge badge-a';
    if (action === 'LOGIN_FAILED') return 'badge badge-c';
    if (action === 'EXPORT') return 'badge badge-b';
    return 'badge badge-neutral';
  }

  // ── CSV export of filtered audit rows ───────────────────
  function exportAuditCsv() {
    const headers = ['id', 'timestamp', 'username', 'action', 'details', 'ip_address'];
    const esc = (v: any) => {
      const s = v === null || v === undefined ? '' : String(v);
      return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };
    const lines = [headers.join(',')];
    for (const r of auditRows) {
      lines.push(headers.map((h) => esc(r[h])).join(','));
    }
    const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `audit_log_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const ACTION_OPTIONS = [
    { value: '', label: 'All actions' },
    { value: 'LOGIN', label: 'LOGIN' },
    { value: 'LOGIN_FAILED', label: 'LOGIN_FAILED' },
    { value: 'CLASSIFY', label: 'CLASSIFY' },
    { value: 'EXPORT', label: 'EXPORT' },
    { value: 'SETTINGS', label: 'SETTINGS' },
    { value: 'CREATE_USER', label: 'CREATE_USER' },
    { value: 'DELETE_USER', label: 'DELETE_USER' },
  ];
</script>

<svelte:head>
  <title>Ops Cockpit | RTM Agent</title>
</svelte:head>

{#if !auth.hasPerm('analytics')}
  <div class="page animate-fade-in">
    <div class="alert alert-danger">
      Access denied &mdash; you do not have the Analytics permission.
    </div>
  </div>
{:else}
  <div class="page animate-fade-in">

    <header class="page-head">
      <h1>Ops Cockpit</h1>
      <p>Live operations &mdash; jobs, tokens, cost, models, logins and full audit</p>
    </header>

    {#if loading}
      <div class="grid-kpi" style="margin-bottom:1.5rem;">
        {#each Array(7) as _}
          <div class="kpi">
            <div class="skeleton" style="height:12px;width:60%;"></div>
            <div class="skeleton" style="height:30px;width:45%;margin-top:8px;"></div>
          </div>
        {/each}
      </div>
      <div class="skeleton" style="height:240px;width:100%;margin-bottom:1.5rem;"></div>
      <div class="skeleton" style="height:300px;width:100%;"></div>
    {:else if error}
      <div class="alert alert-danger">Error: {error}</div>
    {:else if data}

      <div class="tab-bar">
        {#each TABS as t}
          <button class="tab" class:active={activeTab === t.key} onclick={() => activeTab = t.key}>
            {t.label}
          </button>
        {/each}
      </div>

      {#if activeTab === 'trends'}
      <!-- ════ ACTIVITY TREND ════ -->
      <div class="section-head">
        <span class="dot"></span>
        <h2>Activity Trend</h2>
      </div>
      <p class="section-sub" style="margin-bottom:12px;">Logins, jobs and total actions over the last 30 days</p>

      <div class="card">
        {#if trendChart}
          <div class="legend">
            <span class="legend-item"><span class="legend-line" style="background:var(--accent);"></span>Logins</span>
            <span class="legend-item"><span class="legend-line" style="background:var(--success);"></span>Jobs</span>
            <span class="legend-item"><span class="legend-line" style="background:var(--info);"></span>Actions</span>
          </div>
          <svg viewBox="0 0 {CW} {CH}" class="chart" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Activity trend chart">
            <!-- y grid -->
            <line x1={M.left} y1={M.top} x2={M.left} y2={trendChart.baselineY} stroke="var(--border-strong)" stroke-width="1" />
            <line x1={M.left} y1={trendChart.baselineY} x2={CW - M.right} y2={trendChart.baselineY} stroke="var(--border-strong)" stroke-width="1" />
            <!-- y max label -->
            <text x={M.left - 6} y={M.top + 4} text-anchor="end" class="axis-label">{trendChart.maxY}</text>
            <text x={M.left - 6} y={trendChart.baselineY} text-anchor="end" class="axis-label">0</text>
            <!-- x labels -->
            {#each trendChart.xLabels as xl}
              <text x={xl.x} y={CH - 10} text-anchor="middle" class="axis-label">{xl.label}</text>
            {/each}
            <!-- lines -->
            <path d={trendChart.actions} fill="none" stroke="var(--info)" stroke-width="2" stroke-linejoin="round" />
            <path d={trendChart.jobs} fill="none" stroke="var(--success)" stroke-width="2" stroke-linejoin="round" />
            <path d={trendChart.logins} fill="none" stroke="var(--accent)" stroke-width="2" stroke-linejoin="round" />
          </svg>
        {:else}
          <p class="empty">No trend data available.</p>
        {/if}
      </div>

      {:else if activeTab === 'users'}
      <!-- ════ 3. USER ANALYTICS + MANAGEMENT ════ -->
      <div class="section-head">
        <span class="dot"></span>
        <h2>User Analytics &amp; Management</h2>
      </div>
      <p class="section-sub" style="margin-bottom:12px;">Per-user activity. Disable revokes access; super-admins cannot be disabled.</p>

      <div class="data-table-wrap">
        <div class="data-table-wrap-scroll">
          <table class="data-table">
            <thead>
              <tr>
                {#each userCols as col}
                  <th class="sortable" onclick={() => toggleUserSort(col.key)}>
                    {col.label}
                    {#if userSortCol === col.key}
                      <span class="sort-ind">{userSortDir === 'asc' ? '↑' : '↓'}</span>
                    {/if}
                  </th>
                {/each}
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {#each sortedUsers as u (u.id)}
                <tr>
                  <td>
                    <strong>{u.username}</strong>
                    {#if u.email}<div class="sub-email">{u.email}</div>{/if}
                  </td>
                  <td>{u.role}</td>
                  <td>
                    <span class="badge {u.source === 'ldap' ? 'badge-f4' : 'badge-neutral'}">{u.source}</span>
                  </td>
                  <td class="mono-cell">{fmtDate(u.last_login)}</td>
                  <td class="num">{fmtNum(u.login_count)}</td>
                  <td class="num">{fmtNum(u.jobs_run)}</td>
                  <td class="num">{fmtNum(u.exports)}</td>
                  <td class="mono-cell">{fmtDate(u.last_active)}</td>
                  <td>
                    {#if u.disabled}
                      <span class="badge badge-c">Disabled</span>
                    {:else if u.inactive}
                      <span class="badge badge-c">Inactive</span>
                    {:else}
                      <span class="badge badge-a">Active</span>
                    {/if}
                  </td>
                  <td>
                    {#if u.role !== 'super_admin'}
                      <button
                        class={u.disabled ? 'btn btn-sm' : 'btn-danger btn-sm'}
                        disabled={togglingId === u.id}
                        onclick={() => toggleUser(u)}
                      >
                        {togglingId === u.id ? '…' : u.disabled ? 'Enable' : 'Disable'}
                      </button>
                    {:else}
                      <span class="text-faint" style="font-size:12px;">protected</span>
                    {/if}
                  </td>
                </tr>
              {/each}
              {#if sortedUsers.length === 0}
                <tr><td colspan="10" class="empty">No users found.</td></tr>
              {/if}
            </tbody>
          </table>
        </div>
      </div>

      {:else if activeTab === 'actions'}
      <!-- ════ 4. ACTION BREAKDOWN ════ -->
      <div class="section-head">
        <span class="dot"></span>
        <h2>Action Breakdown</h2>
      </div>

      <div class="two-col">
        <div class="card">
          <div class="card-title">Actions by type</div>
          {#if actionChart}
            <svg viewBox="0 0 620 {actionChart.height}" class="chart" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Action breakdown chart">
              {#each actionChart.rows as r}
                <text x="0" y={r.y + actionChart.rowH / 2} dominant-baseline="middle" class="bar-label">{r.action}</text>
                <rect
                  x={actionChart.labelW}
                  y={r.y + 3}
                  width={Math.max(2, r.w)}
                  height={actionChart.rowH - 10}
                  fill="var(--accent)"
                />
                <text
                  x={actionChart.labelW + Math.max(2, r.w) + 6}
                  y={r.y + actionChart.rowH / 2}
                  dominant-baseline="middle"
                  class="bar-value"
                >{r.count}</text>
              {/each}
            </svg>
          {:else}
            <p class="empty">No action data.</p>
          {/if}
        </div>

        <div class="card">
          <div class="card-title">Top 10 users by activity</div>
          {#if data.top_users?.length}
            <table class="mini-table">
              <tbody>
                {#each data.top_users as tu, i}
                  <tr>
                    <td class="rank">{i + 1}</td>
                    <td><strong>{tu.username}</strong></td>
                    <td class="num">{fmtNum(tu.count)}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          {:else}
            <p class="empty">No activity recorded.</p>
          {/if}
        </div>
      </div>

      {:else if activeTab === 'audit'}
      <!-- ════ 5. AUDIT LOG EXPLORER ════ -->
      <div class="section-head">
        <span class="dot"></span>
        <h2>Audit Log Explorer</h2>
      </div>

      <div class="card filter-card">
        <div class="filter-grid">
          <div>
            <label class="label" for="f-user">Username</label>
            <input id="f-user" class="input" type="text" placeholder="username" bind:value={fUsername} />
          </div>
          <div>
            <label class="label" for="f-action">Action</label>
            <select id="f-action" class="select" bind:value={fAction}>
              {#each ACTION_OPTIONS as opt}
                <option value={opt.value}>{opt.label}</option>
              {/each}
            </select>
          </div>
          <div>
            <label class="label" for="f-from">Date from</label>
            <input id="f-from" class="input" type="date" bind:value={fDateFrom} />
          </div>
          <div>
            <label class="label" for="f-to">Date to</label>
            <input id="f-to" class="input" type="date" bind:value={fDateTo} />
          </div>
          <div>
            <label class="label" for="f-q">Search</label>
            <input id="f-q" class="input" type="text" placeholder="search details…" bind:value={fQuery} />
          </div>
          <div class="filter-actions">
            <button class="btn" onclick={loadAudit} disabled={auditLoading}>
              {auditLoading ? 'Loading…' : 'Apply'}
            </button>
            <button class="btn-ghost" onclick={exportAuditCsv} disabled={!auditRows.length}>
              Export CSV
            </button>
          </div>
        </div>
      </div>

      <div class="data-table-wrap" style="margin-top:14px;">
        {#if auditError}
          <div class="alert alert-danger" style="margin:14px;">Error: {auditError}</div>
        {/if}
        <div class="data-table-wrap-scroll">
          <table class="data-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>User</th>
                <th>Action</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              {#each auditRows as row (row.id)}
                <tr>
                  <td class="mono-cell">{fmtDate(row.timestamp)}</td>
                  <td><strong>{row.username ?? '—'}</strong></td>
                  <td><span class={actionBadge(row.action)}>{row.action}</span></td>
                  <td class="details-cell">{row.details ?? ''}</td>
                </tr>
              {/each}
              {#if auditRows.length === 0 && !auditLoading}
                <tr><td colspan="4" class="empty">No audit entries match the filter.</td></tr>
              {/if}
            </tbody>
          </table>
        </div>
      </div>

      {:else if activeTab === 'pulse'}
      <!-- ════ 9. PULSE (live ops) ════ -->
      <div class="section-head">
        <span class="dot"></span>
        <h2>Live pulse</h2>
        <div style="margin-left:auto;display:flex;gap:6px;">
          {#each CK_RANGES as r}
            <button class="ck-chip" class:on={ckDays === r.v} onclick={() => ckRange(r.v)}>{r.l}</button>
          {/each}
          <button class="ck-chip" onclick={loadCockpit}>Refresh</button>
        </div>
      </div>

      {#if ck}
        <div class="grid-kpi" style="margin-bottom:1.25rem;">
          <div class="kpi"><div class="kpi-label">Jobs ({ckDays}d)</div><div class="kpi-value">{ck.kpis.jobs}</div><div class="kpi-sub">{ck.kpis.completed} ok · {ck.kpis.failed} failed</div></div>
          <div class="kpi"><div class="kpi-label">Success rate</div><div class="kpi-value">{ck.kpis.success_rate}%</div></div>
          <div class="kpi"><div class="kpi-label">LLM tokens</div><div class="kpi-value">{kfmt(ck.kpis.tokens)}</div><div class="kpi-sub">{kfmt(ck.kpis.tokens_in)} in · {kfmt(ck.kpis.tokens_out)} out</div></div>
          <div class="kpi"><div class="kpi-label">LLM cost</div><div class="kpi-value">{usd(ck.kpis.cost)}</div><div class="kpi-sub">{usd(ck.kpis.cost_avg)} avg / job</div></div>
          <div class="kpi"><div class="kpi-label">Active users</div><div class="kpi-value">{ck.kpis.active_users}</div><div class="kpi-sub">of {ck.kpis.total_users} total</div></div>
          <div class="kpi"><div class="kpi-label">Failed logins</div><div class="kpi-value" style="color:{ck.kpis.failed_logins ? 'var(--danger)' : 'inherit'};">{ck.kpis.failed_logins}</div></div>
          <div class="kpi"><div class="kpi-label">Avg run time</div><div class="kpi-value">{ck.kpis.avg_runtime_s}s</div></div>
          <div class="kpi"><div class="kpi-label">Outlets</div><div class="kpi-value">{kfmt(ck.kpis.outlets)}</div></div>
        </div>

        <div class="ck-grid">
          <div class="card" style="padding:0;overflow:hidden;">
            <div class="ck-ch">Event feed <span class="ck-tag">jobs + audit</span></div>
            <div class="ck-feed">
              {#if ck.pulse.length === 0}<div class="empty" style="padding:24px;">No activity in range</div>{/if}
              {#each ck.pulse as e}
                <div class="ck-ev {e.level}">
                  <div class="ck-av {e.level}">{ckAvatar(e.level)}</div>
                  <div class="ck-et"><b>{e.title}</b><div class="ck-m">{e.meta}</div></div>
                  <span class="ck-ago">{rel(e.ts)}</span>
                </div>
              {/each}
            </div>
          </div>

          <div style="display:flex;flex-direction:column;gap:18px;">
            <div class="card" style="padding:0;overflow:hidden;">
              <div class="ck-ch">Cost &amp; tokens</div>
              <div style="padding:14px 18px;">
                <div class="ck-bars">
                  {#each ck.cost_trend as t}
                    <div class="ck-bar" title="{t.day}: {usd(t.cost)}"><i style="height:{Math.round(100 * t.cost / ckTrendMax)}%;"></i></div>
                  {/each}
                  {#if ck.cost_trend.length === 0}<div class="empty" style="width:100%;">No spend in range</div>{/if}
                </div>
                <div class="ck-split">
                  <span style="width:{Math.round(100 * ck.tokens.prompt / ckTokTotal)}%;background:var(--accent);"></span>
                  <span style="width:{Math.round(100 * ck.tokens.completion / ckTokTotal)}%;background:var(--info);"></span>
                </div>
                <div class="ck-lg"><span><span class="ck-sw" style="background:var(--accent);"></span>Prompt <b>{kfmt(ck.tokens.prompt)}</b></span><span><span class="ck-sw" style="background:var(--info);"></span>Completion <b>{kfmt(ck.tokens.completion)}</b></span></div>
              </div>
            </div>

            <div class="card" style="padding:0;overflow:hidden;">
              <div class="ck-ch">Models</div>
              <table class="ck-tbl">
                <thead><tr><th>Model</th><th class="num">Runs</th><th class="num">Tokens</th><th class="num">Cost</th></tr></thead>
                <tbody>
                  {#each ck.models as m}<tr><td class="mono-cell">{m.model}</td><td class="num">{m.runs}</td><td class="num">{kfmt(m.tokens)}</td><td class="num">{usd(m.cost)}</td></tr>{/each}
                  {#if ck.models.length === 0}<tr><td colspan="4" class="empty">No runs yet</td></tr>{/if}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div class="card" style="padding:0;overflow:hidden;margin-top:18px;">
          <div class="ck-ch">Recent jobs — who ran what</div>
          <table class="ck-tbl">
            <thead><tr><th>Job</th><th>Run by</th><th>Model</th><th class="num">Outlets</th><th class="num">Tokens</th><th class="num">Cost</th><th class="num">Duration</th><th>Rule</th><th>Status</th></tr></thead>
            <tbody>
              {#each ck.jobs as j}
                <tr>
                  <td class="mono-cell">{j.job_id}</td><td>{j.run_by}</td><td class="mono-cell">{j.model}</td>
                  <td class="num">{j.outlets ? j.outlets.toLocaleString() : '—'}</td><td class="num">{kfmt(j.tokens)}</td>
                  <td class="num">{usd(j.cost)}</td><td class="num">{j.duration}</td><td>{j.rule_version ? 'v' + j.rule_version : '—'}</td>
                  <td><span class="badge {j.status === 'completed' ? 'badge-a' : j.status === 'failed' ? 'badge-c' : 'badge-neutral'}">{j.status}</span></td>
                </tr>
              {/each}
              {#if ck.jobs.length === 0}<tr><td colspan="9" class="empty">No jobs in range</td></tr>{/if}
            </tbody>
          </table>
        </div>
      {:else}
        <p class="empty">Loading live data…</p>
      {/if}
      {/if}

    {/if}
  </div>
{/if}

<style>
  .page {
    padding: 2rem;
    width: 100%;
    margin: 0;
  }

  .page-head {
    margin-bottom: 1.75rem;
  }
  .page-head h1 {
    font-size: 1.6rem;
    font-weight: 600;
    margin: 0;
    color: var(--text);
  }
  .page-head p {
    margin: 0.35rem 0 0;
    font-size: 0.9rem;
    color: var(--text-muted);
  }

  .tab-bar {
    margin-bottom: 1.5rem;
  }

  .caption {
    margin: 10px 0 0;
    font-size: 12px;
    color: var(--text-muted);
    font-family: var(--font-mono);
  }
  .caption strong { color: var(--text); }

  /* charts */
  .chart {
    width: 100%;
    height: auto;
    display: block;
  }
  .axis-label {
    font-size: 10px;
    fill: var(--text-faint);
    font-family: var(--font-mono);
  }
  .bar-label {
    font-size: 11px;
    fill: var(--text-muted);
    font-family: var(--font-mono);
  }
  .bar-value {
    font-size: 11px;
    fill: var(--text);
    font-family: var(--font-mono);
    font-weight: 600;
  }

  .legend {
    display: flex;
    gap: 1.25rem;
    margin-bottom: 10px;
    flex-wrap: wrap;
  }
  .legend-item {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: var(--text-muted);
  }
  .legend-line {
    width: 16px;
    height: 3px;
    display: inline-block;
  }

  /* tables */
  .data-table-wrap-scroll {
    overflow-x: auto;
  }
  .sortable { white-space: nowrap; }
  .sort-ind {
    color: var(--accent);
    margin-left: 2px;
  }
  .num {
    font-family: var(--font-mono);
    text-align: right;
  }
  .mono-cell {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--text-muted);
    white-space: nowrap;
  }
  .sub-email {
    font-size: 11px;
    color: var(--text-faint);
    font-family: var(--font-mono);
  }
  .details-cell {
    color: var(--text-muted);
    font-size: 12px;
    max-width: 420px;
  }
  .empty {
    padding: 1.5rem;
    text-align: center;
    color: var(--text-faint);
    font-size: 13px;
  }

  /* layout */
  .two-col {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 14px;
  }
  .card-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--text);
    margin-bottom: 10px;
  }

  .mini-table {
    width: 100%;
    border-collapse: collapse;
  }
  .mini-table th {
    text-align: left;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: var(--text-muted);
    font-weight: 600;
    padding: 6px 8px;
    border-bottom: 1px solid var(--border);
  }
  .mini-table td {
    padding: 7px 8px;
    font-size: 13px;
    color: var(--text);
    border-bottom: 1px solid var(--border);
  }
  .mini-table tr:last-child td { border-bottom: none; }
  .mini-table .rank {
    color: var(--text-faint);
    font-family: var(--font-mono);
    width: 28px;
  }

  /* filter card */
  .filter-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 12px;
    align-items: end;
  }
  .filter-actions {
    display: flex;
    gap: 8px;
  }

  /* auth */
  .auth-counts {
    display: flex;
    gap: 1.5rem;
    font-size: 13px;
    color: var(--text-muted);
    margin-bottom: 10px;
  }
  .auth-counts strong { color: var(--text); }
  .swatch {
    width: 11px;
    height: 11px;
    display: inline-block;
    margin-right: 5px;
    vertical-align: middle;
  }
  .ratio-bar {
    display: flex;
    height: 14px;
    border: 1px solid var(--border);
    overflow: hidden;
    background: var(--surface-2);
  }
  .ratio-seg { height: 100%; }
  .failed-count {
    font-size: 38px;
    font-weight: 700;
    line-height: 1.1;
    letter-spacing: -0.02em;
  }

  /* ── Pulse (live cockpit) ── */
  .ck-chip { padding: 5px 12px; border-radius: var(--r-pill); border: 1px solid var(--border); background: var(--surface); font: inherit; font-size: 12px; font-weight: 500; color: var(--text-muted); cursor: pointer; }
  .ck-chip.on { background: var(--text); color: var(--surface); border-color: var(--text); }
  .ck-grid { display: grid; grid-template-columns: 1.4fr 1fr; gap: 18px; }
  .ck-ch { display: flex; align-items: center; gap: 8px; padding: 13px 18px; border-bottom: 1px solid var(--border-soft); font-weight: 600; font-size: 14px; }
  .ck-tag { margin-left: auto; font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: .04em; padding: 3px 8px; border-radius: var(--r-pill); background: var(--success-soft); color: var(--success); }
  .ck-feed { max-height: 440px; overflow-y: auto; }
  .ck-ev { display: flex; gap: 11px; padding: 11px 18px; border-bottom: 1px solid var(--border-soft); border-left: 3px solid transparent; }
  .ck-ev.ok { border-left-color: var(--success); } .ck-ev.warn { border-left-color: var(--warning); } .ck-ev.error { border-left-color: var(--danger); } .ck-ev.info { border-left-color: var(--info); }
  .ck-av { flex-shrink: 0; width: 28px; height: 28px; border-radius: var(--r-pill); display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 700; background: var(--surface-2); color: var(--text-muted); }
  .ck-av.ok { background: var(--success-soft); color: var(--success); } .ck-av.warn { background: var(--warning-soft); color: var(--warning); } .ck-av.error { background: var(--danger-soft); color: var(--danger); } .ck-av.info { background: var(--info-soft); color: var(--info); }
  .ck-et { flex: 1; min-width: 0; }
  .ck-et b { font-size: 12.5px; font-weight: 600; }
  .ck-m { font-size: 11.5px; color: var(--text-muted); margin-top: 1px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .ck-ago { font-size: 11px; color: var(--text-faint); white-space: nowrap; flex-shrink: 0; }
  .ck-bars { display: flex; align-items: flex-end; gap: 5px; height: 80px; margin: 4px 0 10px; }
  .ck-bar { flex: 1; background: var(--accent-soft); border-radius: 4px 4px 0 0; position: relative; min-height: 2px; }
  .ck-bar i { position: absolute; bottom: 0; left: 0; right: 0; background: var(--accent); border-radius: 4px 4px 0 0; }
  .ck-split { display: flex; height: 9px; border-radius: var(--r-pill); overflow: hidden; margin: 8px 0; background: var(--surface-2); }
  .ck-lg { display: flex; gap: 14px; font-size: 11px; color: var(--text-muted); flex-wrap: wrap; }
  .ck-lg b { color: var(--text); }
  .ck-sw { display: inline-block; width: 9px; height: 9px; border-radius: 3px; margin-right: 5px; vertical-align: -1px; }
  .ck-tbl { width: 100%; border-collapse: collapse; font-size: 12.5px; }
  .ck-tbl th { text-align: left; color: var(--text-muted); font-weight: 500; font-size: 11px; padding: 9px 12px; border-bottom: 1px solid var(--border-soft); text-transform: uppercase; letter-spacing: .03em; }
  .ck-tbl td { padding: 10px 12px; border-bottom: 1px solid var(--border-soft); }
  .ck-tbl tr:last-child td { border-bottom: none; }
  .ck-tbl tbody tr:hover td { background: var(--surface-2); }
  .ck-tbl .num { text-align: right; font-variant-numeric: tabular-nums; }
  @media (max-width: 1100px) { .ck-grid { grid-template-columns: 1fr; } }
</style>
