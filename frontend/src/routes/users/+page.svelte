<script lang="ts">
  import { auth } from '$lib/stores/auth.svelte';
  import { getUsers, createUser, deleteUser, getSettings, saveSettings, getAuditLog, testLLM,
           getLdapConfig, saveLdapConfig, testLdap, linkUserLdap, resetPassword,
           getGroups, createGroup, updateGroup, deleteGroup, setUserGroups } from '$lib/api';
  import ChapterHeading from '$lib/components/ChapterHeading.svelte';

  let users = $state([]);
  let loading = $state(true);
  let error = $state('');

  let newUsername = $state('');
  let newPassword = $state('');
  let newRole = $state('user');
  let newDisplayName = $state('');
  let newEmail = $state('');
  let newGroups = $state<string[]>([]);
  let creating = $state(false);
  let createError = $state('');

  // Settings state
  let settings = $state<any>(null);
  let settingsLoading = $state(true);
  let llmModel = $state('');
  let llmBaseUrl = $state('');
  let saving = $state(false);
  let saveMsg = $state('');

  // LLM connection test
  let testing = $state(false);
  let testResult = $state<any>(null);

  $effect(() => {
    if (!auth.isSuperAdmin) return;
    loadUsers();
    loadLdap();
    loadGroups();
    getSettings().then(s => {
      settings = s;
      llmModel = s.llm_model || '';
      llmBaseUrl = s.llm_base_url || '';
      settingsLoading = false;
    }).catch(() => { settingsLoading = false; });
  });

  async function handleTest() {
    testing = true;
    testResult = null;
    try {
      testResult = await testLLM(llmModel, llmBaseUrl);
    } catch (e: any) {
      testResult = { ok: false, message: e?.message || 'Test failed' };
    } finally {
      testing = false;
    }
  }

  // ── LDAP servers (multi-server, up to 5) ──
  let ldapServers = $state<any[]>([]);
  let ldapMergeByEmail = $state(true);
  let ldapSaving = $state(false);
  let ldapMsg = $state('');

  function blankServer() {
    return {
      id: '', enabled: true, label: 'New LDAP Server', host: '', port: 389,
      use_tls: false, validate_cert: true, app_dn: '', app_password: '',
      search_base: '', attr_username: 'uid', attr_mail: 'mail',
      search_filter: '', admin_group: '', default_role: 'user',
      app_password_set: false, _testing: false, _test: null,
    };
  }

  async function loadLdap() {
    try {
      const cfg = await getLdapConfig();
      ldapServers = (cfg.servers || []).map((s: any) => ({ ...s, _testing: false, _test: null }));
      ldapMergeByEmail = cfg.merge_by_email ?? true;
    } catch {
      ldapServers = [];
    }
  }

  function addServer() {
    if (ldapServers.length >= 5) return;
    ldapServers = [...ldapServers, blankServer()];
  }

  function removeServer(i: number) {
    if (!confirm('Remove this LDAP server?')) return;
    ldapServers = ldapServers.filter((_, idx) => idx !== i);
  }

  async function handleSaveLdap() {
    ldapSaving = true;
    ldapMsg = '';
    try {
      const payload = ldapServers.map(({ _testing, _test, app_password_set, ...rest }) => rest);
      const res = await saveLdapConfig({ merge_by_email: ldapMergeByEmail, servers: payload });
      ldapServers = (res.config.servers || []).map((s: any) => ({ ...s, _testing: false, _test: null }));
      ldapMsg = 'SAVED';
      setTimeout(() => ldapMsg = '', 3000);
    } catch {
      ldapMsg = 'FAILED';
    } finally {
      ldapSaving = false;
    }
  }

  async function handleTestServer(srv: any) {
    srv._testing = true;
    srv._test = null;
    try {
      srv._test = await testLdap(srv);
    } catch (e: any) {
      srv._test = { ok: false, message: e?.message || 'Test failed' };
    } finally {
      srv._testing = false;
    }
  }

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
      await createUser(newUsername, newPassword, newRole, newDisplayName || newUsername, newEmail, newGroups);
      newUsername = '';
      newPassword = '';
      newRole = 'user';
      newDisplayName = '';
      newEmail = '';
      newGroups = [];
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

  // ── LDAP account linking (merge a local account with a directory username) ──
  let linkUser = $state<any>(null);
  let linkEmail = $state('');
  let linkSaving = $state(false);
  let linkError = $state('');

  function openLink(u: any) {
    linkUser = u;
    linkEmail = u.email || '';
    linkError = '';
  }

  async function saveLink() {
    if (!linkUser) return;
    linkSaving = true;
    linkError = '';
    try {
      await linkUserLdap(linkUser.id, { email: linkEmail.trim() });
      await loadUsers();
      linkUser = null;
    } catch (e: any) {
      linkError = e?.message || 'Failed to save link';
    } finally {
      linkSaving = false;
    }
  }

  // ── Reset a user's password (super-admin) ──
  let resetUser = $state<any>(null);
  let resetPw = $state('');
  let resetSaving = $state(false);
  let resetError = $state('');
  let resetDone = $state(false);

  function openReset(u: any) {
    resetUser = u;
    resetPw = '';
    resetError = '';
    resetDone = false;
  }

  async function saveReset() {
    if (!resetUser) return;
    resetError = '';
    if (resetPw.length < 4) { resetError = 'Password must be at least 4 characters.'; return; }
    resetSaving = true;
    try {
      await resetPassword(resetUser.id, resetPw);
      resetDone = true;
      setTimeout(() => { resetUser = null; }, 1300);
    } catch (e: any) {
      resetError = (e?.message || 'Reset failed').replace(/^\d+\s*/, '');
    } finally {
      resetSaving = false;
    }
  }

  async function handleSaveThresholds() {
    saving = true;
    saveMsg = '';
    try {
      await saveSettings({
        llm_model: llmModel.trim(),
        llm_base_url: llmBaseUrl.trim(),
      });
      saveMsg = 'SAVED';
      if (settings) {
        settings.llm_model = llmModel.trim();
        settings.llm_base_url = llmBaseUrl.trim();
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

  function actionClass(action: string): string {
    const map: Record<string, string> = {
      LOGIN: 'badge-f4',
      CLASSIFY: 'badge-a',
      EXPORT: 'badge-b',
      CREATE_USER: 'badge-a',
      DELETE_USER: 'badge-c',
      SETTINGS: 'badge-neutral',
    };
    return map[action] || 'badge-neutral';
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

  // ── Groups / permission management ──
  let groups = $state<any[]>([]);
  let permCatalog = $state<string[]>([]);
  let groupsLoading = $state(true);
  let groupsError = $state('');

  const PERM_LABELS: Record<string, string> = {
    rules: 'Rules — edit classification rules',
    analytics: 'Analytics — platform analytics',
  };
  function permLabel(p: string): string {
    return PERM_LABELS[p] || p;
  }

  // create-group form
  let gName = $state('');
  let gDesc = $state('');
  let gPerms = $state<string[]>([]);
  let gLdap = $state('');
  let gCreating = $state(false);
  let gCreateError = $state('');

  async function loadGroups() {
    groupsLoading = true;
    groupsError = '';
    try {
      const res = await getGroups();
      groups = Array.isArray(res?.groups) ? res.groups : [];
      permCatalog = Array.isArray(res?.catalog) ? res.catalog : [];
    } catch (e: any) {
      groupsError = e?.message || 'Failed to load groups';
    } finally {
      groupsLoading = false;
    }
  }

  function togglePerm(list: string[], p: string): string[] {
    return list.includes(p) ? list.filter(x => x !== p) : [...list, p];
  }

  async function handleCreateGroup() {
    if (!gName.trim()) {
      gCreateError = 'Group name is required';
      return;
    }
    gCreating = true;
    gCreateError = '';
    try {
      await createGroup({
        name: gName.trim(),
        description: gDesc.trim(),
        permissions: gPerms,
        ldap_group: gLdap.trim(),
      });
      gName = '';
      gDesc = '';
      gPerms = [];
      gLdap = '';
      await loadGroups();
    } catch (e: any) {
      gCreateError = e?.message || 'Failed to create group';
    } finally {
      gCreating = false;
    }
  }

  async function handleDeleteGroup(id: string, name: string) {
    if (!confirm(`Delete group "${name}"?`)) return;
    try {
      await deleteGroup(id);
      await loadGroups();
    } catch (e: any) {
      groupsError = e?.message || 'Failed to delete group';
    }
  }

  // edit-group modal
  let editGroup = $state<any>(null);
  let egName = $state('');
  let egDesc = $state('');
  let egPerms = $state<string[]>([]);
  let egLdap = $state('');
  let egSaving = $state(false);
  let egError = $state('');

  function openEditGroup(g: any) {
    editGroup = g;
    egName = g.name || '';
    egDesc = g.description || '';
    egPerms = [...(g.permissions || [])];
    egLdap = g.ldap_group || '';
    egError = '';
  }

  async function saveEditGroup() {
    if (!editGroup) return;
    if (!egName.trim()) { egError = 'Group name is required'; return; }
    egSaving = true;
    egError = '';
    try {
      await updateGroup(editGroup.id, {
        name: egName.trim(),
        description: egDesc.trim(),
        permissions: egPerms,
        ldap_group: egLdap.trim(),
      });
      await loadGroups();
      editGroup = null;
    } catch (e: any) {
      egError = e?.message || 'Failed to save group';
    } finally {
      egSaving = false;
    }
  }

  // user ↔ group assignment modal
  let groupsUser = $state<any>(null);
  let guSelected = $state<string[]>([]);
  let guSaving = $state(false);
  let guError = $state('');

  function openUserGroups(u: any) {
    groupsUser = u;
    guSelected = [...(u.groups || [])];
    guError = '';
  }

  async function saveUserGroups() {
    if (!groupsUser) return;
    guSaving = true;
    guError = '';
    try {
      await setUserGroups(groupsUser.id, guSelected);
      await loadUsers();
      groupsUser = null;
    } catch (e: any) {
      guError = e?.message || 'Failed to save groups';
    } finally {
      guSaving = false;
    }
  }

  let settingsTab = $state(0);
</script>

<!-- Page header -->
<div class="page-head">
  <h1>Settings</h1>
  <p>System configuration & user management</p>
</div>

{#if !auth.isSuperAdmin}
  <div class="alert alert-danger">
    Access denied — Settings is restricted to super-administrators.
  </div>
{:else}

<!-- Tabs -->
<div class="tab-bar">
  {#each ['Users', 'Model & Config', 'LDAP / Directory', 'Groups', 'Audit Log'] as label, i}
    <button
      class="tab"
      class:active={settingsTab === i}
      onclick={() => { settingsTab = i; if (i === 4 && !auditLoaded) loadAuditLog(); }}
    >
      {label}
    </button>
  {/each}
</div>

<!-- ======== TAB 0: USERS ======== -->
{#if settingsTab === 0}

{#if loading}
  <div class="card card-flush" style="margin-bottom:24px;">
    <div class="data-table-head">
      <span class="title">Users</span>
    </div>
    {#each [1,2,3,4,5] as _}
      <div class="skeleton-row">
        {#each [120,80,60,50,80,70] as w}
          <div class="skeleton" style="height:14px;width:{w}px;"></div>
        {/each}
      </div>
    {/each}
  </div>
{:else if error}
  <div class="alert alert-danger" style="margin-bottom:16px;">{error}</div>
{:else}
  <!-- CREATE USER FORM -->
  <ChapterHeading title="Create User" subtitle="Add a new user to the system" />

  <div class="card" style="margin-bottom:24px;">
    {#if createError}
      <div class="alert alert-danger" style="margin-bottom:16px;">{createError}</div>
    {/if}
    <div class="form-grid">
      <div>
        <label class="label" for="username">Username</label>
        <input id="username" type="text" class="input" bind:value={newUsername} placeholder="username" />
      </div>
      <div>
        <label class="label" for="password">Password</label>
        <input id="password" type="password" class="input" bind:value={newPassword} placeholder="password" />
      </div>
      <div>
        <label class="label" for="display_name">Display Name</label>
        <input id="display_name" type="text" class="input" bind:value={newDisplayName} placeholder="Display Name" />
      </div>
      <div>
        <label class="label" for="email">Email</label>
        <input id="email" type="email" class="input" bind:value={newEmail} placeholder="email@company.com" />
      </div>
      <div>
        <label class="label" for="role">Role</label>
        <select id="role" class="select" bind:value={newRole}>
          <option value="user">User</option>
          <option value="admin">Admin</option>
          <option value="super_admin">Super Admin</option>
        </select>
      </div>
    </div>
    {#if groups.length > 0}
      <div class="field">
        <div class="field-label">Groups</div>
        <div class="check-list">
          {#each groups as g}
            <label class="check-item">
              <input
                type="checkbox"
                checked={newGroups.includes(g.id)}
                onchange={() => newGroups = togglePerm(newGroups, g.id)}
              />
              <span>{g.name}</span>
              {#each (g.permissions || []) as p}
                <span class="badge badge-a">{p}</span>
              {/each}
            </label>
          {/each}
        </div>
      </div>
    {/if}
    <button class="btn" onclick={handleCreate} disabled={creating}>
      {creating ? 'Creating…' : 'Create User'}
    </button>
  </div>

  <!-- USER TABLE -->
  <ChapterHeading title="All Users" subtitle="{users.length} users registered" />

  <div class="card card-flush" style="margin-bottom:24px;">
    <div class="data-table-head">
      <span class="title">Users</span>
      <span class="meta">{users.length} rows</span>
    </div>
    {#if users.length === 0}
      <div class="empty">No users found</div>
    {:else}
      <div class="data-table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Username</th>
              <th>Display Name</th>
              <th>Email</th>
              <th>Role</th>
              <th>Source</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {#each users as user}
              <tr>
                <td class="num">{user.id}</td>
                <td>{user.username}</td>
                <td>{user.display_name ?? '—'}</td>
                <td>{user.email || '—'}</td>
                <td>
                  <span class="badge {user.role === 'super_admin' ? 'badge-f4' : user.role === 'admin' ? 'badge-a' : 'badge-neutral'}">
                    {user.role === 'super_admin' ? 'SUPER ADMIN' : user.role?.toUpperCase()}
                  </span>
                </td>
                <td>
                  {#if user.source === 'ldap'}
                    <span class="badge badge-f4">LDAP</span>
                  {:else}
                    <span class="badge badge-neutral">Local</span>
                  {/if}
                </td>
                <td>
                  <div class="row-actions">
                    <button class="btn-ghost btn-sm" onclick={() => openLink(user)}>Email</button>
                    <button class="btn-ghost btn-sm" onclick={() => openReset(user)}>Reset PW</button>
                    <button class="btn-ghost btn-sm" onclick={() => openUserGroups(user)}>Groups</button>
                    <button class="btn-danger btn-sm" onclick={() => handleDelete(user.id, user.username)}>
                      Delete
                    </button>
                  </div>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </div>
{/if}

<!-- ======== TAB 1: MODEL & CONFIG ======== -->
{:else if settingsTab === 1}

  {#if settingsLoading}
    <div class="config-grid">
      {#each [1, 2] as _}
        <div class="card card-flush">
          <div class="card-head"><span class="skeleton" style="height:14px;width:120px;"></span></div>
          <div style="padding:20px;">
            {#each [1, 2, 3, 4] as __}
              <div class="skeleton" style="height:16px;margin-bottom:16px;width:{60 + Math.random() * 30}%;"></div>
            {/each}
          </div>
        </div>
      {/each}
    </div>
    <div class="card card-flush" style="margin-bottom:24px;">
      <div class="card-head"><span class="skeleton" style="height:14px;width:100px;"></span></div>
      <div style="padding:20px;">
        <div class="skeleton" style="height:16px;margin-bottom:12px;width:70%;"></div>
        <div class="skeleton" style="height:16px;width:50%;"></div>
      </div>
    </div>

  {:else if settings}
    <!-- Two-column grid: LLM PROVIDER + SYSTEM STATUS -->
    <div class="config-grid">

      <!-- Left card: LLM PROVIDER -->
      <div class="card card-flush">
        <div class="card-head">LLM Model &amp; Provider</div>
        <div style="padding:20px;">
          <div class="field">
            <label class="field-label" for="llm-model">Model</label>
            <input id="llm-model" class="input" type="text" bind:value={llmModel}
              placeholder={settings.env_model || 'server default'} />
            <div class="hint">Blank = use the server default (<code>{settings.env_model}</code>).</div>
          </div>

          <div class="field">
            <label class="field-label" for="llm-url">Provider Base URL</label>
            <input id="llm-url" class="input" type="text" bind:value={llmBaseUrl}
              placeholder={settings.env_base_url || 'https://openrouter.ai/api/v1'} />
          </div>

          <div class="field">
            <div class="field-label">API Key</div>
            {#if settings.api_configured}
              <span class="badge badge-a">Configured (.env)</span>
            {:else}
              <span class="badge badge-c">Not Set</span>
            {/if}
          </div>

          <div class="test-row">
            <button class="btn-ghost btn-sm" onclick={handleTest} disabled={testing}>
              {testing ? 'Testing…' : 'Test Connection'}
            </button>
            {#if testResult}
              <span class="test-result" class:ok={testResult.ok} class:bad={!testResult.ok}>
                <span class="material-symbols-outlined" style="font-size:15px;">
                  {testResult.ok ? 'check_circle' : 'error'}
                </span>
                {testResult.message}{testResult.latency_ms ? ` · ${testResult.latency_ms}ms` : ''}
              </span>
            {/if}
          </div>

          {#if saveMsg}
            <div class="save-msg" class:err={saveMsg === 'FAILED'}>{saveMsg}</div>
          {/if}

          <button class="btn btn-block" onclick={handleSaveThresholds} disabled={saving}>
            {saving ? 'Saving…' : 'Save Settings'}
          </button>
          <div class="hint" style="margin-top:8px;">
            Classification thresholds (Pareto cut-offs) are configured on the Rules page.
          </div>
        </div>
      </div>

      <!-- Right card: SYSTEM STATUS -->
      <div class="card card-flush">
        <div class="card-head">System Status</div>
        <div style="padding:20px;">
          <div class="status-row">
            <div class="field-label">Status</div>
            <span class="badge badge-a">Online</span>
          </div>
          <div class="status-row">
            <div class="field-label">Model</div>
            <div class="mono-val">{settings.model}</div>
          </div>
          <div class="status-row">
            <div class="field-label">Pipeline</div>
            <div class="mono-val">Idle</div>
          </div>
          <div class="status-row">
            <div class="field-label">Database</div>
            <span class="badge badge-a">Connected</span>
          </div>
          <div class="status-row" style="border-bottom:none;">
            <div class="field-label">Total Jobs</div>
            <div class="big-num">{settings.total_jobs}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Bottom card: ABOUT (full width) -->
    <div class="card card-flush" style="margin-bottom:24px;">
      <div class="card-head">About</div>
      <div style="padding:20px;">
        <div class="about-title">RTM Agent v{settings.version}</div>
        <div class="about-line">P&G Route-to-Market Outlet Classification</div>
        <div class="about-line">Built by <strong>{settings.team}</strong> — {settings.org}</div>
        <div class="about-line">Powered by <span class="mono-val">{settings.model}</span> via OpenRouter</div>
      </div>
    </div>
  {/if}

<!-- ======== TAB 2: LDAP / DIRECTORY ======== -->
{:else if settingsTab === 2}
  <div class="ldap-intro">
    Configure up to 5 LDAP / Active Directory servers. On a user's first login the
    system tries each enabled server in order — the one that authenticates becomes
    that user's home server and is tried first on later logins.
  </div>

  <label class="merge-toggle">
    <input type="checkbox" bind:checked={ldapMergeByEmail} />
    <span>
      <strong>Auto-merge LDAP logins by email.</strong>
      When an LDAP user's directory email matches an existing account, the login links
      to it automatically (role &amp; history kept). Super-admin accounts are never
      auto-merged. Save to apply.
    </span>
  </label>

  {#each ldapServers as srv, i (srv.id || i)}
    <div class="card card-flush ldap-server">
      <div class="ldap-server-head">
        <span class="ldap-num">{i + 1}</span>
        <input class="input ldap-label-input" bind:value={srv.label} placeholder="Server label" />
        <label class="switch-row" style="margin:0;">
          <input type="checkbox" bind:checked={srv.enabled} />
          <span>Enabled</span>
        </label>
        <button class="btn-danger btn-sm" onclick={() => removeServer(i)}>Remove</button>
      </div>
      <div style="padding:20px;">
        <div class="ldap-grid">
          <div class="field">
            <label class="field-label" for="l-host-{i}">Server host</label>
            <input id="l-host-{i}" class="input" bind:value={srv.host} placeholder="ldap.company.com" />
          </div>
          <div class="field">
            <label class="field-label" for="l-port-{i}">Port</label>
            <input id="l-port-{i}" class="input" type="number" bind:value={srv.port} placeholder="389 / 636" />
          </div>
          <div class="field">
            <label class="field-label" for="l-base-{i}">Search base</label>
            <input id="l-base-{i}" class="input" bind:value={srv.search_base} placeholder="dc=company,dc=com" />
          </div>
          <div class="field">
            <label class="field-label" for="l-dn-{i}">Service account DN</label>
            <input id="l-dn-{i}" class="input" bind:value={srv.app_dn} placeholder="cn=admin,dc=company,dc=com" />
          </div>
          <div class="field">
            <label class="field-label" for="l-pw-{i}">Service account password</label>
            <input id="l-pw-{i}" class="input" type="password" bind:value={srv.app_password}
              placeholder={srv.app_password_set ? '•••••••• (saved — leave blank to keep)' : 'enter password'} />
          </div>
          <div class="field">
            <label class="field-label" for="l-uattr-{i}">Username attribute</label>
            <input id="l-uattr-{i}" class="input" bind:value={srv.attr_username} placeholder="uid / sAMAccountName" />
          </div>
          <div class="field">
            <label class="field-label" for="l-mattr-{i}">Email attribute</label>
            <input id="l-mattr-{i}" class="input" bind:value={srv.attr_mail} placeholder="mail" />
          </div>
          <div class="field">
            <label class="field-label" for="l-filter-{i}">Extra search filter (optional)</label>
            <input id="l-filter-{i}" class="input" bind:value={srv.search_filter} placeholder="(memberOf=cn=allowed,...)" />
          </div>
          <div class="field">
            <label class="field-label" for="l-admin-{i}">Admin group (optional)</label>
            <input id="l-admin-{i}" class="input" bind:value={srv.admin_group} placeholder="cn=rtm-admins" />
          </div>
          <div class="field">
            <label class="field-label" for="l-role-{i}">Default role for new users</label>
            <select id="l-role-{i}" class="select" bind:value={srv.default_role}>
              <option value="user">User</option>
              <option value="admin">Admin</option>
            </select>
          </div>
        </div>

        <div class="ldap-toggles">
          <label class="switch-row">
            <input type="checkbox" bind:checked={srv.use_tls} />
            <span>Use TLS / StartTLS</span>
          </label>
          <label class="switch-row">
            <input type="checkbox" bind:checked={srv.validate_cert} />
            <span>Validate certificate</span>
          </label>
        </div>

        <div class="test-row">
          <button class="btn-ghost btn-sm" onclick={() => handleTestServer(srv)} disabled={srv._testing}>
            {srv._testing ? 'Testing…' : 'Test Connection'}
          </button>
          {#if srv._test}
            <span class="test-result" class:ok={srv._test.ok} class:bad={!srv._test.ok}>
              <span class="material-symbols-outlined" style="font-size:15px;">
                {srv._test.ok ? 'check_circle' : 'error'}
              </span>
              {srv._test.message}{srv._test.latency_ms ? ` · ${srv._test.latency_ms}ms` : ''}
            </span>
          {/if}
        </div>
      </div>
    </div>
  {/each}

  {#if ldapServers.length === 0}
    <div class="alert alert-info" style="margin-bottom:16px;">
      No LDAP servers configured. Add one to enable directory login.
    </div>
  {/if}

  <div class="ldap-actions">
    <button class="btn-ghost" onclick={addServer} disabled={ldapServers.length >= 5}>
      + Add LDAP Server ({ldapServers.length}/5)
    </button>
    <div style="flex:1;"></div>
    {#if ldapMsg}
      <span class="save-msg" class:err={ldapMsg === 'FAILED'} style="margin:0;">{ldapMsg}</span>
    {/if}
    <button class="btn" onclick={handleSaveLdap} disabled={ldapSaving}>
      {ldapSaving ? 'Saving…' : 'Save All Servers'}
    </button>
  </div>

  <div class="ldap-note">
    Local accounts (including super-admin) always work — no lockout if directories are
    unreachable. LDAP users are created on first login; their directory password is never stored.
  </div>

<!-- ======== TAB 3: GROUPS ======== -->
{:else if settingsTab === 3}

  {#if groupsLoading}
    <div class="card card-flush" style="margin-bottom:24px;">
      <div class="data-table-head"><span class="title">Groups</span></div>
      {#each [1,2,3] as _}
        <div class="skeleton-row">
          {#each [120,160,90,80] as w}
            <div class="skeleton" style="height:14px;width:{w}px;"></div>
          {/each}
        </div>
      {/each}
    </div>
  {:else}
    <!-- CREATE GROUP -->
    <ChapterHeading title="Create Group" subtitle="Define a group and its granted permissions" />

    <div class="card" style="margin-bottom:24px;">
      {#if gCreateError}
        <div class="alert alert-danger" style="margin-bottom:16px;">{gCreateError}</div>
      {/if}
      <div class="form-grid">
        <div>
          <label class="label" for="g-name">Name</label>
          <input id="g-name" type="text" class="input" bind:value={gName} placeholder="Analysts" />
        </div>
        <div>
          <label class="label" for="g-desc">Description</label>
          <input id="g-desc" type="text" class="input" bind:value={gDesc} placeholder="What this group is for" />
        </div>
        <div>
          <label class="label" for="g-ldap">LDAP group (optional)</label>
          <input id="g-ldap" type="text" class="input" bind:value={gLdap}
            placeholder="cn=rtm-analysts,ou=groups,dc=..." />
        </div>
      </div>
      <div class="field">
        <div class="field-label">Permissions</div>
        {#if permCatalog.length === 0}
          <div class="hint">No grantable permissions available.</div>
        {:else}
          <div class="check-list">
            {#each permCatalog as p}
              <label class="check-item">
                <input
                  type="checkbox"
                  checked={gPerms.includes(p)}
                  onchange={() => gPerms = togglePerm(gPerms, p)}
                />
                <span>{permLabel(p)}</span>
              </label>
            {/each}
          </div>
        {/if}
      </div>
      <button class="btn" onclick={handleCreateGroup} disabled={gCreating}>
        {gCreating ? 'Creating…' : 'Create Group'}
      </button>
    </div>

    <!-- GROUPS TABLE -->
    <ChapterHeading title="All Groups" subtitle="{groups.length} groups defined" />

    {#if groupsError}
      <div class="alert alert-danger" style="margin-bottom:16px;">{groupsError}</div>
    {/if}

    <div class="card card-flush" style="margin-bottom:24px;">
      <div class="data-table-head">
        <span class="title">Groups</span>
        <span class="meta">{groups.length} rows</span>
      </div>
      {#if groups.length === 0}
        <div class="empty">No groups yet — create one above.</div>
      {:else}
        <div class="data-table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Description</th>
                <th>Permissions</th>
                <th>LDAP Group</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {#each groups as g}
                <tr>
                  <td>{g.name}</td>
                  <td>{g.description || '—'}</td>
                  <td>
                    {#if (g.permissions || []).length === 0}
                      <span class="text-faint">—</span>
                    {:else}
                      <div class="badge-row">
                        {#each g.permissions as p}
                          <span class="badge badge-a">{p}</span>
                        {/each}
                      </div>
                    {/if}
                  </td>
                  <td>
                    {#if g.ldap_group}
                      <span class="mono-cell">{g.ldap_group}</span>
                    {:else}
                      <span class="text-faint">—</span>
                    {/if}
                  </td>
                  <td>
                    <div class="row-actions">
                      <button class="btn-ghost btn-sm" onclick={() => openEditGroup(g)}>Edit</button>
                      <button class="btn-danger btn-sm" onclick={() => handleDeleteGroup(g.id, g.name)}>
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </div>
  {/if}

<!-- ======== TAB 4: AUDIT LOG ======== -->
{:else if settingsTab === 4}

  {#if auditLoading}
    <div class="loading-state">
      <div class="dots">
        <span></span><span></span><span></span>
      </div>
      <div class="loading-text">Loading audit log…</div>
    </div>
  {:else if auditError}
    <div class="alert alert-danger" style="margin-bottom:16px;">{auditError}</div>
  {:else}
    <div class="audit-head">
      <ChapterHeading title="Audit Log" subtitle="{auditLog.length} entries" />
      <button class="btn-ghost btn-sm" onclick={loadAuditLog}>Refresh</button>
    </div>

    <div class="card card-flush" style="margin-bottom:24px;">
      <div class="data-table-head">
        <span class="title">Audit Log</span>
        <span class="meta">{auditLog.length} entries</span>
      </div>
      {#if auditLog.length === 0}
        <div class="empty">No audit entries</div>
      {:else}
        <div class="data-table-wrap" style="max-height:600px;">
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
              {#each auditLog as entry}
                <tr>
                  <td class="mono-cell">{formatTimestamp(entry.timestamp)}</td>
                  <td>{entry.username || '—'}</td>
                  <td>
                    <span class="badge {actionClass(entry.action)}">{entry.action}</span>
                  </td>
                  <td>{entry.details || '—'}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </div>
  {/if}
{/if}
{/if}

{#if linkUser}
  <div class="modal-backdrop" onclick={(e) => { if (e.target === e.currentTarget) linkUser = null; }} role="presentation">
    <div class="modal" role="dialog" aria-label="Link LDAP account">
      <h3>Edit Email — {linkUser.username}</h3>
      <p class="link-sub">
        Set this account's email. An LDAP login whose directory email matches will
        auto-merge into this account — role, history and preferences are kept.
      </p>
      {#if linkError}<div class="alert alert-danger" style="margin:12px 0;">{linkError}</div>{/if}

      <label class="label" for="link-email">Email</label>
      <input id="link-email" class="input" type="email" bind:value={linkEmail}
        placeholder="email@company.com" />
      <div class="link-hint">Used as the auto-merge key for LDAP logins.</div>
      <div class="link-actions">
        <button class="btn-ghost" onclick={() => linkUser = null} disabled={linkSaving}>Cancel</button>
        <button class="btn" onclick={saveLink} disabled={linkSaving}>
          {linkSaving ? 'Saving…' : 'Save link'}
        </button>
      </div>
    </div>
  </div>
{/if}

{#if resetUser}
  <div class="modal-backdrop" onclick={(e) => { if (e.target === e.currentTarget) resetUser = null; }} role="presentation">
    <div class="modal" role="dialog" aria-label="Reset password">
      <h3>Reset Password — {resetUser.username}</h3>
      <p class="link-sub">
        Set a new password for this account. The user can change it later from
        the key icon in the sidebar.
      </p>
      {#if resetDone}
        <div class="alert alert-success" style="margin-top:12px;">
          <span class="material-symbols-outlined" style="font-size:18px;">check_circle</span>
          Password reset.
        </div>
      {:else}
        {#if resetError}<div class="alert alert-danger" style="margin:12px 0;">{resetError}</div>{/if}
        <label class="label" for="reset-pw">New password</label>
        <input id="reset-pw" class="input" type="text" bind:value={resetPw}
          placeholder="new password (min 4 chars)" />
        <div class="link-actions">
          <button class="btn-ghost" onclick={() => resetUser = null} disabled={resetSaving}>Cancel</button>
          <button class="btn" onclick={saveReset} disabled={resetSaving || !resetPw}>
            {resetSaving ? 'Saving…' : 'Reset password'}
          </button>
        </div>
      {/if}
    </div>
  </div>
{/if}

{#if editGroup}
  <div class="modal-backdrop" onclick={(e) => { if (e.target === e.currentTarget) editGroup = null; }} role="presentation">
    <div class="modal" role="dialog" aria-label="Edit group">
      <h3>Edit Group — {editGroup.name}</h3>
      <p class="link-sub">
        Update the group's name, description, granted permissions and optional LDAP mapping.
      </p>
      {#if egError}<div class="alert alert-danger" style="margin:12px 0;">{egError}</div>{/if}

      <label class="label" for="eg-name">Name</label>
      <input id="eg-name" class="input" type="text" bind:value={egName} placeholder="Group name" />

      <label class="label" for="eg-desc" style="margin-top:12px;display:block;">Description</label>
      <input id="eg-desc" class="input" type="text" bind:value={egDesc} placeholder="What this group is for" />

      <div class="label" style="margin-top:12px;">Permissions</div>
      {#if permCatalog.length === 0}
        <div class="hint">No grantable permissions available.</div>
      {:else}
        <div class="check-list">
          {#each permCatalog as p}
            <label class="check-item">
              <input
                type="checkbox"
                checked={egPerms.includes(p)}
                onchange={() => egPerms = togglePerm(egPerms, p)}
              />
              <span>{permLabel(p)}</span>
            </label>
          {/each}
        </div>
      {/if}

      <label class="label" for="eg-ldap" style="margin-top:12px;display:block;">LDAP group (optional)</label>
      <input id="eg-ldap" class="input" type="text" bind:value={egLdap}
        placeholder="cn=rtm-analysts,ou=groups,dc=..." />

      <div class="link-actions">
        <button class="btn-ghost" onclick={() => editGroup = null} disabled={egSaving}>Cancel</button>
        <button class="btn" onclick={saveEditGroup} disabled={egSaving}>
          {egSaving ? 'Saving…' : 'Save group'}
        </button>
      </div>
    </div>
  </div>
{/if}

{#if groupsUser}
  <div class="modal-backdrop" onclick={(e) => { if (e.target === e.currentTarget) groupsUser = null; }} role="presentation">
    <div class="modal" role="dialog" aria-label="Assign groups">
      <h3>Groups — {groupsUser.username}</h3>
      <p class="link-sub">
        Select the groups this user belongs to. Group permissions are granted in addition to the user's role.
      </p>
      {#if guError}<div class="alert alert-danger" style="margin:12px 0;">{guError}</div>{/if}

      {#if groups.length === 0}
        <div class="empty">No groups defined — create one in the Groups tab.</div>
      {:else}
        <div class="check-list">
          {#each groups as g}
            <label class="check-item">
              <input
                type="checkbox"
                checked={guSelected.includes(g.id)}
                onchange={() => guSelected = togglePerm(guSelected, g.id)}
              />
              <span>{g.name}</span>
              {#each (g.permissions || []) as p}
                <span class="badge badge-a">{p}</span>
              {/each}
            </label>
          {/each}
        </div>
      {/if}

      <div class="link-actions">
        <button class="btn-ghost" onclick={() => groupsUser = null} disabled={guSaving}>Cancel</button>
        <button class="btn" onclick={saveUserGroups} disabled={guSaving}>
          {guSaving ? 'Saving…' : 'Save groups'}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .page-head {
    margin-bottom: 24px;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--border);
  }
  .page-head h1 {
    margin: 0;
    font-size: 1.5rem;
    font-weight: 600;
    color: var(--text);
  }
  .page-head p {
    margin: 4px 0 0;
    font-size: 13px;
    color: var(--text-muted);
  }

  .form-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px;
    margin-bottom: 20px;
  }

  .config-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
    margin-bottom: 24px;
  }
  @media (max-width: 720px) {
    .config-grid { grid-template-columns: 1fr; }
  }

  .card-head {
    padding: 14px 20px;
    font-size: 14px;
    font-weight: 600;
    color: var(--text);
    border-bottom: 1px solid var(--border);
  }

  .field { margin-bottom: 16px; }
  .field-label {
    font-size: 12px;
    font-weight: 500;
    color: var(--text-muted);
    margin-bottom: 6px;
  }
  .code-box {
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    padding: 8px 12px;
    font-family: var(--font-mono);
    font-size: 13px;
    color: var(--text);
  }
  .divider {
    border-top: 1px solid var(--border);
    margin: 16px 0;
  }
  .hint {
    font-size: 11.5px;
    color: var(--text-faint);
    margin-top: 5px;
  }
  .hint code {
    font-family: var(--font-mono);
    font-size: 11px;
  }
  .test-row {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    margin-top: 4px;
  }
  .test-result {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 12px;
    font-weight: 500;
  }
  .test-result.ok { color: var(--success); }
  .test-result.bad { color: var(--danger); }

  /* LDAP card */
  .switch-row {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    color: var(--text);
    margin-bottom: 14px;
  }
  .switch-row input { width: 15px; height: 15px; accent-color: var(--accent); cursor: pointer; }
  .ldap-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 14px;
    margin-bottom: 14px;
  }
  .ldap-toggles {
    display: flex;
    gap: 24px;
    flex-wrap: wrap;
    margin-bottom: 14px;
  }
  .ldap-toggles .switch-row { margin-bottom: 0; }
  .ldap-note {
    margin-top: 12px;
    font-size: 12px;
    color: var(--text-muted);
    line-height: 1.55;
  }
  .ldap-intro {
    font-size: 13px;
    color: var(--text-muted);
    line-height: 1.55;
    margin-bottom: 16px;
    max-width: 640px;
  }
  .merge-toggle {
    display: flex;
    gap: 10px;
    align-items: flex-start;
    padding: 12px 14px;
    background: var(--surface-2);
    border: 1px solid var(--border);
    margin-bottom: 16px;
    font-size: 12.5px;
    color: var(--text-muted);
    line-height: 1.55;
  }
  .merge-toggle input {
    width: 15px; height: 15px;
    margin-top: 1px;
    accent-color: var(--accent);
    cursor: pointer;
    flex-shrink: 0;
  }
  .merge-toggle strong { color: var(--text); }
  .ldap-server { margin-bottom: 16px; }
  .ldap-server-head {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 14px;
    border-bottom: 1px solid var(--border);
  }
  .ldap-num {
    width: 24px; height: 24px;
    flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
    background: var(--accent-soft); color: var(--accent-ink);
    font-size: 12px; font-weight: 700;
  }
  .ldap-label-input {
    flex: 1;
    font-weight: 600;
  }
  .ldap-actions {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-top: 4px;
  }
  .row-actions { display: flex; gap: 6px; flex-wrap: wrap; }

  /* Groups — permission checkbox list */
  .check-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-top: 4px;
  }
  .check-item {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    color: var(--text);
    padding: 8px 10px;
    background: var(--surface-2);
    border: 1px solid var(--border);
  }
  .check-item input {
    width: 15px;
    height: 15px;
    accent-color: var(--accent);
    cursor: pointer;
    flex-shrink: 0;
  }
  .badge-row {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
  }
  .text-faint {
    color: var(--text-faint);
  }
  .ldap-alias {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--info);
  }
  .link-sub {
    font-size: 13px;
    color: var(--text-muted);
    line-height: 1.55;
    margin: 6px 0 14px;
  }
  .link-hint {
    font-size: 11.5px;
    color: var(--text-faint);
    margin-top: 5px;
  }
  .link-actions {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    margin-top: 18px;
  }
  @media (max-width: 720px) {
    .ldap-grid { grid-template-columns: 1fr; }
  }
  .save-msg {
    margin-bottom: 12px;
    font-size: 13px;
    font-weight: 500;
    color: var(--success);
  }
  .save-msg.err { color: var(--danger); }

  .status-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 0;
    border-bottom: 1px solid var(--border);
  }
  .status-row .field-label { margin-bottom: 0; }
  .mono-val {
    font-family: var(--font-mono);
    font-size: 13px;
    color: var(--text);
  }
  .big-num {
    font-size: 1.5rem;
    font-weight: 600;
    color: var(--success);
    font-family: var(--font-mono);
  }

  .about-title {
    font-size: 18px;
    font-weight: 600;
    color: var(--text);
    margin-bottom: 8px;
  }
  .about-line {
    font-size: 13px;
    color: var(--text-muted);
    margin-bottom: 4px;
  }
  .about-line strong { color: var(--text); font-weight: 600; }

  .empty {
    text-align: center;
    padding: 32px;
    font-size: 13px;
    color: var(--text-muted);
  }

  .skeleton-row {
    display: flex;
    gap: 12px;
    padding: 14px 16px;
    border-bottom: 1px solid var(--border);
  }
  .skeleton-row:last-child { border-bottom: none; }

  .mono-cell {
    font-family: var(--font-mono);
    font-size: 12px;
    white-space: nowrap;
    color: var(--text-muted);
  }

  .audit-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
  }

  .loading-state {
    text-align: center;
    padding: 48px;
  }
  .dots {
    display: flex;
    justify-content: center;
    gap: 6px;
    margin-bottom: 16px;
  }
  .dots span {
    width: 8px;
    height: 8px;
    border-radius: var(--r-pill);
    background: var(--accent);
    animation: bounce 0.6s ease-in-out infinite;
  }
  .dots span:nth-child(2) { animation-delay: 0.15s; background: var(--warning); }
  .dots span:nth-child(3) { animation-delay: 0.3s; background: var(--info); }
  .loading-text {
    font-size: 13px;
    color: var(--text-muted);
  }

  @keyframes bounce {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-6px); }
  }
</style>
