<script lang="ts">
  import { auth } from '$lib/stores/auth.svelte';
  import { getUsers, createUser, deleteUser, getSettings, saveSettings, getAuditLog } from '$lib/api';
  import ChapterHeading from '$lib/components/ChapterHeading.svelte';

  let users = $state([]);
  let loading = $state(true);
  let error = $state('');

  let newUsername = $state('');
  let newPassword = $state('');
  let newRole = $state('viewer');
  let newDisplayName = $state('');
  let creating = $state(false);
  let createError = $state('');

  // Settings state
  let settings = $state<any>(null);
  let settingsLoading = $state(true);
  let thresholdA = $state(80);
  let thresholdB = $state(95);
  let saving = $state(false);
  let saveMsg = $state('');

  $effect(() => {
    loadUsers();
    getSettings().then(s => {
      settings = s;
      thresholdA = s.default_threshold_a || 80;
      thresholdB = s.default_threshold_b || 95;
      settingsLoading = false;
    }).catch(() => { settingsLoading = false; });
  });

  async function loadUsers() {
    loading = true;
    error = '';
    try {
      const raw = await getUsers();
      users = Array.isArray(raw) ? raw : [];
    } catch (e: any) {
      error = e?.message || 'Failed to load users';
    } finally {
      loading = false;
    }
  }

  async function handleCreate() {
    if (!newUsername || !newPassword) {
      createError = 'Username and password are required';
      return;
    }
    creating = true;
    createError = '';
    try {
      await createUser(newUsername, newPassword, newRole, newDisplayName || newUsername);
      newUsername = '';
      newPassword = '';
      newRole = 'viewer';
      newDisplayName = '';
      await loadUsers();
    } catch (e: any) {
      createError = e?.message || 'Failed to create user';
    } finally {
      creating = false;
    }
  }

  async function handleDelete(userId: number, username: string) {
    if (!confirm(`Delete user "${username}"?`)) return;
    try {
      await deleteUser(userId);
      await loadUsers();
    } catch (e: any) {
      error = e?.message || 'Failed to delete user';
    }
  }

  async function handleSaveThresholds() {
    saving = true;
    saveMsg = '';
    try {
      await saveSettings({ threshold_a: thresholdA, threshold_b: thresholdB });
      saveMsg = 'SAVED';
      if (settings) {
        settings.default_threshold_a = thresholdA;
        settings.default_threshold_b = thresholdB;
      }
      setTimeout(() => saveMsg = '', 3000);
    } catch (e) {
      saveMsg = 'FAILED';
    } finally {
      saving = false;
    }
  }
  // Audit log state
  let auditLog = $state<any[]>([]);
  let auditLoading = $state(false);
  let auditError = $state('');
  let auditLoaded = $state(false);

  function actionColor(action: string): string {
    const colors: Record<string, string> = {
      LOGIN: '#006f7c',
      CLASSIFY: '#007518',
      EXPORT: '#ff9d00',
      CREATE_USER: '#007518',
      DELETE_USER: '#be2d06',
      SETTINGS: '#9d4867',
    };
    return colors[action] || '#383832';
  }

  function formatTimestamp(ts: string): string {
    try {
      const d = new Date(ts);
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) +
        ' ' + d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch {
      return ts;
    }
  }

  async function loadAuditLog() {
    auditLoading = true;
    auditError = '';
    try {
      auditLog = await getAuditLog();
      auditLoaded = true;
    } catch (e: any) {
      auditError = e?.message || 'Failed to load audit log';
    } finally {
      auditLoading = false;
    }
  }

  let settingsTab = $state(0);
</script>

<!-- HERO BOX -->
<div style="background:#383832;color:#feffd6;padding:16px 24px;margin-bottom:24px;border-bottom:4px solid #383832;border-right:4px solid #383832;">
  <div style="font-size:1.5rem;font-weight:900;letter-spacing:-0.03em;">SETTINGS</div>
  <div style="font-size:11px;opacity:0.75;margin-top:4px;">SYSTEM CONFIGURATION & USER MANAGEMENT</div>
