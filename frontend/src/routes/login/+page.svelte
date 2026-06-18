<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { auth } from '$lib/stores/auth.svelte';
  import { login, getOidcProviders, getMe } from '$lib/api';

  let username = $state('');
  let password = $state('');
  let showPassword = $state(false);
  let error = $state('');
  let loading = $state(false);
  let providers = $state<{ id: string; name: string }[]>([]);

  const OIDC_ERRORS: Record<string, string> = {
    oidc_state: 'SSO session expired or invalid — try again',
    oidc_exchange: 'SSO token exchange failed — check provider config',
    oidc_discovery: 'Could not reach the SSO provider',
    oidc_claims: 'SSO provider returned no usable account',
    oidc_denied: 'Your SSO account is not permitted to sign in',
  };

  onMount(async () => {
    const url = new URL(window.location.href);
    const token = url.searchParams.get('token');
    const err = url.searchParams.get('error');
    if (err) error = OIDC_ERRORS[err] || 'Sign-in failed';
    if (token) {
      // OIDC callback handed us a token — resolve the user, then finish login.
      try {
        auth.token = token;  // so getMe sends the bearer header
        const me = await getMe();
        auth.login(token, { id: me.id ?? me.user_id, username: me.username, role: me.role, display_name: me.display_name, permissions: me.permissions || [] });
        history.replaceState(null, '', '/login');
        goto('/');
        return;
      } catch {
        auth.logout();
        error = 'SSO sign-in failed — please try again';
      }
    }
    try {
      const r = await getOidcProviders();
      if (r.enabled) providers = r.providers;
    } catch { /* ignore */ }
  });

  $effect(() => {
    if (auth.isAuthenticated) goto('/');
  });

  async function handleLogin(e: Event) {
    e.preventDefault();
    error = '';
    loading = true;
    try {
      const data = await login(username, password);
      auth.login(data.access_token, data.user);
      goto('/');
    } catch (err: any) {
      error = err.message === 'INVALID_CREDENTIALS'
        ? 'Invalid username or password'
        : 'Authentication failed — check your connection';
    } finally {
      loading = false;
    }
  }
</script>

<svelte:head>
  <title>Sign in — RTM Agent</title>
</svelte:head>

<div class="login-page">
  <div class="login-card animate-fade-up">

    <!-- Brand -->
    <div class="brand">
      <div class="brand-mark">RTM</div>
      <div class="brand-text">
        <div class="brand-name">RTM Agent</div>
        <div class="brand-sub">Route-to-Market Classification</div>
      </div>
    </div>

    <h1 class="login-title">Sign in</h1>
    <p class="login-desc">City Holdings Myanmar — P&amp;G route-to-market platform</p>

    <form onsubmit={handleLogin}>
      {#if error}
        <div class="alert alert-danger" style="margin-bottom:16px;">{error}</div>
      {/if}

      <!-- Username -->
      <div class="field">
        <label class="label" for="login-username">Username</label>
        <input
          id="login-username"
          class="input"
          type="text"
          bind:value={username}
          required
          autocomplete="username"
          placeholder="Enter your username"
        />
      </div>

      <!-- Password -->
      <div class="field">
        <label class="label" for="login-password">Password</label>
        <div class="password-wrap">
          <input
            id="login-password"
            class="input"
            type={showPassword ? 'text' : 'password'}
            bind:value={password}
            required
            autocomplete="current-password"
            placeholder="Enter your password"
          />
          <button
            type="button"
            class="toggle-btn"
            onclick={() => showPassword = !showPassword}
          >
            {showPassword ? 'Hide' : 'Show'}
          </button>
        </div>
      </div>

      <!-- Submit -->
      <button
        type="submit"
        class="btn btn-block"
        disabled={loading}
      >
        {loading ? 'Signing in…' : 'Sign in'}
      </button>
    </form>

    {#if providers.length}
      <div class="sso-sep"><span>or continue with</span></div>
      <div class="sso-list">
        {#each providers as p}
          <a class="btn-ghost sso-btn" href={`/api/auth/oidc/${p.id}/login`}>
            <span class="material-symbols-outlined">login</span>
            {p.name}
          </a>
        {/each}
      </div>
    {/if}

    <div class="login-footer">
      <span class="dot-active"></span>
      <span>Secure connection</span>
      <span class="sep">·</span>
      <span>AES-256</span>
      <span class="sep">·</span>
      <span>v1.0</span>
    </div>
  </div>

  <div class="copyright">© 2026 City Holdings Myanmar</div>
</div>

<style>
  .login-page {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 20px;
    padding: 32px 20px;
    background: var(--bg);
  }

  .login-card {
    width: 100%;
    max-width: 400px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    box-shadow: var(--shadow-lg);
    padding: 32px;
  }

  .brand {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 24px;
  }

  .brand-mark {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 44px;
    height: 44px;
    border-radius: var(--r-md);
    background: var(--accent);
    color: var(--accent-ink);
    font-family: var(--font-mono);
    font-weight: 700;
    font-size: 0.85rem;
    letter-spacing: 0.04em;
  }

  .brand-name {
    font-size: 1rem;
    font-weight: 600;
    color: var(--text);
  }

  .brand-sub {
    font-size: 0.75rem;
    color: var(--text-muted);
    margin-top: 2px;
  }

  .login-title {
    font-size: 1.5rem;
    font-weight: 600;
    color: var(--text);
    margin: 0;
  }

  .login-desc {
    font-size: 0.8rem;
    color: var(--text-muted);
    margin: 6px 0 24px;
  }

  .field {
    margin-bottom: 16px;
  }

  .password-wrap {
    position: relative;
  }

  .password-wrap .input {
    padding-right: 60px;
  }

  .toggle-btn {
    position: absolute;
    right: 8px;
    top: 50%;
    transform: translateY(-50%);
    background: none;
    border: none;
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--text-muted);
    cursor: pointer;
    padding: 4px 6px;
    border-radius: var(--r-sm);
  }

  .toggle-btn:hover {
    color: var(--text);
    background: var(--surface-2);
  }

  form .btn-block {
    margin-top: 4px;
  }

  .sso-sep {
    display: flex;
    align-items: center;
    gap: 12px;
    margin: 20px 0 14px;
    color: var(--text-faint);
    font-size: 0.72rem;
  }
  .sso-sep::before, .sso-sep::after {
    content: '';
    flex: 1;
    height: 1px;
    background: var(--border);
  }
  .sso-list { display: flex; flex-direction: column; gap: 8px; }
  .sso-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    width: 100%;
    text-decoration: none;
  }
  .sso-btn .material-symbols-outlined { font-size: 18px; }

  .login-footer {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 20px;
    font-size: 0.72rem;
    color: var(--text-faint);
  }

  .login-footer .sep {
    color: var(--border-strong);
  }

  .dot-active {
    width: 7px;
    height: 7px;
    border-radius: var(--r-pill);
    background: var(--success);
    flex-shrink: 0;
  }

  .copyright {
    font-size: 0.72rem;
    color: var(--text-faint);
    font-family: var(--font-mono);
  }
</style>
