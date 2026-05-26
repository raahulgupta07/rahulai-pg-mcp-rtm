<script lang="ts">
  let { title = "", subtitle = "", question = "" } = $props();
</script>

<div class="chapter">
  <div class="section-head">
    <span class="dot"></span>
    <div>
      <h2>{title}</h2>
      {#if subtitle}<div class="section-sub">{subtitle}</div>{/if}
    </div>
  </div>
  {#if question}
    <div class="chapter-q">
      <span class="material-symbols-outlined">help</span>
      <span>{question}</span>
    </div>
  {/if}
</div>

<style>
  .chapter { margin-bottom: 16px; }
  .chapter-q {
    display: flex;
    align-items: center;
    gap: 7px;
    margin-top: 6px;
    padding: 8px 12px;
    background: var(--surface-2);
    border-radius: var(--r-md);
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--text-muted);
  }
  .chapter-q .material-symbols-outlined { font-size: 16px; color: var(--accent); }
</style>
