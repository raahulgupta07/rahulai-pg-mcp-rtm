<script lang="ts">
  import { onMount } from 'svelte';
  import { auth } from '$lib/stores/auth.svelte';
  import { renderMarkdown } from '$lib/md';

  let tabs = $state<any[]>([]);
  let activeTab = $state(0);
  let loading = $state(true);
  let error = $state('');

  let current = $derived(tabs[activeTab] ?? null);
  let isColumns = $derived(current?.kind === 'columns');

  async function load() {
    loading = true;
    error = '';
    try {
      const res = await fetch('/api/docs-content', { headers: auth.getHeaders() });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      tabs = data.tabs ?? [];
    } catch (e) {
      error = 'Could not load documentation.';
    } finally {
      loading = false;
    }
  }

  onMount(load);
</script>

<div class="page animate-fade-in">
  <header class="page-head">
    <h1>Documentation</h1>
    <p>RTM classification system reference</p>
  </header>

  {#if loading}
    <div class="card"><div class="skeleton" style="height:220px;"></div></div>
  {:else if error && !tabs.length}
    <div class="alert alert-danger">{error}</div>
  {:else}
    <div class="tab-bar">
      {#each tabs as tab, i}
        <button class="tab" class:active={activeTab === i} onclick={() => activeTab = i}>
          {tab.label}
        </button>
      {/each}
    </div>

    {#if isColumns}
      <!-- Columns view -->
      <div class="card docs-view">
        {#if current.intro}<p class="col-intro">{current.intro}</p>{/if}
        {#each [['Required columns', current.required], ['Optional columns', current.optional]] as [title, rows]}
          <div class="section-head" style="margin-top:18px;">
            <span class="dot"></span><h3>{title}</h3>
          </div>
          <div class="data-table-wrap">
            <table class="data-table">
              <thead><tr><th>Column</th><th>Description</th></tr></thead>
              <tbody>
                {#each rows ?? [] as r}
                  <tr><td><code>{r.column}</code></td><td>{r.description}</td></tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/each}
      </div>
    {:else}
      <!-- Markdown view -->
      <div class="card prose docs-view">{@html renderMarkdown(current?.markdown ?? '')}</div>
    {/if}
  {/if}
</div>

<style>
  .page { width: 100%; margin: 0; }
  .page-head { margin-bottom: 18px; }
  .page-head h1 { font-size: 24px; }
  .page-head p { margin: 3px 0 0; font-size: 14px; color: var(--text-muted); }

  .tab-bar { margin-bottom: 16px; }
  .docs-view { padding: 24px 28px; }
  .col-intro { font-size: 14px; color: var(--text-muted); margin: 0; }
</style>
