<script lang="ts">
  import { onMount } from 'svelte';
  import { getCockpit } from '$lib/api';
  import { auth } from '$lib/stores/auth.svelte';
  import { goto } from '$app/navigation';

  let days = $state(7);
  let d = $state<any>(null);
  let loading = $state(true);

  const RANGES = [{ v: 1, l: '24h' }, { v: 7, l: '7 days' }, { v: 30, l: '30 days' }];

  async function load() {
    loading = true;
    try { d = await getCockpit(days); } catch { /* ignore */ }
    loading = false;
  }

  onMount(() => {
    if (!auth.isSuperAdmin) { goto('/'); return; }
    load();
    const iv = setInterval(load, 30000);
    return () => clearInterval(iv);
  });

  function setRange(v: number) { days = v; load(); }

  function k(n: number): string {
    if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
    if (n >= 1e3) return (n / 1e3).toFixed(1) + 'k';
    return String(n ?? 0);
  }
  function usd(n: number): string { return '$' + (n ?? 0).toFixed(2); }
  function ago(s: string): string {
    if (!s) return '';
    const mins = Math.floor((Date.now() - new Date(s).getTime()) / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const h = Math.floor(mins / 60);
    if (h < 24) return `${h}h ago`;
    return `${Math.floor(h / 24)}d ago`;
  }
  function avatar(l: string) { return l === 'error' ? '✕' : l === 'warn' ? '!' : l === 'info' ? '→' : 'OK'; }

  const trendMax = $derived(Math.max(1, ...((d?.cost_trend ?? []).map((t: any) => t.cost))));
  const tokTotal = $derived((d?.tokens?.prompt ?? 0) + (d?.tokens?.completion ?? 0) || 1);
  const failMax = $derived(Math.max(1, ...Object.values(d?.auth?.failed_by_reason ?? { x: 1 }) as number[]));
</script>

<div class="ck-head">
  <h1>Ops Cockpit</h1>
  <span class="live"><span class="led"></span>live</span>
  <div class="rng">
    {#each RANGES as r}
      <button class="chip" class:on={days === r.v} onclick={() => setRange(r.v)}>{r.l}</button>
    {/each}
    <button class="chip" onclick={load}>Refresh</button>
  </div>
</div>
<p class="ck-sub">Every job, token, dollar, model, login and failure — one screen.</p>

{#if loading && !d}
  <div class="ck-empty">Loading cockpit…</div>
{:else if d}
  <!-- KPI band -->
  <div class="kpis">
    <div class="kc"><div class="l">Jobs ({days}d)</div><div class="v">{d.kpis.jobs}</div><div class="dd">{d.kpis.completed} ok · {d.kpis.failed} failed</div></div>
    <div class="kc"><div class="l">Success rate</div><div class="v">{d.kpis.success_rate}%</div></div>
    <div class="kc"><div class="l">LLM tokens</div><div class="v">{k(d.kpis.tokens)}</div><div class="dd">{k(d.kpis.tokens_in)} in · {k(d.kpis.tokens_out)} out</div></div>
    <div class="kc"><div class="l">LLM cost</div><div class="v">{usd(d.kpis.cost)}</div><div class="dd">{usd(d.kpis.cost_avg)} avg / job</div></div>
    <div class="kc"><div class="l">Active users</div><div class="v">{d.kpis.active_users}</div><div class="dd">of {d.kpis.total_users} total</div></div>
    <div class="kc"><div class="l">Failed logins</div><div class="v" class:err={d.kpis.failed_logins > 0}>{d.kpis.failed_logins}</div></div>
    <div class="kc"><div class="l">Avg run time</div><div class="v">{d.kpis.avg_runtime_s}s</div></div>
    <div class="kc"><div class="l">Outlets classified</div><div class="v">{k(d.kpis.outlets)}</div></div>
  </div>

  <div class="grid">
    <!-- Pulse feed -->
    <div class="ck-card">
      <div class="ch">Live pulse <span class="tag">jobs + audit</span></div>
      <div class="feed">
        {#if d.pulse.length === 0}<div class="ck-empty">No activity in range</div>{/if}
        {#each d.pulse as e}
          <div class="ev {e.level}">
            <div class="av {e.level}">{avatar(e.level)}</div>
            <div class="et"><b>{e.title}</b><div class="m">{e.meta}</div></div>
            <span class="ago">{ago(e.ts)}</span>
          </div>
        {/each}
      </div>
    </div>

    <div class="col">
      <!-- Cost & tokens -->
      <div class="ck-card">
        <div class="ch">Cost &amp; tokens</div>
        <div class="cb">
          <div class="bars">
            {#each d.cost_trend as t}
              <div class="bar" title="{t.day}: {usd(t.cost)}"><i style="height:{Math.round(100 * t.cost / trendMax)}%"></i></div>
            {/each}
            {#if d.cost_trend.length === 0}<div class="ck-empty" style="width:100%">No spend in range</div>{/if}
          </div>
          <div class="lbl">Prompt vs completion tokens</div>
          <div class="split">
            <span style="width:{Math.round(100 * d.tokens.prompt / tokTotal)}%;background:var(--accent)"></span>
            <span style="width:{Math.round(100 * d.tokens.completion / tokTotal)}%;background:var(--info)"></span>
          </div>
          <div class="lg"><span><span class="sw" style="background:var(--accent)"></span>Prompt <b>{k(d.tokens.prompt)}</b></span><span><span class="sw" style="background:var(--info)"></span>Completion <b>{k(d.tokens.completion)}</b></span></div>
        </div>
      </div>

      <!-- Models -->
      <div class="ck-card">
        <div class="ch">Models</div>
        <div class="cb tbl">
          <table>
            <thead><tr><th>Model</th><th class="num">Runs</th><th class="num">Tokens</th><th class="num">Cost</th></tr></thead>
            <tbody>
              {#each d.models as m}
                <tr><td class="mono">{m.model}</td><td class="num">{m.runs}</td><td class="num">{k(m.tokens)}</td><td class="num">{usd(m.cost)}</td></tr>
              {/each}
              {#if d.models.length === 0}<tr><td colspan="4" class="ck-empty">No runs yet</td></tr>{/if}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>

  <!-- Recent jobs -->
  <div class="ck-card wide">
    <div class="ch">Recent jobs — who ran what</div>
    <div class="cb tbl">
      <table>
        <thead><tr><th>Job</th><th>Run by</th><th>Model</th><th class="num">Outlets</th><th class="num">Tokens</th><th class="num">Cost</th><th class="num">Duration</th><th>Rule</th><th>Status</th></tr></thead>
        <tbody>
          {#each d.jobs as j}
            <tr>
              <td class="mono">{j.job_id}</td><td>{j.run_by}</td><td class="mono">{j.model}</td>
              <td class="num">{j.outlets ? j.outlets.toLocaleString() : '—'}</td><td class="num">{k(j.tokens)}</td>
              <td class="num">{usd(j.cost)}</td><td class="num">{j.duration}</td><td>{j.rule_version ? 'v' + j.rule_version : '—'}</td>
              <td><span class="pill p-{j.status === 'completed' ? 'ok' : j.status === 'failed' ? 'err' : 'run'}">{j.status}</span></td>
            </tr>
          {/each}
          {#if d.jobs.length === 0}<tr><td colspan="9" class="ck-empty">No jobs in range</td></tr>{/if}
        </tbody>
      </table>
    </div>
  </div>

  <div class="grid3">
    <!-- Per-user -->
    <div class="ck-card">
      <div class="ch">Per-user activity</div>
      <div class="cb tbl">
        <table>
          <thead><tr><th>User</th><th class="num">Jobs</th><th class="num">Tokens</th><th class="num">Cost</th><th>Last active</th></tr></thead>
          <tbody>
            {#each d.users as u}
              <tr><td>{u.username} <span class="role">{u.role}</span></td><td class="num">{u.jobs}</td><td class="num">{k(u.tokens)}</td><td class="num">{usd(u.cost)}</td><td>{u.last_active ? ago(u.last_active) : '—'}</td></tr>
            {/each}
            {#if d.users.length === 0}<tr><td colspan="5" class="ck-empty">No runs in range</td></tr>{/if}
          </tbody>
        </table>
      </div>
    </div>

    <!-- Auth & security -->
    <div class="ck-card">
      <div class="ch">Auth &amp; security</div>
      <div class="cb">
        <div class="sr"><span class="k">Logins ({days}d)</span><span><b>{d.auth.logins_success}</b> success · <b class="err">{d.auth.logins_failed}</b> failed</span></div>
        <div class="sr"><span class="k">Local vs LDAP users</span><span>{d.auth.local_users} local · {d.auth.ldap_users} LDAP</span></div>
        <div class="lbl" style="margin-top:14px">Failed logins by reason</div>
        {#each Object.entries(d.auth.failed_by_reason) as [reason, count]}
          <div class="sr"><span class="k">{reason.replace('_', ' ')}</span><div class="mr"><div class="mini"><i style="width:{Math.round(100 * (count as number) / failMax)}%;background:var(--{reason === 'bad_password' ? 'warning' : 'danger'})"></i></div><b>{count}</b></div></div>
        {/each}
      </div>
    </div>
  </div>
{/if}

<style>
  .ck-head { display: flex; align-items: center; gap: 14px; margin-bottom: 4px; }
  .ck-head h1 { font-size: 24px; font-weight: 600; letter-spacing: -.01em; }
  .live { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: var(--success); font-weight: 500; background: var(--success-soft); padding: 4px 10px; border-radius: var(--r-pill); }
  .led { width: 7px; height: 7px; border-radius: var(--r-pill); background: var(--success); animation: pulse 1.6s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
  .ck-sub { color: var(--text-muted); font-size: 13px; margin-bottom: 18px; }
  .rng { margin-left: auto; display: flex; gap: 6px; }
  .chip { padding: 6px 13px; border-radius: var(--r-pill); border: 1px solid var(--border); background: var(--surface); font: inherit; font-size: 12px; font-weight: 500; color: var(--text-muted); }
  .chip.on { background: var(--text); color: var(--surface); border-color: var(--text); }

  .kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 13px; margin-bottom: 18px; }
  .kc { background: var(--surface); border: 1px solid var(--border-soft); border-radius: var(--r-lg); box-shadow: var(--shadow-sm); padding: 15px 16px; }
  .kc .l { font-size: 11px; text-transform: uppercase; letter-spacing: .05em; color: var(--text-faint); font-weight: 600; margin-bottom: 6px; }
  .kc .v { font-size: 23px; font-weight: 600; letter-spacing: -.02em; }
  .kc .v.err { color: var(--danger); }
  .kc .dd { font-size: 11px; margin-top: 4px; color: var(--text-muted); }

  .grid { display: grid; grid-template-columns: 1.4fr 1fr; gap: 18px; margin-bottom: 18px; }
  .grid3 { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; margin-bottom: 18px; }
  .col { display: flex; flex-direction: column; gap: 18px; }
  .ck-card { background: var(--surface); border: 1px solid var(--border-soft); border-radius: var(--r-lg); box-shadow: var(--shadow-sm); overflow: hidden; }
  .ch { display: flex; align-items: center; gap: 8px; padding: 14px 18px; border-bottom: 1px solid var(--border-soft); font-weight: 600; font-size: 14px; }
  .ch .tag { margin-left: auto; font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: .04em; padding: 3px 8px; border-radius: var(--r-pill); background: var(--success-soft); color: var(--success); }
  .cb { padding: 14px 18px; }
  .cb.tbl { padding: 4px 8px; }
  .ck-empty { padding: 30px 16px; text-align: center; color: var(--text-faint); font-size: 13px; }

  .feed { max-height: 460px; overflow-y: auto; }
  .ev { display: flex; gap: 11px; padding: 11px 18px; border-bottom: 1px solid var(--border-soft); border-left: 3px solid transparent; }
  .ev.ok { border-left-color: var(--success); } .ev.warn { border-left-color: var(--warning); } .ev.error { border-left-color: var(--danger); } .ev.info { border-left-color: var(--info); }
  .av { flex-shrink: 0; width: 28px; height: 28px; border-radius: var(--r-pill); display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 700; background: var(--surface-2); color: var(--text-muted); }
  .av.ok { background: var(--success-soft); color: var(--success); } .av.warn { background: var(--warning-soft); color: var(--warning); } .av.error { background: var(--danger-soft); color: var(--danger); } .av.info { background: var(--info-soft); color: var(--info); }
  .et { flex: 1; min-width: 0; }
  .et b { font-size: 12.5px; font-weight: 600; }
  .et .m { font-size: 11.5px; color: var(--text-muted); margin-top: 1px; overflow: hidden; text-overflow: ellipsis; }
  .ago { font-size: 11px; color: var(--text-faint); white-space: nowrap; flex-shrink: 0; }

  .bars { display: flex; align-items: flex-end; gap: 5px; height: 88px; margin: 4px 0 10px; }
  .bar { flex: 1; background: var(--accent-soft); border-radius: 4px 4px 0 0; position: relative; min-height: 2px; }
  .bar i { position: absolute; bottom: 0; left: 0; right: 0; background: var(--accent); border-radius: 4px 4px 0 0; }
  .lbl { font-size: 11px; color: var(--text-muted); margin-top: 6px; font-weight: 500; }
  .split { display: flex; height: 9px; border-radius: var(--r-pill); overflow: hidden; margin: 8px 0; background: var(--surface-2); }
  .lg { display: flex; gap: 14px; font-size: 11px; color: var(--text-muted); flex-wrap: wrap; }
  .lg b { color: var(--text); }
  .sw { display: inline-block; width: 9px; height: 9px; border-radius: 3px; margin-right: 5px; vertical-align: -1px; }

  table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
  th { text-align: left; color: var(--text-muted); font-weight: 500; font-size: 11px; padding: 8px 10px; border-bottom: 1px solid var(--border-soft); text-transform: uppercase; letter-spacing: .03em; }
  td { padding: 10px 10px; border-bottom: 1px solid var(--border-soft); }
  tr:last-child td { border-bottom: none; }
  tbody tr:hover td { background: var(--surface-2); }
  .num { text-align: right; font-variant-numeric: tabular-nums; }
  .mono { font-family: var(--font-mono); font-size: 11.5px; }
  .pill { display: inline-block; padding: 2px 9px; border-radius: var(--r-pill); font-size: 11px; font-weight: 600; }
  .p-ok { background: var(--success-soft); color: var(--success); } .p-err { background: var(--danger-soft); color: var(--danger); } .p-run { background: var(--info-soft); color: var(--info); }
  .role { font-size: 10px; color: var(--text-muted); background: var(--surface-2); padding: 1px 7px; border-radius: var(--r-pill); }

  .sr { display: flex; justify-content: space-between; align-items: center; padding: 9px 0; border-bottom: 1px solid var(--border-soft); font-size: 12.5px; }
  .sr:last-child { border: none; }
  .sr .k { color: var(--text-muted); text-transform: capitalize; }
  .sr .err { color: var(--danger); }
  .mr { display: flex; gap: 8px; align-items: center; }
  .mini { width: 110px; height: 8px; background: var(--surface-2); border-radius: var(--r-pill); overflow: hidden; }
  .mini i { display: block; height: 100%; border-radius: var(--r-pill); }

  @media (max-width: 1100px) {
    .kpis { grid-template-columns: repeat(2, 1fr); }
    .grid, .grid3 { grid-template-columns: 1fr; }
  }
</style>