</div>

<!-- Tab buttons -->
<div style="display:flex;gap:6px;margin-bottom:24px;">
  {#each ['USERS', 'MODEL & CONFIG', 'AUDIT LOG'] as label, i}
    <button
      onclick={() => { settingsTab = i; if (i === 2 && !auditLoaded) loadAuditLog(); }}
      style="
        padding:8px 20px;font-size:10px;font-weight:900;letter-spacing:0.08em;
        text-transform:uppercase;cursor:pointer;font-family:'Space Grotesk',sans-serif;
        border:2px solid #383832;transition:all 0.15s;
        {settingsTab === i
          ? 'background:#383832;color:#feffd6;box-shadow:3px 3px 0 #383832;'
          : 'background:#feffd6;color:#383832;box-shadow:3px 3px 0 #383832;'}
      "
      onmouseenter={(e) => { if (settingsTab !== i) { e.currentTarget.style.background='#007518'; e.currentTarget.style.color='white'; e.currentTarget.style.borderColor='#007518'; }}}
      onmouseleave={(e) => { if (settingsTab !== i) { e.currentTarget.style.background='#feffd6'; e.currentTarget.style.color='#383832'; e.currentTarget.style.borderColor='#383832'; }}}
      onmousedown={(e) => { e.currentTarget.style.transform='translate(2px,2px)'; e.currentTarget.style.boxShadow='1px 1px 0 #383832'; }}
      onmouseup={(e) => { e.currentTarget.style.transform='translate(0,0)'; e.currentTarget.style.boxShadow='3px 3px 0 #383832'; }}
    >
      {label}
    </button>
  {/each}
</div>

<!-- ======== TAB 0: USERS ======== -->
{#if settingsTab === 0}

{#if loading}
  <div style="margin-bottom:24px;">
    <!-- Skeleton title bar -->
    <div style="height:44px;background:#383832;margin-bottom:0;"></div>
    <!-- Skeleton rows -->
    {#each [1,2,3,4,5] as _}
      <div style="display:flex;gap:12px;padding:12px 16px;border-bottom:1px solid #ebe8dd;background:white;">
        {#each [120,80,60,50,80,70] as w}
          <div style="height:14px;width:{w}px;background:#ebe8dd;animation:skeleton-pulse 1.5s ease-in-out infinite;"></div>
        {/each}
      </div>
    {/each}
  </div>
{:else if error}
  <div style="padding:16px;background:#be2d06;color:white;font-size:12px;font-weight:700;border:2px solid #383832;margin-bottom:16px;">
    ERROR: {error}
  </div>
{:else}
  <!-- CREATE USER FORM -->
  <ChapterHeading title="Create User" subtitle="Add a new user to the system" />

  <div style="background:white;border:3px solid #383832;box-shadow:4px 4px 0 #383832;padding:24px;margin-bottom:24px;">
    {#if createError}
      <div style="padding:8px 12px;background:#be2d06;color:white;font-size:11px;font-weight:700;margin-bottom:16px;border:2px solid #383832;">
        {createError}
      </div>
    {/if}
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:16px;">
      <div>
        <label for="username" style="display:block;font-size:10px;font-weight:900;letter-spacing:0.08em;color:#383832;margin-bottom:4px;">USERNAME</label>
        <input
          id="username"
          type="text"
          bind:value={newUsername}
          placeholder="username"
          style="width:100%;padding:8px 12px;font-size:12px;font-weight:700;border:2px solid #383832;border-radius:0;background:#f6f4e9;font-family:'Space Grotesk',sans-serif;"
        />
      </div>
      <div>
        <label for="password" style="display:block;font-size:10px;font-weight:900;letter-spacing:0.08em;color:#383832;margin-bottom:4px;">PASSWORD</label>
        <input
          id="password"
          type="password"
          bind:value={newPassword}
          placeholder="password"
          style="width:100%;padding:8px 12px;font-size:12px;font-weight:700;border:2px solid #383832;border-radius:0;background:#f6f4e9;font-family:'Space Grotesk',sans-serif;"
        />
      </div>
      <div>
        <label for="display_name" style="display:block;font-size:10px;font-weight:900;letter-spacing:0.08em;color:#383832;margin-bottom:4px;">DISPLAY NAME</label>
        <input
          id="display_name"
          type="text"
          bind:value={newDisplayName}
          placeholder="Display Name"
          style="width:100%;padding:8px 12px;font-size:12px;font-weight:700;border:2px solid #383832;border-radius:0;background:#f6f4e9;font-family:'Space Grotesk',sans-serif;"
        />
      </div>
      <div>
        <label for="role" style="display:block;font-size:10px;font-weight:900;letter-spacing:0.08em;color:#383832;margin-bottom:4px;">ROLE</label>
        <select
          id="role"
          bind:value={newRole}
          style="width:100%;padding:8px 12px;font-size:12px;font-weight:700;border:2px solid #383832;border-radius:0;background:#f6f4e9;font-family:'Space Grotesk',sans-serif;"
        >
          <option value="viewer">VIEWER</option>
          <option value="admin">ADMIN</option>
        </select>
      </div>
    </div>
    <button
      onclick={handleCreate}
      disabled={creating}
      style="padding:10px 24px;font-size:11px;font-weight:900;letter-spacing:0.1em;background:#00fc40;color:#383832;border:2px solid #383832;box-shadow:3px 3px 0 #383832;cursor:pointer;font-family:'Space Grotesk',sans-serif;border-radius:0;"
    >
      {creating ? 'CREATING...' : 'CREATE USER'}
    </button>
  </div>

  <!-- USER TABLE -->
  <ChapterHeading title="All Users" subtitle="{users.length} users registered" />

  <div style="border:3px solid #383832;box-shadow:4px 4px 0 #383832;overflow:hidden;margin-bottom:24px;">
    <div style="padding:8px 12px;background:#383832;color:#feffd6;font-size:10px;font-weight:900;letter-spacing:0.1em;display:flex;justify-content:space-between;">
      <span>USERS</span>
      <span style="opacity:0.7;">{users.length} ROWS</span>
    </div>
    {#if users.length === 0}
      <div style="text-align:center;padding:32px;">
        <div style="font-size:12px;font-weight:900;color:#383832;">NO USERS FOUND</div>
      </div>
    {:else}
      <table style="width:100%;border-collapse:collapse;font-size:12px;">
        <thead>
          <tr>
            <th style="position:sticky;top:0;background:#ebe8dd;padding:8px 12px;text-align:left;font-size:10px;font-weight:800;letter-spacing:0.08em;text-transform:uppercase;color:#383832;border-bottom:2px solid #383832;">ID</th>
            <th style="position:sticky;top:0;background:#ebe8dd;padding:8px 12px;text-align:left;font-size:10px;font-weight:800;letter-spacing:0.08em;text-transform:uppercase;color:#383832;border-bottom:2px solid #383832;">USERNAME</th>
            <th style="position:sticky;top:0;background:#ebe8dd;padding:8px 12px;text-align:left;font-size:10px;font-weight:800;letter-spacing:0.08em;text-transform:uppercase;color:#383832;border-bottom:2px solid #383832;">DISPLAY NAME</th>
            <th style="position:sticky;top:0;background:#ebe8dd;padding:8px 12px;text-align:left;font-size:10px;font-weight:800;letter-spacing:0.08em;text-transform:uppercase;color:#383832;border-bottom:2px solid #383832;">ROLE</th>
            <th style="position:sticky;top:0;background:#ebe8dd;padding:8px 12px;text-align:left;font-size:10px;font-weight:800;letter-spacing:0.08em;text-transform:uppercase;color:#383832;border-bottom:2px solid #383832;">ACTIONS</th>
          </tr>
        </thead>
        <tbody>
          {#each users as user, i}
            <tr style="background:{i % 2 === 0 ? 'white' : '#fcf9ef'};border-bottom:1px solid #ebe8dd;">
              <td style="padding:8px 12px;font-size:11px;font-weight:600;color:#383832;">{user.id}</td>
              <td style="padding:8px 12px;font-size:11px;font-weight:600;color:#383832;">{user.username}</td>
              <td style="padding:8px 12px;font-size:11px;font-weight:600;color:#383832;">{user.display_name ?? '--'}</td>
              <td style="padding:8px 12px;font-size:11px;font-weight:900;letter-spacing:0.06em;color:{user.role === 'admin' ? '#007518' : '#828179'};">{user.role?.toUpperCase()}</td>
              <td style="padding:8px 12px;">
                <button
                  onclick={() => handleDelete(user.id, user.username)}
                  style="padding:4px 10px;font-size:10px;font-weight:900;letter-spacing:0.06em;background:#be2d06;color:white;border:2px solid #383832;cursor:pointer;font-family:'Space Grotesk',sans-serif;border-radius:0;"
                >
                  DELETE
                </button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </div>
{/if}

<!-- ======== TAB 1: MODEL & CONFIG ======== -->
{:else if settingsTab === 1}

  {#if settingsLoading}
    <!-- Loading skeleton -->
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:24px;padding:0 0 24px;">
      {#each [1, 2] as _}
        <div style="
          background:#f5f5ee;
          border-top:2px solid #383832;border-left:2px solid #383832;
          border-bottom:4px solid #383832;border-right:4px solid #383832;
          box-shadow:4px 4px 0px #383832;
          min-height:280px;
          animation:pulse 1.5s ease-in-out infinite;
        ">
          <div style="background:#383832;height:36px;"></div>
          <div style="padding:20px;">
            {#each [1, 2, 3, 4] as __}
              <div style="background:#e0e0d8;height:16px;margin-bottom:16px;width:{60 + Math.random() * 30}%;"></div>
            {/each}
          </div>
        </div>
      {/each}
    </div>
    <div style="padding:0 0 24px;">
      <div style="
        background:#f5f5ee;
        border-top:2px solid #383832;border-left:2px solid #383832;
        border-bottom:4px solid #383832;border-right:4px solid #383832;
        box-shadow:4px 4px 0px #383832;
        min-height:100px;
        animation:pulse 1.5s ease-in-out infinite;
      ">
        <div style="background:#383832;height:36px;"></div>
        <div style="padding:20px;">
          <div style="background:#e0e0d8;height:16px;margin-bottom:12px;width:70%;"></div>
          <div style="background:#e0e0d8;height:16px;width:50%;"></div>
        </div>
      </div>
    </div>

  {:else if settings}
    <!-- Two-column grid: LLM PROVIDER + SYSTEM STATUS -->
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:24px;padding:0 0 24px;font-family:'Space Grotesk',sans-serif;">

      <!-- Left card: LLM PROVIDER -->
      <div style="
        background:#feffd6;
        border-top:2px solid #383832;border-left:2px solid #383832;
        border-bottom:4px solid #383832;border-right:4px solid #383832;
        box-shadow:4px 4px 0px #383832;
      ">
        <!-- Dark bar title -->
        <div style="background:#383832;color:#feffd6;padding:10px 16px;font-weight:900;font-size:12px;letter-spacing:0.05em;text-transform:uppercase;">
          <span style="color:#ff9d00;margin-right:8px;">&#x25C6;</span>LLM PROVIDER
        </div>

        <div style="padding:20px;">
          <!-- MODEL -->
          <div style="margin-bottom:16px;">
            <div style="font-size:10px;font-weight:900;text-transform:uppercase;color:#383832;opacity:0.6;margin-bottom:4px;letter-spacing:0.05em;">MODEL</div>
            <div style="
              background:#f5f5ee;padding:8px 12px;font-family:monospace;font-size:13px;color:#383832;
              border:2px solid #383832;
            ">{settings.model}</div>
          </div>

          <!-- API KEY -->
          <div style="margin-bottom:16px;">
            <div style="font-size:10px;font-weight:900;text-transform:uppercase;color:#383832;opacity:0.6;margin-bottom:4px;letter-spacing:0.05em;">API KEY</div>
            {#if settings.api_configured}
              <span style="
                display:inline-block;padding:4px 10px;font-size:11px;font-weight:900;text-transform:uppercase;
                background:#007518;color:#feffd6;letter-spacing:0.05em;
              ">CONFIGURED</span>
            {:else}
              <span style="
                display:inline-block;padding:4px 10px;font-size:11px;font-weight:900;text-transform:uppercase;
                background:#be2d06;color:#feffd6;letter-spacing:0.05em;
              ">NOT SET</span>
            {/if}
          </div>

          <!-- BASE URL -->
          <div style="margin-bottom:20px;">
            <div style="font-size:10px;font-weight:900;text-transform:uppercase;color:#383832;opacity:0.6;margin-bottom:4px;letter-spacing:0.05em;">BASE URL</div>
            <div style="
              background:#f5f5ee;padding:8px 12px;font-family:monospace;font-size:12px;color:#383832;
              border:2px solid #383832;word-break:break-all;
            ">{settings.base_url}</div>
          </div>

          <!-- Divider -->
          <div style="border-top:2px solid #383832;margin-bottom:16px;"></div>

          <!-- PARETO DEFAULTS -->
          <div style="font-size:10px;font-weight:900;text-transform:uppercase;color:#383832;opacity:0.6;margin-bottom:12px;letter-spacing:0.05em;">PARETO DEFAULTS</div>

          <div style="display:flex;gap:24px;margin-bottom:16px;">
            <div style="flex:1;">
              <label style="font-size:10px;font-weight:900;text-transform:uppercase;color:#383832;display:block;margin-bottom:4px;letter-spacing:0.05em;">
                CLASS A CUTOFF: <span style="color:#007518;">{thresholdA}%</span>
              </label>
              <input type="range" min="50" max="95" bind:value={thresholdA}
                style="width:100%;accent-color:#007518;cursor:pointer;" />
            </div>
            <div style="flex:1;">
              <label style="font-size:10px;font-weight:900;text-transform:uppercase;color:#383832;display:block;margin-bottom:4px;letter-spacing:0.05em;">
                CLASS B CUTOFF: <span style="color:#ff9d00;">{thresholdB}%</span>
              </label>
              <input type="range" min={thresholdA + 1} max="99" bind:value={thresholdB}
                style="width:100%;accent-color:#ff9d00;cursor:pointer;" />
            </div>
          </div>

          {#if saveMsg}
            <div style="margin-bottom:12px;font-size:11px;font-weight:700;color:{saveMsg === 'SAVED' ? '#007518' : '#be2d06'};">{saveMsg}</div>
          {/if}

          <button
            onclick={handleSaveThresholds}
            disabled={saving}
            style="width:100%;padding:10px;font-size:11px;font-weight:900;letter-spacing:0.1em;text-transform:uppercase;cursor:pointer;border:2px solid #383832;box-shadow:3px 3px 0 #383832;background:#00fc40;color:#383832;"
          >
            {saving ? 'SAVING...' : 'SAVE THRESHOLDS'}
          </button>
        </div>
      </div>

      <!-- Right card: SYSTEM STATUS -->
      <div style="
        background:#feffd6;
        border-top:2px solid #383832;border-left:2px solid #383832;
        border-bottom:4px solid #383832;border-right:4px solid #383832;
        box-shadow:4px 4px 0px #383832;
      ">
        <!-- Dark bar title -->
        <div style="background:#383832;color:#feffd6;padding:10px 16px;font-weight:900;font-size:12px;letter-spacing:0.05em;text-transform:uppercase;">
          <span style="color:#ff9d00;margin-right:8px;">&#x25C6;</span>SYSTEM STATUS
        </div>

        <div style="padding:20px;">
          <!-- STATUS -->
          <div style="margin-bottom:16px;display:flex;justify-content:space-between;align-items:center;">
            <div style="font-size:10px;font-weight:900;text-transform:uppercase;color:#383832;opacity:0.6;letter-spacing:0.05em;">STATUS</div>
            <span style="
              display:inline-block;padding:4px 10px;font-size:11px;font-weight:900;text-transform:uppercase;
              background:#007518;color:#feffd6;letter-spacing:0.05em;
            ">ONLINE</span>
          </div>

          <!-- MODEL -->
          <div style="margin-bottom:16px;display:flex;justify-content:space-between;align-items:center;">
            <div style="font-size:10px;font-weight:900;text-transform:uppercase;color:#383832;opacity:0.6;letter-spacing:0.05em;">MODEL</div>
            <div style="font-family:monospace;font-size:13px;color:#383832;font-weight:700;">{settings.model}</div>
          </div>

          <!-- PIPELINE -->
          <div style="margin-bottom:16px;display:flex;justify-content:space-between;align-items:center;">
            <div style="font-size:10px;font-weight:900;text-transform:uppercase;color:#383832;opacity:0.6;letter-spacing:0.05em;">PIPELINE</div>
            <div style="font-family:monospace;font-size:13px;color:#383832;font-weight:700;">IDLE</div>
          </div>

          <!-- DATABASE -->
          <div style="margin-bottom:16px;display:flex;justify-content:space-between;align-items:center;">
            <div style="font-size:10px;font-weight:900;text-transform:uppercase;color:#383832;opacity:0.6;letter-spacing:0.05em;">DATABASE</div>
            <span style="
              display:inline-block;padding:4px 10px;font-size:11px;font-weight:900;text-transform:uppercase;
              background:#007518;color:#feffd6;letter-spacing:0.05em;
            ">CONNECTED</span>
          </div>

          <!-- TOTAL JOBS -->
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <div style="font-size:10px;font-weight:900;text-transform:uppercase;color:#383832;opacity:0.6;letter-spacing:0.05em;">TOTAL JOBS</div>
            <div style="font-size:1.5rem;font-weight:900;color:#007518;">{settings.total_jobs}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Bottom card: ABOUT (full width) -->
    <div style="margin:0 0 24px;font-family:'Space Grotesk',sans-serif;">
      <div style="
        background:#feffd6;
        border-top:2px solid #383832;border-left:2px solid #383832;
        border-bottom:4px solid #383832;border-right:4px solid #383832;
        box-shadow:4px 4px 0px #383832;
      ">
        <!-- Dark bar title -->
        <div style="background:#383832;color:#feffd6;padding:10px 16px;font-weight:900;font-size:12px;letter-spacing:0.05em;text-transform:uppercase;">
          <span style="color:#ff9d00;margin-right:8px;">&#x25C6;</span>ABOUT
        </div>

        <div style="padding:20px;">
          <div style="font-weight:900;font-size:18px;color:#383832;margin-bottom:8px;letter-spacing:-0.02em;">MCP AGENT V{settings.version}</div>
          <div style="font-size:13px;color:#383832;margin-bottom:4px;">P&G Route-to-Market Outlet Classification</div>
          <div style="font-size:13px;color:#383832;margin-bottom:4px;">Built by <span style="font-weight:900;">{settings.team}</span> — {settings.org}</div>
          <div style="font-size:13px;color:#383832;">Powered by <span style="font-weight:700;font-family:monospace;">{settings.model}</span> via OpenRouter</div>
        </div>
      </div>
    </div>
  {/if}

<!-- ======== TAB 2: AUDIT LOG ======== -->
{:else if settingsTab === 2}

  {#if auditLoading}
    <div style="text-align:center;padding:48px;">
      <div style="display:flex;justify-content:center;gap:6px;margin-bottom:16px;">
        <span style="width:8px;height:8px;background:#007518;animation:bounce 0.6s ease-in-out infinite;"></span>
        <span style="width:8px;height:8px;background:#ff9d00;animation:bounce 0.6s ease-in-out infinite;animation-delay:0.15s;"></span>
        <span style="width:8px;height:8px;background:#be2d06;animation:bounce 0.6s ease-in-out infinite;animation-delay:0.3s;"></span>
      </div>
      <div style="font-size:11px;font-weight:700;color:#828179;letter-spacing:0.08em;">LOADING AUDIT LOG...</div>
    </div>
  {:else if auditError}
    <div style="padding:16px;background:#be2d06;color:white;font-size:12px;font-weight:700;border:2px solid #383832;margin-bottom:16px;">
      ERROR: {auditError}
    </div>
  {:else}
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
      <ChapterHeading title="Audit Log" subtitle="{auditLog.length} entries" />
      <button
        onclick={loadAuditLog}
        style="padding:6px 16px;font-size:10px;font-weight:900;letter-spacing:0.08em;background:#feffd6;color:#383832;border:2px solid #383832;box-shadow:3px 3px 0 #383832;cursor:pointer;font-family:'Space Grotesk',sans-serif;border-radius:0;"
      >
        REFRESH
      </button>
    </div>

    <div style="border:3px solid #383832;box-shadow:4px 4px 0 #383832;overflow:hidden;margin-bottom:24px;">
      <div style="padding:8px 12px;background:#383832;color:#feffd6;font-size:10px;font-weight:900;letter-spacing:0.1em;display:flex;justify-content:space-between;">
        <span>AUDIT LOG</span>
        <span style="opacity:0.7;">{auditLog.length} ENTRIES</span>
      </div>
      {#if auditLog.length === 0}
        <div style="text-align:center;padding:32px;">
          <div style="font-size:12px;font-weight:900;color:#383832;">NO AUDIT ENTRIES</div>
        </div>
      {:else}
        <div style="max-height:600px;overflow-y:auto;">
          <table style="width:100%;border-collapse:collapse;font-size:12px;">
            <thead>
              <tr>
                <th style="position:sticky;top:0;background:#ebe8dd;padding:8px 12px;text-align:left;font-size:10px;font-weight:800;letter-spacing:0.08em;text-transform:uppercase;color:#383832;border-bottom:2px solid #383832;">TIME</th>
                <th style="position:sticky;top:0;background:#ebe8dd;padding:8px 12px;text-align:left;font-size:10px;font-weight:800;letter-spacing:0.08em;text-transform:uppercase;color:#383832;border-bottom:2px solid #383832;">USER</th>
                <th style="position:sticky;top:0;background:#ebe8dd;padding:8px 12px;text-align:left;font-size:10px;font-weight:800;letter-spacing:0.08em;text-transform:uppercase;color:#383832;border-bottom:2px solid #383832;">ACTION</th>
                <th style="position:sticky;top:0;background:#ebe8dd;padding:8px 12px;text-align:left;font-size:10px;font-weight:800;letter-spacing:0.08em;text-transform:uppercase;color:#383832;border-bottom:2px solid #383832;">DETAILS</th>
              </tr>
            </thead>
            <tbody>
              {#each auditLog as entry, i}
                <tr style="background:{i % 2 === 0 ? 'white' : '#fcf9ef'};border-bottom:1px solid #ebe8dd;">
                  <td style="padding:8px 12px;font-size:11px;font-weight:600;color:#383832;font-family:monospace;white-space:nowrap;">{formatTimestamp(entry.timestamp)}</td>
                  <td style="padding:8px 12px;font-size:11px;font-weight:700;color:#383832;">{entry.username || '--'}</td>
                  <td style="padding:8px 12px;">
                    <span style="
                      display:inline-block;padding:3px 8px;font-size:10px;font-weight:900;letter-spacing:0.06em;
                      background:{actionColor(entry.action)};color:#feffd6;text-transform:uppercase;
                    ">{entry.action}</span>
                  </td>
                  <td style="padding:8px 12px;font-size:11px;font-weight:600;color:#383832;">{entry.details || '--'}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </div>
  {/if}
{/if}

<style>
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }
</style>
