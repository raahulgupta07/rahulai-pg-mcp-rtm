<script lang="ts">
  import { changePassword } from '$lib/api';

  let { open = false, onclose = () => {} } = $props();

  let oldPw = $state('');
  let newPw = $state('');
  let confirmPw = $state('');
  let saving = $state(false);
  let error = $state('');
  let done = $state(false);

  function reset() {
    oldPw = ''; newPw = ''; confirmPw = '';
    error = ''; done = false; saving = false;
  }

  function close() {
    reset();
    onclose();
  }

  async function submit() {
    error = '';
    if (newPw.length < 4) { error = 'New password must be at least 4 characters.'; return; }
    if (newPw !== confirmPw) { error = 'New password and confirmation do not match.'; return; }
    saving = true;
    try {
      await changePassword(oldPw, newPw);
      done = true;
      setTimeout(close, 1400);
    } catch (e: any) {
      error = (e?.message || 'Could not change password').replace(/^\d+\s*/, '');
    } finally {
      saving = false;
    }
  }

  function onKey(e: KeyboardEvent) {
    if (e.key === 'Escape') close();
  }
</script>

<svelte:window onkeydown={onKey} />

{#if open}
  <div class="modal-backdrop" onclick={(e) => { if (e.target === e.currentTarget) close(); }} role="presentation">
    <div class="modal cp-modal animate-fade-up" role="dialog" aria-label="Change password">
      <h3>Change Password</h3>
      <p class="cp-sub">Update the password for your account.</p>

      {#if done}
        <div class="alert alert-success" style="margin-top:14px;">
          <span class="material-symbols-outlined" style="font-size:18px;">check_circle</span>
          Password changed.
        </div>
      {:else}
        {#if error}<div class="alert alert-danger" style="margin:12px 0;">{error}</div>{/if}

        <label class="label" for="cp-old">Current password</label>
        <input id="cp-old" class="input" type="password" bind:value={oldPw} autocomplete="current-password" />

        <label class="label" for="cp-new" style="margin-top:12px;">New password</label>
        <input id="cp-new" class="input" type="password" bind:value={newPw} autocomplete="new-password" />

        <label class="label" for="cp-confirm" style="margin-top:12px;">Confirm new password</label>
        <input id="cp-confirm" class="input" type="password" bind:value={confirmPw} autocomplete="new-password" />

        <div class="cp-actions">
          <button class="btn-ghost" onclick={close} disabled={saving}>Cancel</button>
          <button class="btn" onclick={submit} disabled={saving || !oldPw || !newPw}>
            {saving ? 'Saving…' : 'Change password'}
          </button>
        </div>
      {/if}
    </div>
  </div>
{/if}

<style>
  .cp-modal { max-width: 380px; }
  .cp-sub { font-size: 13px; color: var(--text-muted); margin: 4px 0 8px; }
  .cp-actions {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    margin-top: 18px;
  }
</style>
