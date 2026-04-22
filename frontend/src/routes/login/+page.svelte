<script lang="ts">
  import { goto } from '$app/navigation';
  import { auth } from '$lib/stores/auth.svelte';
  import { login } from '$lib/api';

  let username = $state('');
  let password = $state('');
  let showPassword = $state(false);
  let error = $state('');
  let loading = $state(false);

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
        ? 'INVALID OPERATOR_ID OR ACCESS_KEY'
        : 'AUTHENTICATION FAILED — CHECK CONNECTION';
    } finally {
      loading = false;
    }
  }
</script>

<svelte:head>
  <title>ACCESS PORTAL — MCP AGENT</title>
</svelte:head>

<div class="login-page" style="height:100vh;display:flex;flex-direction:column;overflow:hidden;background:var(--surface);font-family:'Space Grotesk',sans-serif;">

  <!-- Top bar -->
  <div style="display:flex;align-items:center;justify-content:space-between;padding:8px 24px;border-bottom:3px solid #383832;flex-shrink:0;">
    <div style="background:#383832;color:#00fc40;padding:4px 16px;font-weight:900;font-size:1.1rem;letter-spacing:-0.5px;">
      MCP AGENT
    </div>
    <div style="display:flex;align-items:center;gap:12px;">
      <span style="font-size:9px;font-weight:700;letter-spacing:2px;color:#828179;">CITY AI TEAM</span>
      <span style="font-size:9px;font-weight:900;letter-spacing:1px;padding:2px 10px;background:#006f7c;color:white;">V1.0</span>
    </div>
  </div>

  <!-- Main content -->
  <div style="flex:1;display:flex;align-items:center;padding:0 24px 0 64px;min-height:0;">
    <div style="width:100%;max-width:1400px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;gap:48px;">

      <!-- Left: Form -->
      <div style="width:100%;max-width:480px;">

        <!-- Auth badge + Title -->
        <div style="margin-bottom:4px;">
          <span style="display:inline-block;background:#383832;color:#feffd6;font-size:9px;font-weight:900;letter-spacing:2px;padding:3px 10px;">AUTHENTICATION_REQUIRED</span>
        </div>
        <div style="font-size:2.2rem;font-weight:900;color:#383832;letter-spacing:-1px;border-bottom:3px solid #383832;padding-bottom:6px;">
          ACCESS_PORTAL
        </div>
        <div style="font-size:0.72rem;font-weight:700;color:#828179;letter-spacing:1.5px;margin-top:8px;margin-bottom:24px;">
          CITY HOLDINGS MYANMAR — PG : MCP AGENT
        </div>

        <!-- Form container -->
        <form onsubmit={handleLogin} style="padding:20px;background:var(--surface-container);border-top:2px solid #383832;border-left:2px solid #383832;border-bottom:3px solid #383832;border-right:3px solid #383832;box-shadow:4px 4px 0 #383832;">

          {#if error}
            <div style="background:#be2d06;color:white;font-size:0.72rem;font-weight:900;letter-spacing:1px;padding:8px 14px;margin-bottom:16px;border:2px solid #383832;">
              {error}
            </div>
          {/if}

          <!-- Username -->
          <div style="margin-bottom:12px;">
            <div style="display:inline-block;background:#383832;color:#feffd6;font-size:9px;font-weight:900;letter-spacing:1px;padding:2px 8px;margin-bottom:4px;">OPERATOR_ID</div>
            <input
              type="text"
              bind:value={username}
              required
              autocomplete="username"
              placeholder="Enter credentials"
              style="width:100%;padding:8px 12px;font-family:'Space Grotesk',sans-serif;font-size:0.875rem;font-weight:700;background:white;border:2px solid #383832;color:#383832;outline:none;box-sizing:border-box;"
            />
          </div>

          <!-- Password -->
          <div style="margin-bottom:16px;">
            <div style="display:inline-block;background:#383832;color:#feffd6;font-size:9px;font-weight:900;letter-spacing:1px;padding:2px 8px;margin-bottom:4px;">ACCESS_KEY</div>
            <div style="position:relative;">
              <input
                type={showPassword ? 'text' : 'password'}
                bind:value={password}
                required
                autocomplete="current-password"
                placeholder="Enter password"
                style="width:100%;padding:8px 60px 8px 12px;font-family:'Space Grotesk',sans-serif;font-size:0.875rem;font-weight:700;background:white;border:2px solid #383832;color:#383832;outline:none;box-sizing:border-box;"
              />
              <button
                type="button"
                onclick={() => showPassword = !showPassword}
                style="position:absolute;right:8px;top:50%;transform:translateY(-50%);background:none;border:none;font-family:'Space Grotesk',sans-serif;font-size:9px;font-weight:900;letter-spacing:1px;color:#828179;cursor:pointer;padding:4px;"
              >
                {showPassword ? 'HIDE' : 'SHOW'}
              </button>
            </div>
          </div>

          <!-- Submit -->
          <button
            type="submit"
            disabled={loading}
            style="width:100%;padding:12px;background:#00fc40;color:#383832;border:2px solid #383832;font-family:'Space Grotesk',sans-serif;font-size:0.75rem;font-weight:900;letter-spacing:2px;cursor:pointer;box-shadow:3px 3px 0 #383832;opacity:{loading ? 0.5 : 1};"
            onmousedown={(e) => { e.currentTarget.style.transform='translate(2px,2px)'; e.currentTarget.style.boxShadow='1px 1px 0 #383832'; }}
            onmouseup={(e) => { e.currentTarget.style.transform='translate(0,0)'; e.currentTarget.style.boxShadow='3px 3px 0 #383832'; }}
          >
            {loading ? 'AUTHENTICATING...' : 'INITIATE_AUTHENTICATION'}
          </button>
        </form>

        <!-- Status bar -->
        <div style="margin-top:12px;display:flex;align-items:center;gap:12px;opacity:0.4;">
          <div style="display:flex;align-items:center;gap:6px;">
            <span style="display:inline-block;width:6px;height:6px;background:#007518;"></span>
            <span style="font-size:9px;font-weight:900;letter-spacing:2px;color:#383832;">NODE_ACTIVE</span>
          </div>
          <span style="color:#828179;">|</span>
          <span style="font-size:9px;font-weight:900;letter-spacing:2px;color:#383832;">AES-256</span>
          <span style="color:#828179;">|</span>
          <span style="font-size:9px;font-weight:900;letter-spacing:2px;color:#383832;">V1.0</span>
        </div>
      </div>

      <!-- Right: Big text decoration -->
      <div style="display:none;flex:1;text-align:right;" class="lg-show">
        <div style="font-weight:900;text-transform:uppercase;line-height:0.85;letter-spacing:-4px;font-size:7rem;color:#1a1a1a;opacity:0.08;user-select:none;">
          CITY<br>HOLDINGS<br>MYANMAR
        </div>
        <div style="margin-top:16px;display:flex;align-items:center;justify-content:flex-end;gap:12px;">
          <span style="font-size:1.25rem;font-weight:900;letter-spacing:-1px;color:#1a1a1a;opacity:0.25;">MCP AGENT</span>
          <span style="font-size:1.25rem;font-weight:900;color:#1a1a1a;opacity:0.25;">V1.0</span>
        </div>
      </div>
    </div>
  </div>

  <!-- Footer -->
  <div style="display:flex;align-items:center;justify-content:space-between;padding:8px 24px;border-top:1px solid rgba(56,56,50,0.15);flex-shrink:0;">
    <span style="font-size:9px;font-family:monospace;letter-spacing:1px;color:#828179;opacity:0.4;">&copy; 2026 CITY HOLDINGS MYANMAR</span>
    <span style="font-size:9px;font-family:monospace;letter-spacing:1px;color:#828179;opacity:0.4;">SECURE_TERMINAL</span>
  </div>
</div>

<style>
  @media (min-width: 1024px) {
    .lg-show { display: block !important; }
  }
</style>
