<script lang="ts">
  /**
   * Checkbox dropdown. Empty selection = "All" (no filtering), which keeps the
   * filter engine simple: an empty array never narrows anything.
   */
  let {
    label = '',
    options = [],
    selected = $bindable([]),
    placeholder = 'All',
    searchable = null,   // null = auto (search box appears once the list is long)
  } = $props();

  let open = $state(false);
  let query = $state('');
  let root: HTMLDivElement;

  const showSearch = $derived(searchable ?? options.length > 8);

  const shown = $derived(
    query.trim()
      ? options.filter(o => String(o).toLowerCase().includes(query.trim().toLowerCase()))
      : options
  );

  const summary = $derived(
    selected.length === 0
      ? placeholder
      : selected.length === 1
        ? String(selected[0])
        : `${selected[0]} +${selected.length - 1}`
  );

  function toggle(opt) {
    selected = selected.includes(opt)
      ? selected.filter(o => o !== opt)
      : [...selected, opt];
  }

  function clear() {
    selected = [];
    query = '';
  }

  function selectAllShown() {
    selected = [...new Set([...selected, ...shown])];
  }

  // Close when focus or a click leaves the control
  function onWindowClick(e: MouseEvent) {
    if (open && root && !root.contains(e.target as Node)) open = false;
  }
</script>

<svelte:window onclick={onWindowClick} />

<div class="ms" bind:this={root}>
  {#if label}<span class="ms-label">{label}</span>{/if}

  <button
    type="button"
    class="ms-trigger"
    class:has-value={selected.length > 0}
    onclick={() => (open = !open)}
  >
    <span class="ms-summary">{summary}</span>
    <span class="ms-caret" aria-hidden="true">▾</span>
  </button>

  {#if open}
    <div class="ms-pop">
      {#if showSearch}
        <input
          class="ms-search"
          placeholder="Search…"
          bind:value={query}
        />
      {/if}

      <div class="ms-actions">
        <button type="button" onclick={selectAllShown}>Select {query ? 'matching' : 'all'}</button>
        <button type="button" onclick={clear} disabled={!selected.length}>Clear</button>
      </div>

      <div class="ms-list">
        {#each shown as opt (opt)}
          <label class="ms-opt">
            <input
              type="checkbox"
              checked={selected.includes(opt)}
              onchange={() => toggle(opt)}
            />
            <span class="ms-opt-text">{opt}</span>
          </label>
        {:else}
          <div class="ms-empty">No matches</div>
        {/each}
      </div>

      {#if selected.length}
        <div class="ms-foot">{selected.length} selected</div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .ms {
    position: relative;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .ms-label {
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--text-muted);
  }
  .ms-trigger {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    height: 32px;
    min-width: 132px;
    max-width: 200px;
    padding: 0 8px;
    font-size: 0.8rem;
    font-family: inherit;
    color: var(--text);
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r-sm, 6px);
    cursor: pointer;
  }
  .ms-trigger:hover { border-color: var(--border-strong); }
  .ms-trigger.has-value {
    border-color: var(--accent);
    color: var(--accent);
    font-weight: 500;
  }
  .ms-summary {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .ms-caret { font-size: 0.6rem; opacity: 0.6; flex-shrink: 0; }

  .ms-pop {
    position: absolute;
    top: calc(100% + 4px);
    left: 0;
    z-index: 40;
    width: 240px;
    padding: 8px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r-md, 8px);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  }
  .ms-search {
    width: 100%;
    height: 30px;
    padding: 0 8px;
    margin-bottom: 6px;
    font-size: 0.8rem;
    font-family: inherit;
    color: var(--text);
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: var(--r-sm, 6px);
  }
  .ms-actions {
    display: flex;
    justify-content: space-between;
    padding-bottom: 6px;
    margin-bottom: 4px;
    border-bottom: 1px solid var(--border);
  }
  .ms-actions button {
    padding: 2px 4px;
    font-size: 0.72rem;
    font-family: inherit;
    color: var(--text-muted);
    background: none;
    border: none;
    cursor: pointer;
  }
  .ms-actions button:hover:not(:disabled) { color: var(--accent); }
  .ms-actions button:disabled { opacity: 0.4; cursor: not-allowed; }

  .ms-list {
    max-height: 220px;
    overflow-y: auto;
  }
  .ms-opt {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 5px 4px;
    font-size: 0.8rem;
    border-radius: var(--r-sm, 6px);
    cursor: pointer;
  }
  .ms-opt:hover { background: var(--surface-2); }
  .ms-opt-text {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .ms-empty {
    padding: 10px 4px;
    font-size: 0.78rem;
    color: var(--text-faint);
    text-align: center;
  }
  .ms-foot {
    padding-top: 6px;
    margin-top: 4px;
    font-size: 0.72rem;
    color: var(--text-muted);
    border-top: 1px solid var(--border);
  }
</style>
