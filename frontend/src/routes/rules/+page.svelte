<script lang="ts">
  import { onMount } from 'svelte';
  import { auth } from '$lib/stores/auth.svelte';

  interface RuleConfig {
    pareto: { class_a_cutoff: number; class_b_cutoff: number };
    wholesaler: { enabled: boolean; cartons_per_brand_month: number; item_type: string };
    category_override: { enabled: boolean; contribution_cutoff: number };
    frequency: { class_a_tier: string; other_tier: string };
    workload: { yangon_min: number; yangon_max: number; regional_min: number; regional_max: number };
    growth: { growing_pct: number; declining_pct: number };
    risk: {
      freq_medium_days: number; freq_high_days: number; low_purchase_days: number;
      signals_for_high: number; signals_for_medium: number;
    };
    ai: { llm_enabled: boolean; temperature: number; enrich_top_n: number };
  }

  let cfg = $state<RuleConfig | null>(null);
  let loading = $state(true);
  let saving = $state(false);
  let error = $state('');
  let saveMsg = $state('');

  const readOnly = !auth.hasPerm('rules');

  async function load() {
    loading = true;
    error = '';
    try {
      const res = await fetch('/api/rule-config', { headers: auth.getHeaders() });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      cfg = await res.json();
    } catch {
      error = 'Could not load rule config.';
    } finally {
      loading = false;
    }
  }

  async function post(body: any, okMsg: string) {
    saving = true;
    error = '';
    saveMsg = '';
    try {
      const res = await fetch('/api/rule-config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...auth.getHeaders() },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      cfg = data.config;
      saveMsg = okMsg;
      setTimeout(() => saveMsg = '', 3500);
    } catch {
      error = 'Request failed. Check your connection and permissions.';
    } finally {
      saving = false;
    }
  }

  const save = () => cfg && post(cfg, 'Saved — applies to the next classification run');
  function resetDefaults() {
    if (!confirm('Reset all classification rules to factory defaults?')) return;
    post({}, 'Reset to factory defaults');
  }

  let cutoffWarn = $derived(cfg ? cfg.pareto.class_b_cutoff <= cfg.pareto.class_a_cutoff : false);

  // ── Change history + rollback ──
  let historyOpen = $state(false);
  let history = $state<any[]>([]);
  let historyLoading = $state(false);

  async function openHistory() {
    historyOpen = true;
    historyLoading = true;
    try {
      const res = await fetch('/api/rule-config/history', { headers: auth.getHeaders() });
      history = res.ok ? await res.json() : [];
    } catch {
      history = [];
    } finally {
      historyLoading = false;
    }
  }

  async function rollback(versionId: number) {
    if (!confirm(`Roll back the classification rules to version v${versionId}?`)) return;
    saving = true;
    error = '';
    try {
      const res = await fetch(`/api/rule-config/rollback/${versionId}`, {
        method: 'POST', headers: auth.getHeaders(),
      });
      if (!res.ok) throw new Error();
      const data = await res.json();
      cfg = data.config;
      saveMsg = `Rolled back to v${versionId}`;
      setTimeout(() => saveMsg = '', 3500);
      historyOpen = false;
    } catch {
      error = 'Rollback failed.';
    } finally {
      saving = false;
    }
  }

  function fmtTime(ts: string): string {
    try { return new Date(ts).toLocaleString(); } catch { return ts; }
  }

  onMount(load);
</script>

<div class="page animate-fade-in">
  <header class="page-head">
    <div>
      <h1>Classification Rules</h1>
      <p>Every parameter the classification engine and AI enrichment use — tune it, save, then run
         a new job. Each rule explains how it works and what changing it does.</p>
    </div>
    {#if !loading && cfg && !readOnly}
      <div class="head-actions">
        <button class="btn-ghost btn-sm" onclick={openHistory}>
          <span class="material-symbols-outlined" style="font-size:16px;">history</span>
          History
        </button>
        <button class="btn-ghost btn-sm" onclick={resetDefaults} disabled={saving}>Reset defaults</button>
        <button class="btn btn-sm" onclick={save} disabled={saving}>
          {saving ? 'Saving…' : 'Save changes'}
        </button>
      </div>
    {/if}
  </header>

  {#if saveMsg}
    <div class="alert alert-success" style="margin-bottom:14px;">
      <span class="material-symbols-outlined" style="font-size:18px;">check_circle</span>
      {saveMsg}
    </div>
  {/if}
  {#if error}
    <div class="alert alert-danger" style="margin-bottom:14px;">{error}</div>
  {/if}
  {#if readOnly && !loading}
    <div class="alert alert-info" style="margin-bottom:14px;">
      <span class="material-symbols-outlined" style="font-size:18px;">lock</span>
      Read-only — only administrators can change classification rules.
    </div>
  {/if}

  {#if loading}
    <div class="card"><div class="skeleton" style="height:280px;"></div></div>
  {:else if cfg}

    <!-- ════ SECTION 1 — CLASSIFICATION ENGINE ════ -->
    <div class="section-head">
      <span class="dot"></span>
      <div>
        <h2>Classification Engine</h2>
        <div class="section-sub">Rules that decide each outlet's class — A / B / C / F4</div>
      </div>
    </div>

    <div class="rule-grid">

      <!-- Pareto -->
      <section class="card">
        <div class="rule-head">
          <span class="material-symbols-outlined">percent</span>
          <div>
            <h3>Pareto Cutoffs</h3>
            <div class="rule-sub">Cumulative-revenue ceilings that split A / B / C</div>
          </div>
        </div>
        <div class="field-row">
          <label class="field">
            <span class="label">Class A ceiling (%)</span>
            <input class="input" type="number" min="50" max="95" disabled={readOnly}
              bind:value={cfg.pareto.class_a_cutoff} />
          </label>
          <label class="field">
            <span class="label">Class B ceiling (%)</span>
            <input class="input" type="number" min="55" max="99" disabled={readOnly}
              bind:value={cfg.pareto.class_b_cutoff} />
          </label>
        </div>
        {#if cutoffWarn}
          <div class="inline-warn">Class B ceiling must be greater than Class A ceiling.</div>
        {/if}
        <div class="preview-line">
          A ≤ {cfg.pareto.class_a_cutoff}% &nbsp;·&nbsp;
          B {cfg.pareto.class_a_cutoff}–{cfg.pareto.class_b_cutoff}% &nbsp;·&nbsp;
          C &gt; {cfg.pareto.class_b_cutoff}%
        </div>
        <div class="explain">
          <div class="explain-title">How it works &amp; impact</div>
          <div class="explain-body">
            <p><strong>How it works.</strong> Within each branch, outlets are ranked by 2-year
              revenue, highest first. A running cumulative-% of branch revenue is computed. Outlets
              under the Class A ceiling are Class A; those between the two ceilings are Class B;
              the rest are Class C.</p>
            <p><strong>Impact.</strong> A <em>lower</em> Class A ceiling gives a smaller, more elite
              priority tier — fewer outlets get costly frequent visits. <em>Raising</em> it widens
              the priority tier and field cost. The Class B ceiling sets where the low-value long
              tail (Class C) begins.</p>
          </div>
        </div>
      </section>

      <!-- Wholesaler -->
      <section class="card">
        <div class="rule-head">
          <span class="material-symbols-outlined">inventory_2</span>
          <div>
            <h3>Wholesaler (F4)</h3>
            <div class="rule-sub">Bulk-buyer auto-classification to Class A</div>
          </div>
          <label class="switch">
            <input type="checkbox" disabled={readOnly} bind:checked={cfg.wholesaler.enabled} />
            <span>Enabled</span>
          </label>
        </div>
        <div class="field-row">
          <label class="field">
            <span class="label">Cartons / brand / month</span>
            <input class="input" type="number" min="1" max="50" disabled={readOnly || !cfg.wholesaler.enabled}
              bind:value={cfg.wholesaler.cartons_per_brand_month} />
          </label>
          <label class="field">
            <span class="label">Item type</span>
            <select class="select" disabled={readOnly || !cfg.wholesaler.enabled}
              bind:value={cfg.wholesaler.item_type}>
              <option value="Local">Local</option>
              <option value="Import">Import</option>
            </select>
          </label>
        </div>
        <div class="explain">
          <div class="explain-title">How it works &amp; impact</div>
          <div class="explain-body">
            <p><strong>How it works.</strong> Monthly cartons per brand = pieces ÷ units-per-carton.
              If an outlet hits the carton threshold for any brand in any month (on the chosen item
              type), it is flagged a wholesaler and forced to <em>Class A Local (F4)</em> — no matter
              its revenue rank.</p>
            <p><strong>Impact.</strong> A <em>lower</em> carton threshold flags more outlets as
              wholesalers, growing the F4 / Class A count. <em>Disabling</em> it removes all F4
              overrides — outlets are then classed purely by Pareto.</p>
          </div>
        </div>
      </section>

      <!-- Category override -->
      <section class="card">
        <div class="rule-head">
          <span class="material-symbols-outlined">category</span>
          <div>
            <h3>Category Override</h3>
            <div class="rule-sub">Category-dominant outlets jump to Class A</div>
          </div>
          <label class="switch">
            <input type="checkbox" disabled={readOnly} bind:checked={cfg.category_override.enabled} />
            <span>Enabled</span>
          </label>
        </div>
        <div class="field-row">
          <label class="field">
            <span class="label">Contribution cutoff (%)</span>
            <input class="input" type="number" min="50" max="100" disabled={readOnly || !cfg.category_override.enabled}
              bind:value={cfg.category_override.contribution_cutoff} />
          </label>
        </div>
        <div class="explain">
          <div class="explain-title">How it works &amp; impact</div>
          <div class="explain-body">
            <p><strong>How it works.</strong> After Pareto runs, if an outlet's share of a single
              category (Nutrition, Food, or Non-Food) within its branch reaches the cutoff, it is
              promoted to <em>Class A {'{'}category{'}'}</em> even if its overall revenue is modest.</p>
            <p><strong>Impact.</strong> A <em>lower</em> cutoff promotes more category leaders into
              Class A. A <em>high</em> cutoff (e.g. 90%) promotes only true category dominators.
              <em>Disabling</em> it leaves revenue rank and the wholesaler rule as the only routes
              into Class A.</p>
          </div>
        </div>
      </section>

      <!-- Frequency tiers -->
      <section class="card">
        <div class="rule-head">
          <span class="material-symbols-outlined">event_repeat</span>
          <div>
            <h3>Visit Frequency Tiers</h3>
            <div class="rule-sub">Tier label assigned by classification</div>
          </div>
        </div>
        <div class="field-row">
          <label class="field">
            <span class="label">Class A tier</span>
            <input class="input" type="text" disabled={readOnly} bind:value={cfg.frequency.class_a_tier} />
          </label>
          <label class="field">
            <span class="label">Other classes tier</span>
            <input class="input" type="text" disabled={readOnly} bind:value={cfg.frequency.other_tier} />
          </label>
        </div>
        <div class="explain">
          <div class="explain-title">How it works &amp; impact</div>
          <div class="explain-body">
            <p><strong>How it works.</strong> Every outlet gets a visit-frequency label derived from
              its class — Class A outlets receive one tier code, all other classes another. The
              label feeds route planning and the exported reports.</p>
            <p><strong>Impact.</strong> This only re-labels — it does <em>not</em> change which class
              an outlet is in. Set the codes to match your field team's scheme (e.g. F4 = four
              visits per cycle, F2 = two).</p>
          </div>
        </div>
      </section>

      <!-- Workload -->
      <section class="card wide">
        <div class="rule-head">
          <span class="material-symbols-outlined">groups</span>
          <div>
            <h3>Seller Workload Targets</h3>
            <div class="rule-sub">Outlets-per-route min / max by region</div>
          </div>
        </div>
        <div class="field-row">
          <label class="field">
            <span class="label">Yangon min</span>
            <input class="input" type="number" min="1" disabled={readOnly} bind:value={cfg.workload.yangon_min} />
          </label>
          <label class="field">
            <span class="label">Yangon max</span>
            <input class="input" type="number" min="1" disabled={readOnly} bind:value={cfg.workload.yangon_max} />
          </label>
          <label class="field">
            <span class="label">Regional min</span>
            <input class="input" type="number" min="1" disabled={readOnly} bind:value={cfg.workload.regional_min} />
          </label>
          <label class="field">
            <span class="label">Regional max</span>
            <input class="input" type="number" min="1" disabled={readOnly} bind:value={cfg.workload.regional_max} />
          </label>
        </div>
        <div class="explain">
          <div class="explain-title">How it works &amp; impact</div>
          <div class="explain-body">
            <p><strong>How it works.</strong> The engine counts unique outlets on each route per
              branch, then compares the count to the min/max band — Yangon branches use the Yangon
              band, every other branch uses the Regional band. Routes below min are flagged
              <em>BELOW</em>, above max <em>ABOVE</em>, in range <em>OK</em>.</p>
            <p><strong>Impact.</strong> Set these to your real route-capacity policy. A
              <em>tighter</em> band flags more routes as under/over-loaded. This affects the
              workload report and warnings only — it does not change outlet classification.</p>
          </div>
        </div>
      </section>

    </div>

    <!-- ════ SECTION 2 — AI ENRICHMENT ════ -->
    <div class="section-head" style="margin-top:28px;">
      <span class="dot"></span>
      <div>
        <h2>AI Enrichment</h2>
        <div class="section-sub">Per-outlet signals and LLM-generated insight added after classification</div>
      </div>
    </div>

    <div class="rule-grid">

      <!-- LLM settings -->
      <section class="card wide">
        <div class="rule-head">
          <span class="material-symbols-outlined">smart_toy</span>
          <div>
            <h3>LLM Behaviour</h3>
            <div class="rule-sub">Drives AI_Insight, executive summary, recommendations &amp; growth analysis</div>
          </div>
          <label class="switch">
            <input type="checkbox" disabled={readOnly} bind:checked={cfg.ai.llm_enabled} />
            <span>LLM enabled</span>
          </label>
        </div>
        <div class="field-row">
          <label class="field">
            <span class="label">Temperature (0–1)</span>
            <input class="input" type="number" min="0" max="1" step="0.1"
              disabled={readOnly || !cfg.ai.llm_enabled} bind:value={cfg.ai.temperature} />
          </label>
          <label class="field">
            <span class="label">Enrich top-N outlets</span>
            <input class="input" type="number" min="1" max="100"
              disabled={readOnly || !cfg.ai.llm_enabled} bind:value={cfg.ai.enrich_top_n} />
          </label>
        </div>
        <div class="explain">
          <div class="explain-title">How it works &amp; impact</div>
          <div class="explain-body">
            <p><strong>How it works.</strong> When enabled and an API key is present, the engine
              calls the LLM to write the executive summary, A/B/C recommendations, growth analysis,
              and a one-line <em>AI_Insight</em> for the top-N outlets by revenue. If disabled — or
              no key — it falls back to built-in rule-based text, so a run never fails.</p>
            <p><strong>Impact.</strong> <em>Temperature</em> near 0 gives stable, repeatable wording;
              higher is more varied. <em>Top-N</em> controls how many outlets get a personalised
              insight — higher means more LLM calls (slower, higher cost).</p>
            <p><strong>Model &amp; provider</strong> (which LLM, which API URL) are set by a
              super-admin in <em>Settings</em> — not here.</p>
          </div>
        </div>
      </section>

      <!-- Growth -->
      <section class="card">
        <div class="rule-head">
          <span class="material-symbols-outlined">trending_up</span>
          <div>
            <h3>Growth Signal</h3>
            <div class="rule-sub">Field: AI_Growth_Signal</div>
          </div>
        </div>
        <div class="field-row">
          <label class="field">
            <span class="label">Growing threshold (%)</span>
            <input class="input" type="number" min="0" max="100" disabled={readOnly}
              bind:value={cfg.growth.growing_pct} />
          </label>
          <label class="field">
            <span class="label">Declining threshold (%)</span>
            <input class="input" type="number" min="0" max="100" disabled={readOnly}
              bind:value={cfg.growth.declining_pct} />
          </label>
        </div>
        <div class="explain">
          <div class="explain-title">How it works &amp; impact</div>
          <div class="explain-body">
            <p><strong>How it works.</strong> The last 6 months of sales are compared to half of the
              12-month total (the 6-month-equivalent baseline). Above the growing threshold →
              <em>Growing</em>; below the declining threshold → <em>Declining</em>; otherwise
              <em>Stable</em>.</p>
            <p><strong>Impact.</strong> <em>Smaller</em> thresholds make the signal more sensitive —
              more outlets flagged Growing or Declining. <em>Larger</em> thresholds flag only strong
              movers. This signal feeds the Risk score and the AI action items.</p>
          </div>
        </div>
      </section>

      <!-- Risk -->
      <section class="card">
        <div class="rule-head">
          <span class="material-symbols-outlined">warning</span>
          <div>
            <h3>Risk Scoring</h3>
            <div class="rule-sub">Field: AI_Risk_Level</div>
          </div>
        </div>
        <div class="field-row">
          <label class="field">
            <span class="label">Buy-gap medium (days)</span>
            <input class="input" type="number" min="1" disabled={readOnly} bind:value={cfg.risk.freq_medium_days} />
          </label>
          <label class="field">
            <span class="label">Buy-gap high (days)</span>
            <input class="input" type="number" min="1" disabled={readOnly} bind:value={cfg.risk.freq_high_days} />
          </label>
        </div>
        <div class="field-row">
          <label class="field">
            <span class="label">Low purchase days</span>
            <input class="input" type="number" min="1" disabled={readOnly} bind:value={cfg.risk.low_purchase_days} />
          </label>
          <label class="field">
            <span class="label">Signals → High</span>
            <input class="input" type="number" min="1" max="10" disabled={readOnly} bind:value={cfg.risk.signals_for_high} />
          </label>
          <label class="field">
            <span class="label">Signals → Medium</span>
            <input class="input" type="number" min="1" max="10" disabled={readOnly} bind:value={cfg.risk.signals_for_medium} />
          </label>
        </div>
        <div class="explain">
          <div class="explain-title">How it works &amp; impact</div>
          <div class="explain-body">
            <p><strong>How it works.</strong> Each outlet accrues risk signals: a <em>Declining</em>
              growth signal adds 2; an average buy-gap over the medium-days threshold adds 1, over
              the high-days threshold adds 1 more; fewer purchase days than the low-purchase
              threshold adds 1. Total at or above the High count → <em>High</em>; at or above the
              Medium count → <em>Medium</em>; otherwise <em>Low</em>.</p>
            <p><strong>Impact.</strong> <em>Lower</em> day thresholds make signals easier to
              accumulate — more Medium/High outlets. <em>Lower</em> signal counts grade risk more
              strictly. Risk drives visit priority and AI action urgency.</p>
          </div>
        </div>
      </section>

      <!-- Derived fields (info only) -->
      <section class="card wide">
        <div class="rule-head">
          <span class="material-symbols-outlined">auto_awesome</span>
          <div>
            <h3>Derived AI Fields</h3>
            <div class="rule-sub">Computed from the rules above — no separate settings</div>
          </div>
        </div>
        <div class="derived-grid">
          <div class="derived">
            <code>AI_Visit_Priority</code>
            <p>Rank 1–4 combining classification, growth signal and risk. Class A with High/Medium
               risk = 1 (most urgent); Class C steady = 4. Tune it via the Pareto, Growth and Risk
               rules above.</p>
          </div>
          <div class="derived">
            <code>AI_Action</code>
            <p>A recommended next step per outlet (e.g. "increase visits", "monitor", "cross-sell"),
               chosen from class + growth + risk. Changes automatically as you tune those rules.</p>
          </div>
          <div class="derived">
            <code>AI_Insight</code>
            <p>A one-line LLM note for each of the top-N outlets. Controlled by the LLM Settings
               card — model, temperature and top-N. Empty when the LLM is disabled.</p>
          </div>
        </div>
      </section>

    </div>

    {#if !readOnly}
      <div class="foot-bar">
        <button class="btn-ghost" onclick={resetDefaults} disabled={saving}>Reset defaults</button>
        <button class="btn" onclick={save} disabled={saving}>
          {saving ? 'Saving…' : 'Save changes'}
        </button>
      </div>
    {/if}
  {/if}

  {#if historyOpen}
    <div class="modal-backdrop" onclick={(e) => { if (e.target === e.currentTarget) historyOpen = false; }} role="presentation">
      <div class="modal animate-fade-up" role="dialog" aria-label="Rule change history">
        <div class="hist-head">
          <div>
            <h3>Rule Change History</h3>
            <div class="section-sub">Every save is versioned — restore any previous version</div>
          </div>
          <button class="hist-x" onclick={() => historyOpen = false} aria-label="Close">
            <span class="material-symbols-outlined">close</span>
          </button>
        </div>
        {#if historyLoading}
          <div class="skeleton" style="height:160px;"></div>
        {:else if history.length === 0}
          <p class="text-muted" style="font-size:13px;">
            No saved versions yet — saving the rules creates the first version.
          </p>
        {:else}
          <div class="hist-list">
            {#each history as v, i}
              <div class="hist-row">
                <div class="hist-info">
                  <div class="hist-v">
                    v{v.id}
                    {#if i === 0}<span class="hist-cur">current</span>{/if}
                  </div>
                  <div class="hist-meta">{fmtTime(v.timestamp)} · {v.username || '—'}</div>
                  {#if v.note}<div class="hist-note">{v.note}</div>{/if}
                </div>
                {#if i !== 0 && !readOnly}
                  <button class="btn-ghost btn-sm" onclick={() => rollback(v.id)} disabled={saving}>
                    Restore
                  </button>
                {/if}
              </div>
            {/each}
          </div>
        {/if}
      </div>
    </div>
  {/if}
</div>

<style>
  .page { max-width: 1100px; margin: 0 auto; }

  .page-head {
    display: flex;
    align-items: flex-start;
    gap: 14px;
    margin-bottom: 18px;
  }
  .page-head > div:first-child { flex: 1; }
  .page-head h1 { font-size: 24px; }
  .page-head p { margin: 4px 0 0; font-size: 14px; color: var(--text-muted); max-width: 620px; line-height: 1.55; }
  .head-actions { display: flex; gap: 8px; flex-shrink: 0; }

  .rule-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
  }
  .card.wide { grid-column: 1 / -1; }

  .rule-head {
    display: flex;
    align-items: center;
    gap: 11px;
    margin-bottom: 14px;
  }
  .rule-head h3 { font-size: 15px; }
  .rule-head > .material-symbols-outlined {
    font-size: 22px;
    color: var(--accent);
    background: var(--accent-soft);
    padding: 7px;
    border-radius: var(--r-md);
  }
  .rule-head > div { flex: 1; min-width: 0; }
  .rule-sub { font-size: 12px; color: var(--text-muted); margin-top: 1px; }

  .field-row {
    display: flex;
    gap: 12px;
    margin-bottom: 10px;
  }
  .field-row:last-of-type { margin-bottom: 0; }
  .field { flex: 1; display: block; min-width: 0; }
  .field .label { display: block; margin-bottom: 5px; }

  .switch {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted);
    flex-shrink: 0;
  }
  .switch input { width: 15px; height: 15px; accent-color: var(--accent); cursor: pointer; }

  .preview-line {
    margin-top: 10px;
    padding: 8px 11px;
    background: var(--surface-2);
    border-radius: var(--r-md);
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--text-muted);
  }
  .inline-warn {
    margin-top: 8px;
    font-size: 12px;
    color: var(--danger);
    font-weight: 500;
  }

  /* Explanation panel — always visible */
  .explain { margin-top: 12px; }
  .explain-title {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 12px;
    font-weight: 600;
    color: var(--accent);
    margin-bottom: 8px;
  }
  .explain-title::before {
    content: 'info';
    font-family: 'Material Symbols Outlined';
    font-size: 15px;
    font-weight: 400;
  }
  .explain-body {
    padding: 11px 13px;
    background: var(--surface-2);
    border-radius: var(--r-md);
    border-left: 3px solid var(--accent);
  }
  .explain-body p {
    margin: 0 0 8px;
    font-size: 12.5px;
    line-height: 1.6;
    color: var(--text-muted);
  }
  .explain-body p:last-child { margin-bottom: 0; }
  .explain-body strong { color: var(--text); font-weight: 600; }
  .explain-body em { font-style: normal; font-weight: 600; color: var(--text); }

  /* Derived-fields grid */
  .derived-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
  }
  .derived {
    padding: 11px 13px;
    background: var(--surface-2);
    border-radius: var(--r-md);
  }
  .derived code {
    font-family: var(--font-mono);
    font-size: 12px;
    font-weight: 600;
    color: var(--info);
  }
  .derived p {
    margin: 6px 0 0;
    font-size: 12px;
    line-height: 1.55;
    color: var(--text-muted);
  }

  .foot-bar {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    margin-top: 18px;
    padding-top: 16px;
    border-top: 1px solid var(--border);
  }

  /* Change history modal */
  .hist-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    margin-bottom: 14px;
  }
  .hist-x {
    display: inline-flex; align-items: center; justify-content: center;
    width: 32px; height: 32px;
    background: transparent; border: 1px solid var(--border);
    border-radius: var(--r-md); color: var(--text-muted);
  }
  .hist-x:hover { background: var(--surface-2); color: var(--text); }
  .hist-x .material-symbols-outlined { font-size: 18px; }
  .hist-list { display: flex; flex-direction: column; gap: 8px; max-height: 420px; overflow-y: auto; }
  .hist-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 10px 12px;
    background: var(--surface-2);
    border-radius: var(--r-md);
  }
  .hist-v { font-size: 13px; font-weight: 600; color: var(--text); display: flex; align-items: center; gap: 7px; }
  .hist-cur {
    font-size: 10px; font-weight: 600;
    background: var(--success-soft); color: var(--success);
    padding: 1px 7px; border-radius: var(--r-pill);
  }
  .hist-meta { font-size: 12px; color: var(--text-muted); margin-top: 2px; }
  .hist-note { font-size: 11.5px; color: var(--text-faint); margin-top: 1px; }

  @media (max-width: 760px) {
    .rule-grid { grid-template-columns: 1fr; }
    .page-head { flex-direction: column; }
    .derived-grid { grid-template-columns: 1fr; }
    .field-row { flex-wrap: wrap; }
  }
</style>
