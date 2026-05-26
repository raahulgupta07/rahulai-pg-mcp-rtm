<script lang="ts">
  let { label = "", value = "", subtitle = "", accent = "", icon = "" } = $props();
</script>

<div class="kpi">
  <div class="kpi-top">
    <span class="kpi-label">{label}</span>
    {#if icon}
      <span class="material-symbols-outlined kpi-icon">{icon}</span>
    {/if}
  </div>
  <div class="kpi-value" style={accent ? `color:${accent}` : ''}>{value}</div>
  {#if subtitle}
    <div class="kpi-sub">{subtitle}</div>
  {/if}
</div>

<style>
  .kpi-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .kpi-icon {
    font-size: 18px;
    color: var(--text-faint);
  }
</style>
