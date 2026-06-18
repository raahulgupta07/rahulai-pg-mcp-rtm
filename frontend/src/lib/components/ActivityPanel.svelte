<script lang="ts">
  import { getActivity, markActivitySeen, getVersion, type ActivityEvent, type VersionResponse } from '$lib/api';

  let { open = false, onclose = () => {}, onseen = () => {} } = $props<{
    open?: boolean; onclose?: () => void; onseen?: (n: number) => void;
  }>();

  let tab = $state<'activity' | 'whatsnew'>('activity');
  let filter = $state<'all' | 'unread' | 'jobs' | 'rules' | 'alerts'>('all');
  let events = $state<ActivityEvent[]>([]);
  let seenAt = $state('');
  let ver = $state<VersionResponse | null>(null);
  let loading = $state(false);
  let loaded = false;

  const FILTERS = [
    { key: 'all', label: 'All' }, { key: 'unread', label: 'Unread' },
    { key: 'jobs', label: 'Jobs' }, { key: 'rules', label: 'Rules' },
    { key: 'alerts', label: 'Alerts' },
  ] as const;

  function isUnread(e: ActivityEvent) { return (e.ts || '') > seenAt; }
  const unreadCount = $derived(events.filter(isUnread).length);
  const counts = $derived({
    ok: events.filter(e => e.level === 'ok').length,
    warn: events.filter(e => e.level === 'warn').length,
    error: events.filter(e => e.level === 'error').length,
  });
  const shown = $derived(events.filter(e =>
    filter === 'all' ? true : filter === 'unread' ? isUnread(e) : e.type === filter
  ));

  async function load() {
    loading = true;
    try {
      const [a, v] = await Promise.all([getActivity(), getVersion()]);
      events = a.events; seenAt = a.seen_at; ver = v;
    } catch { /* ignore */ }
    loading = false;
  }

  $effect(() => {
    if (open && !loaded) { loaded = true; load(); }
    if (!open) loaded = false;
  });

  async function markAll() {
    try {
      const r = await markActivitySeen();
      seenAt = r.seen_at;
      onseen(0);
    } catch { /* ignore */ }
  }

  function ago(s: string): string {
    if (!s) return '';
    const mins = Math.floor((Date.now() - new Date(s).getTime()) / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const h = Math.floor(mins / 60);
    if (h < 24) return `${h}h ago`;
    return `${Math.floor(h / 24)}d ago`;
  }

  function avatar(level: string) {
    return level === 'error' ? '✕' : level === 'warn' ? '!' : 'OK';
  }
</script>

{#if open}
  <div class="ap-backdrop" onclick={onclose} role="presentation"></div>
  <div class="ap-panel" role="dialog" aria-label="Activity and updates">
    <div class="ap-tabs">
      <button class="ap-tab" class:on={tab === 'activity'} onclick={() => tab = 'activity'}>
        Activity {#if unreadCount}<span class="ap-count">{unreadCount}</span>{/if}
      </button>
      <button class="ap-tab" class:on={tab === 'whatsnew'} onclick={() => tab = 'whatsnew'}>What's new</button>
      <button class="ap-x" onclick={onclose} aria-label="Close">
        <span class="material-symbols-outlined">close</span>
      </button>
    </div>

    {#if tab === 'activity'}
      <div class="ap-summary">
        <span class="ap-live"><span class="ap-led"></span>live · {unreadCount} unread</span>
        <span class="ap-stat ok">{counts.ok} <span class="material-symbols-outlined">check</span></span>
        <span class="ap-stat warn">{counts.warn} <span class="material-symbols-outlined">warning</span></span>
        <span class="ap-stat err">{counts.error} <span class="material-symbols-outlined">close</span></span>
        <span class="ap-total">{events.length} total</span>
      </div>

      <div class="ap-filters">
        {#each FILTERS as f}
          <button class="ap-chip" class:on={filter === f.key} onclick={() => filter = f.key}>{f.label}</button>
        {/each}
        <button class="ap-markall" onclick={markAll}>Mark all read</button>
      </div>

      <div class="ap-list">
        {#if loading}
          <div class="ap-empty">Loading…</div>
        {:else if shown.length === 0}
          <div class="ap-empty">Nothing here yet</div>
        {:else}
          {#each shown as e (e.id)}
            <div class="ap-row lvl-{e.level}">
              <div class="ap-av lvl-{e.level}">{avatar(e.level)}</div>
              <div class="ap-body">
                <div class="ap-title">{e.title}</div>
                <div class="ap-sub">{e.subtitle}</div>
              </div>
              <div class="ap-meta">
                <span class="ap-ago">{ago(e.ts)}</span>
                {#if isUnread(e)}<span class="ap-dot"></span>{/if}
              </div>
            </div>
          {/each}
        {/if}
      </div>
    {:else}
      <div class="ap-whatsnew">
        {#if ver}
          <div class="ap-vhead">
            <span class="ap-ver">v{ver.version}</span>
            <span class="ap-badge" class:utd={ver.up_to_date}>{ver.up_to_date ? 'Up to date' : `Latest v${ver.latest}`}</span>
          </div>
          {#each ver.releases as r}
            <div class="ap-rel">
              <div class="ap-relhead"><span class="ap-relver">v{r.version}</span> {r.title}<span class="ap-reldate">{r.date}</span></div>
              <div class="ap-relbody">{r.body}</div>
            </div>
          {/each}
        {:else}
          <div class="ap-empty">Loading…</div>
        {/if}
      </div>
    {/if}
  </div>
{/if}

<style>
  .ap-backdrop { position: fixed; inset: 0; z-index: 90; background: transparent; }
  .ap-panel {
    position: fixed; top: 64px; right: 20px; z-index: 91;
    width: 400px; max-width: calc(100vw - 32px); max-height: 78vh;
    display: flex; flex-direction: column;
    background: var(--surface); border: 1px solid var(--border-soft);
    border-radius: var(--r-xl); box-shadow: var(--shadow-xl); overflow: hidden;
  }
  .ap-tabs { display: flex; align-items: center; gap: 6px; padding: 10px 10px 0; border-bottom: 1px solid var(--border-soft); }
  .ap-tab {
    background: transparent; border: none; padding: 10px 14px; font: inherit; font-size: 13px; font-weight: 600;
    color: var(--text-muted); border-radius: var(--r-md) var(--r-md) 0 0; display: flex; align-items: center; gap: 7px;
  }
  .ap-tab.on { color: var(--text); background: var(--surface-2); }
  .ap-count { background: var(--accent); color: #fff; font-size: 11px; padding: 1px 7px; border-radius: var(--r-pill); }
  .ap-x { margin-left: auto; background: transparent; border: none; color: var(--text-faint); display: flex; padding: 6px; }
  .ap-x:hover { color: var(--text); }

  .ap-summary { display: flex; align-items: center; gap: 12px; padding: 12px 16px; font-size: 12px; color: var(--text-muted); border-bottom: 1px solid var(--border-soft); }
  .ap-live { display: flex; align-items: center; gap: 6px; font-weight: 500; }
  .ap-led { width: 7px; height: 7px; border-radius: var(--r-pill); background: var(--success); }
  .ap-stat { display: flex; align-items: center; gap: 3px; }
  .ap-stat .material-symbols-outlined { font-size: 14px; }
  .ap-stat.ok { color: var(--success); } .ap-stat.warn { color: var(--warning); } .ap-stat.err { color: var(--danger); }
  .ap-total { margin-left: auto; color: var(--text-faint); }

  .ap-filters { display: flex; flex-wrap: wrap; gap: 7px; padding: 12px 16px; align-items: center; }
  .ap-chip { background: var(--surface); border: 1px solid var(--border); color: var(--text-muted); font: inherit; font-size: 12px; font-weight: 500; padding: 5px 12px; border-radius: var(--r-pill); }
  .ap-chip.on { background: var(--text); color: var(--surface); border-color: var(--text); }
  .ap-markall { margin-left: auto; background: transparent; border: none; color: var(--accent); font: inherit; font-size: 12px; font-weight: 600; }
  .ap-markall:hover { text-decoration: underline; }

  .ap-list { overflow-y: auto; }
  .ap-row { display: flex; gap: 11px; padding: 13px 16px; border-bottom: 1px solid var(--border-soft); border-left: 3px solid transparent; }
  .ap-row.lvl-ok { border-left-color: var(--success); }
  .ap-row.lvl-warn { border-left-color: var(--warning); }
  .ap-row.lvl-error { border-left-color: var(--danger); }
  .ap-row:hover { background: var(--surface-2); }
  .ap-av { flex-shrink: 0; width: 30px; height: 30px; border-radius: var(--r-pill); display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 600; background: var(--surface-2); color: var(--text-muted); }
  .ap-av.lvl-ok { background: var(--success-soft); color: var(--success); }
  .ap-av.lvl-warn { background: var(--warning-soft); color: var(--warning); }
  .ap-av.lvl-error { background: var(--danger-soft); color: var(--danger); }
  .ap-body { flex: 1; min-width: 0; }
  .ap-title { font-size: 13px; font-weight: 600; color: var(--text); }
  .ap-sub { font-size: 12px; color: var(--text-muted); margin-top: 2px; }
  .ap-meta { flex-shrink: 0; display: flex; flex-direction: column; align-items: flex-end; gap: 6px; }
  .ap-ago { font-size: 11px; color: var(--text-faint); white-space: nowrap; }
  .ap-dot { width: 7px; height: 7px; border-radius: var(--r-pill); background: var(--accent); }
  .ap-empty { padding: 36px 16px; text-align: center; color: var(--text-faint); font-size: 13px; }

  .ap-whatsnew { overflow-y: auto; padding: 16px; }
  .ap-vhead { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
  .ap-ver { font-size: 22px; font-weight: 700; color: var(--accent); }
  .ap-badge { font-size: 11px; font-weight: 600; padding: 3px 10px; border-radius: var(--r-pill); background: var(--surface-2); color: var(--text-muted); }
  .ap-badge.utd { background: var(--success-soft); color: var(--success); }
  .ap-rel { padding: 12px 0; border-top: 1px solid var(--border-soft); }
  .ap-relhead { font-size: 13px; font-weight: 600; color: var(--text); display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
  .ap-relver { color: var(--accent); }
  .ap-reldate { margin-left: auto; font-size: 11px; font-weight: 400; color: var(--text-faint); }
  .ap-relbody { font-size: 12px; color: var(--text-muted); line-height: 1.6; margin-top: 5px; }
</style>
