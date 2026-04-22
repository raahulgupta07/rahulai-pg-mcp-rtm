<script lang="ts">
  let { title = "", subtitle = "", question = "" } = $props();
</script>

<div style="font-family: 'Space Grotesk', sans-serif;">
  <!-- Dark bar -->
  <div
    class="flex items-center gap-3 px-4 py-3"
    style="background: #383832; color: #feffd6;"
  >
    <!-- Amber diamond -->
    <span class="text-2xl leading-none" style="color: #ff9d00;">&#x25C6;</span>

    <div>
      <div class="font-black uppercase" style="font-size: 0.875rem; letter-spacing: 0.05em;">
        {title}
      </div>
      {#if subtitle}
        <div style="font-size: 10px; opacity: 0.75;">
          {subtitle}
        </div>
      {/if}
    </div>
  </div>

  <!-- Question line -->
  {#if question}
    <div
      class="font-mono px-4 py-2"
      style="
        font-size: 0.75rem;
        color: #00fc40;
        background: #383832;
        border-top: 1px solid rgba(254, 255, 214, 0.1);
        padding-left: 3.25rem;
      "
    >
      {question}
    </div>
  {/if}
</div>
