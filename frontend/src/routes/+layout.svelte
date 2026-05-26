<script lang="ts">
  import '../app.css';
  import { onMount } from 'svelte';
  import { auth } from '$lib/stores/auth.svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { appearance, initAppearance, loadServerPrefs, modeLabel } from '$lib/theme';
  import Appearance from '$lib/components/Appearance.svelte';
  import ChangePassword from '$lib/components/ChangePassword.svelte';

  let { children } = $props();

  let apOpen = $state(false);
  let pwOpen = $state(false);

  const currentPath = $derived($page.url.pathname);
  const isLoginRoute = $derived(currentPath === '/login');

  interface NavItem { label: string; href: string; icon: string; perm?: string; superOnly?: boolean; }

  const ALL_TABS: NavItem[] = [
    { label: 'Classify', href: '/',         icon: 'science' },
    { label: 'History',  href: '/history',  icon: 'history' },
    { label: 'RTM Data', href: '/rtm',      icon: 'table_chart' },
    { label: 'Compare',  href: '/compare',  icon: 'compare_arrows' },
    { label: 'Coverage', href: '/coverage', icon: 'map' },
    { label: 'Docs',     href: '/docs',     icon: 'menu_book' },
    { label: 'Rules',     href: '/rules',     icon: 'tune',       perm: 'rules' },
    { label: 'Analytics', href: '/analytics', icon: 'monitoring', perm: 'analytics' },
    { label: 'Settings',  href: '/users',     icon: 'settings',   superOnly: true },
  ];

  const tabs = $derived(ALL_TABS.filter(t =>
    t.superOnly ? auth.isSuperAdmin : (t.perm ? auth.hasPerm(t.perm) : true)
  ));
  // Mobile bottom nav — keep to 5 most-used
  const mobileTabs = $derived(tabs.slice(0, 5));

  function isActive(href: string): boolean {
    if (href === '/') return currentPath === '/';
    return currentPath.startsWith(href);
  }

  let userInitial = $derived(
    auth.user?.display_name?.charAt(0)?.toUpperCase() ||
    auth.user?.username?.charAt(0)?.toUpperCase() || '?'
  );

  // ── Health status ──
  let health = $state({ status: 'ok', pipeline: 'idle', jobs: 0, last_run: null as string | null, model: '' });

  function pollHealth() {
    fetch('/api/health').then(r => r.json()).then(d => health = d).catch(() => {});
  }

  function timeAgo(s: string | null): string {
    if (!s) return '—';
    const mins = Math.floor((Date.now() - new Date(s).getTime()) / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  }

  onMount(() => {
    initAppearance();
    pollHealth();
    const iv = setInterval(pollHealth, 30000);
    return () => clearInterval(iv);
  });

  $effect(() => {
    if (!auth.isAuthenticated && currentPath !== '/login') goto('/login');
  });

  // Pull per-user appearance once the user is signed in
  let prefsLoaded = false;
  $effect(() => {
    if (auth.isAuthenticated && !prefsLoaded) {
      prefsLoaded = true;
      loadServerPrefs();
    }
  });
</script>

{#if isLoginRoute || !auth.isAuthenticated}
  {@render children()}
{:else}
<div class="app-shell">
  <!-- ── Desktop Sidebar ── -->
  <aside class="sidebar">
    <div class="sidebar-brand">
      <span class="brand-mark">RTM</span>
      <span class="brand-text">Agent</span>
    </div>

    <div class="sidebar-div"></div>

    <nav class="sidebar-nav">
      {#each tabs as tab}
        <a href={tab.href} class="nav-item" class:active={isActive(tab.href)}>
          <span class="material-symbols-outlined nav-ico">{tab.icon}</span>
          <span>{tab.label}</span>
        </a>
      {/each}
    </nav>

    <div class="sidebar-foot">
      <!-- System status -->
      <div class="sys-status">
        <div class="sys-row">
          <span class="dot" class:ok={health.status === 'ok'} class:bad={health.status !== 'ok'}></span>
          <span class="sys-label">{health.status === 'ok' ? 'System OK' : 'System Error'}</span>
        </div>
        <div class="sys-meta">
          <span>{health.jobs} jobs</span>
          <span>·</span>
          <span>last {timeAgo(health.last_run)}</span>
        </div>
      </div>

      <!-- User card -->
      <div class="user-card">
        <div class="avatar">{userInitial}</div>
        <div class="user-info">
          <div class="user-name">{auth.user?.display_name || auth.user?.username}</div>
          <div class="user-role">{auth.user?.role}</div>
        </div>
        <button class="icon-btn" onclick={() => pwOpen = true} title="Change password" aria-label="Change password">
          <span class="material-symbols-outlined">key</span>
        </button>
        <button class="icon-btn" onclick={() => auth.logout()} title="Sign out" aria-label="Sign out">
          <span class="material-symbols-outlined">logout</span>
        </button>
      </div>

      <!-- Appearance -->
      <button class="theme-toggle" onclick={() => apOpen = true} title="Appearance settings">
        <span class="material-symbols-outlined">palette</span>
        <span class="tt-label">Appearance</span>
        <span class="tt-value">{modeLabel($appearance.mode)}</span>
      </button>
    </div>
  </aside>

  <!-- ── Main column ── -->
  <div class="app-main">
    <!-- Mobile header -->
    <header class="mobile-header">
      <div class="sidebar-brand">
        <span class="brand-mark">RTM</span>
        <span class="brand-text">Agent</span>
      </div>
      <div class="mob-actions">
        <button class="icon-btn" onclick={() => apOpen = true} aria-label="Appearance">
          <span class="material-symbols-outlined">palette</span>
        </button>
        <button class="icon-btn" onclick={() => pwOpen = true} aria-label="Change password">
          <span class="material-symbols-outlined">key</span>
        </button>
        <button class="icon-btn" onclick={() => auth.logout()} aria-label="Sign out">
          <span class="material-symbols-outlined">logout</span>
        </button>
      </div>
    </header>

    <main class="page-content">
      {@render children()}
    </main>

    <!-- Mobile bottom nav -->
    <nav class="nav-bottom">
      {#each mobileTabs as tab}
        <a href={tab.href} class="nav-bottom-item" class:active={isActive(tab.href)}>
          <span class="material-symbols-outlined">{tab.icon}</span>
          <span>{tab.label}</span>
        </a>
      {/each}
    </nav>
  </div>
</div>

<Appearance open={apOpen} onclose={() => apOpen = false} />
<ChangePassword open={pwOpen} onclose={() => pwOpen = false} />
{/if}

<style>
  .app-shell {
    display: flex;
    min-height: 100vh;
    min-height: 100dvh;
    background: var(--bg);
    color: var(--text);
  }

  .app-main {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
  }

  .page-content {
    flex: 1;
    padding: 16px;
    padding-bottom: calc(64px + 16px + env(safe-area-inset-bottom, 0px));
    animation: fadeIn 0.2s ease-out;
  }

  /* ── Brand ── */
  .sidebar-brand {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .brand-mark {
    background: var(--accent);
    color: #fff;
    font-weight: 700;
    font-size: 14px;
    letter-spacing: 0.02em;
    padding: 5px 9px;
    border-radius: var(--r-sm);
  }
  .brand-text {
    font-weight: 600;
    font-size: 15px;
    color: var(--text);
    white-space: nowrap;
  }

  /* ── Sidebar (desktop only) ── */
  .sidebar { display: none; }

  .sidebar-div { height: 1px; background: var(--border); margin: 0 14px; }

  /* ── Mobile header ── */
  .mobile-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    background: var(--sidebar-bg);
    border-bottom: 1px solid var(--border);
    position: sticky;
    top: 0;
    z-index: 50;
  }
  .mob-actions { display: flex; gap: 6px; }

  .icon-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    background: transparent;
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    color: var(--text-muted);
    transition: background-color 0.15s, color 0.15s;
  }
  .icon-btn:hover { background: var(--surface-2); color: var(--text); }
  .icon-btn .material-symbols-outlined { font-size: 19px; }

  /* ── Bottom nav (mobile) ── */
  .nav-bottom {
    position: fixed;
    bottom: 0; left: 0; right: 0;
    display: flex;
    justify-content: space-around;
    background: var(--sidebar-bg);
    border-top: 1px solid var(--border);
    padding: 6px 4px;
    padding-bottom: calc(6px + env(safe-area-inset-bottom, 0px));
    z-index: 100;
  }
  .nav-bottom-item {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    padding: 4px;
    color: var(--text-muted);
    font-size: 10px;
    font-weight: 500;
    text-decoration: none;
    border-radius: var(--r-md);
  }
  .nav-bottom-item .material-symbols-outlined { font-size: 21px; }
  .nav-bottom-item.active { color: var(--accent); }

  /* ── Desktop layout ── */
  @media (min-width: 768px) {
    .mobile-header, .nav-bottom { display: none; }

    .sidebar {
      display: flex;
      flex-direction: column;
      width: 244px;
      flex-shrink: 0;
      background: var(--sidebar-bg);
      border-right: 1px solid var(--border);
      position: sticky;
      top: 0;
      height: 100vh;
      height: 100dvh;
    }
    .sidebar-brand { padding: 18px 16px; }

    .sidebar-nav {
      flex: 1;
      display: flex;
      flex-direction: column;
      padding: 12px 0;
      gap: 2px;
      overflow-y: auto;
    }
    .nav-item {
      display: flex;
      align-items: center;
      gap: 11px;
      margin: 0 10px;
      padding: 9px 12px;
      border-radius: var(--r-md);
      color: var(--text-muted);
      font-size: 14px;
      font-weight: 500;
      text-decoration: none;
      transition: background-color 0.15s, color 0.15s;
    }
    .nav-item:hover { background: var(--surface-2); color: var(--text); }
    .nav-item.active {
      background: var(--accent-soft);
      color: var(--accent-ink);
      font-weight: 600;
    }
    .nav-ico { font-size: 20px; }

    .sidebar-foot {
      padding: 12px;
      border-top: 1px solid var(--border);
      display: flex;
      flex-direction: column;
      gap: 10px;
    }

    .page-content { padding: 28px 36px; padding-bottom: 36px; }
  }

  @media (min-width: 1280px) {
    .sidebar { width: 264px; }
    .page-content { padding: 32px 48px; }
  }

  /* ── System status ── */
  .sys-status {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    padding: 9px 11px;
  }
  .sys-row { display: flex; align-items: center; gap: 7px; }
  .sys-row .dot { width: 7px; height: 7px; border-radius: var(--r-pill); }
  .sys-row .dot.ok { background: var(--success); }
  .sys-row .dot.bad { background: var(--danger); }
  .sys-label { font-size: 12px; font-weight: 600; color: var(--text); }
  .sys-meta {
    display: flex; gap: 5px;
    margin-top: 3px; padding-left: 14px;
    font-size: 11px; color: var(--text-faint);
    font-family: var(--font-mono);
  }

  /* ── User card ── */
  .user-card {
    display: flex;
    align-items: center;
    gap: 9px;
    padding: 8px 9px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
  }
  .avatar {
    width: 32px; height: 32px;
    flex-shrink: 0;
    border-radius: var(--r-pill);
    background: var(--accent);
    color: #fff;
    display: flex; align-items: center; justify-content: center;
    font-size: 13px; font-weight: 700;
  }
  .user-info { flex: 1; min-width: 0; }
  .user-name {
    font-size: 13px; font-weight: 600; color: var(--text);
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  .user-role { font-size: 11px; color: var(--text-faint); text-transform: capitalize; }

  /* ── Theme toggle ── */
  .theme-toggle {
    display: flex;
    align-items: center;
    gap: 9px;
    width: 100%;
    padding: 8px 11px;
    background: transparent;
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    color: var(--text-muted);
    font-size: 13px;
    font-weight: 500;
    transition: background-color 0.15s, color 0.15s;
  }
  .theme-toggle:hover { background: var(--surface-2); color: var(--text); }
  .theme-toggle .material-symbols-outlined { font-size: 18px; }
  .tt-label { flex: 1; text-align: left; }
  .tt-value { font-size: 12px; color: var(--text); opacity: 0.75; }
</style>
