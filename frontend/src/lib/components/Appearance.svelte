<script lang="ts">
  import {
    appearance, PALETTES, setAppearance, quadFor, resolveMode,
    type Mode, type DensityKey,
  } from '$lib/theme';

  let { open = false, onclose = () => {} } = $props();

  const modes: { id: Mode; label: string; icon: string }[] = [
    { id: 'light', label: 'Light', icon: 'light_mode' },
    { id: 'dark',  label: 'Dark',  icon: 'dark_mode' },
    { id: 'auto',  label: 'Auto',  icon: 'contrast' },
  ];
  const densities: { id: DensityKey; label: string }[] = [
    { id: 'comfortable', label: 'Comfortable' },
    { id: 'compact',     label: 'Compact' },
  ];

  // Swatch colour for each palette, resolved to the current mode
  let darkMode = $derived(resolveMode($appearance.mode) === 'dark');

  function swatchColor(skin: string): string {
    return quadFor({ ...$appearance, skin }, darkMode).accent;
  }

  function onBackdrop(e: MouseEvent) {
    if (e.target === e.currentTarget) onclose();
  }
  function onKey(e: KeyboardEvent) {
    if (e.key === 'Escape') onclose();
  }
</script>

<svelte:window onkeydown={onKey} />

{#if open}
  <div class="modal-backdrop" onclick={onBackdrop} role="presentation">
    <div class="modal appearance-modal animate-fade-up" role="dialog" aria-label="Appearance settings">
      <div class="ap-head">
        <div>
          <h3>Appearance</h3>
          <div class="ap-sub">Personalize the interface — saved to your account</div>
        </div>
        <button class="ap-x" onclick={onclose} aria-label="Close">
          <span class="material-symbols-outlined">close</span>
        </button>
      </div>

      <!-- Mode -->
      <div class="ap-section">
        <div class="ap-label">Mode</div>
        <div class="segmented">
          {#each modes as m}
            <button
              class="seg"
              class:active={$appearance.mode === m.id}
              onclick={() => setAppearance({ mode: m.id })}
            >
              <span class="material-symbols-outlined">{m.icon}</span>
              {m.label}
            </button>
          {/each}
        </div>
      </div>

      <!-- Palette -->
      <div class="ap-section">
        <div class="ap-label">Palette</div>
        <div class="swatches">
          {#each PALETTES as p}
            <button
              class="swatch"
              class:active={$appearance.skin === p.id}
              onclick={() => setAppearance({ skin: p.id })}
              title={p.name}
            >
              <span class="dot" style="background:{swatchColor(p.id)}"></span>
              <span class="sw-name">{p.name}</span>
            </button>
          {/each}
          <button
            class="swatch"
            class:active={$appearance.skin === 'custom'}
            onclick={() => setAppearance({ skin: 'custom' })}
            title="Custom"
          >
            <span class="dot custom-dot" style="background:{$appearance.customAccent}"></span>
            <span class="sw-name">Custom</span>
          </button>
        </div>

        {#if $appearance.skin === 'custom'}
          <div class="custom-row animate-fade-in">
            <label class="custom-pick">
              <input
                type="color"
                value={$appearance.customAccent}
                oninput={(e) => setAppearance({ customAccent: e.currentTarget.value })}
              />
              <span>Accent colour</span>
            </label>
            <code class="hex">{$appearance.customAccent.toUpperCase()}</code>
          </div>
        {/if}
      </div>

      <!-- Density -->
      <div class="ap-section">
        <div class="ap-label">Density</div>
        <div class="segmented">
          {#each densities as d}
            <button
              class="seg"
              class:active={$appearance.density === d.id}
              onclick={() => setAppearance({ density: d.id })}
            >{d.label}</button>
          {/each}
        </div>
      </div>

      <!-- Preview -->
      <div class="ap-section">
        <div class="ap-label">Preview</div>
        <div class="preview card">
          <div class="pv-row">
            <span class="badge badge-a">Class A</span>
            <span class="badge badge-b">Class B</span>
            <span class="badge badge-c">Class C</span>
            <span class="badge badge-f4">F4</span>
          </div>
          <div class="pv-row">
            <button class="btn btn-sm">Primary</button>
            <button class="btn-ghost btn-sm">Secondary</button>
            <span class="chip chip-accent">Accent chip</span>
          </div>
        </div>
      </div>

      <div class="ap-foot">
        <button class="btn btn-block" onclick={onclose}>Done</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .appearance-modal { max-width: 460px; }

  .ap-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    margin-bottom: 6px;
  }
  .ap-sub { font-size: 12px; color: var(--text-muted); margin-top: 2px; }
  .ap-x {
    display: inline-flex; align-items: center; justify-content: center;
    width: 32px; height: 32px;
    background: transparent; border: 1px solid var(--border);
    border-radius: var(--r-md); color: var(--text-muted);
  }
  .ap-x:hover { background: var(--surface-2); color: var(--text); }
  .ap-x .material-symbols-outlined { font-size: 18px; }

  .ap-section { margin-top: 16px; }
  .ap-label {
    font-size: 12px; font-weight: 600;
    color: var(--text-muted); margin-bottom: 7px;
  }

  /* Segmented control */
  .segmented {
    display: flex;
    gap: 4px;
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    padding: 3px;
  }
  .seg {
    flex: 1;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 5px;
    padding: 7px 8px;
    background: transparent;
    border: none;
    border-radius: var(--r-sm);
    color: var(--text-muted);
    font-size: 13px;
    font-weight: 500;
    transition: background-color 0.15s, color 0.15s;
  }
  .seg:hover { color: var(--text); }
  .seg.active {
    background: var(--surface);
    color: var(--text);
    font-weight: 600;
    box-shadow: var(--shadow-sm);
  }
  .seg .material-symbols-outlined { font-size: 16px; }

  /* Palette swatches */
  .swatches {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
  }
  .swatch {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 9px 11px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    color: var(--text);
    font-size: 13px;
    transition: border-color 0.15s, background-color 0.15s;
  }
  .swatch:hover { border-color: var(--border-strong); }
  .swatch.active {
    border-color: var(--accent);
    background: var(--accent-soft);
    color: var(--accent-ink);
  }
  .swatch .dot {
    width: 16px; height: 16px;
    border-radius: var(--r-pill);
    flex-shrink: 0;
    box-shadow: inset 0 0 0 1px rgba(0,0,0,0.12);
  }
  .custom-dot { background-image: conic-gradient(red, yellow, lime, aqua, blue, magenta, red); }
  .sw-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

  .custom-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-top: 10px;
    padding: 10px 12px;
    background: var(--surface-2);
    border-radius: var(--r-md);
  }
  .custom-pick {
    display: flex;
    align-items: center;
    gap: 9px;
    font-size: 13px;
    color: var(--text);
  }
  .custom-pick input[type="color"] {
    width: 34px; height: 34px;
    padding: 0;
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    background: none;
    cursor: pointer;
  }
  .hex {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--text-muted);
  }

  .preview { padding: 14px; display: flex; flex-direction: column; gap: 10px; }
  .pv-row { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }

  .ap-foot { margin-top: 20px; }

  @media (max-width: 420px) {
    .swatches { grid-template-columns: repeat(2, 1fr); }
  }
</style>
