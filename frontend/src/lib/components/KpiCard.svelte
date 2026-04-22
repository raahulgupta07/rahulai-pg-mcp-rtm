<script lang="ts">
  let { label = "", value = "", subtitle = "", accent = "#007518" } = $props();
</script>

<div
  class="flex flex-col"
  style="
    background: white;
    border-top: 2px solid #383832;
    border-left: 2px solid #383832;
    border-bottom: 4px solid #383832;
    border-right: 4px solid #383832;
    border-radius: 0;
    box-shadow: 4px 4px 0px 0px #383832;
    font-family: 'Space Grotesk', sans-serif;
  "
>
  <!-- Tag label -->
  <div
    class="px-3 py-1 font-black uppercase tracking-widest self-start"
    style="
      background: #383832;
      color: #feffd6;
      font-size: 10px;
      border-radius: 0;
    "
  >
    {label}
  </div>

  <!-- Value + subtitle -->
  <div class="px-4 py-3">
    <div
      class="font-black tracking-tighter"
      style="
        font-size: 2.25rem;
        line-height: 2.5rem;
        color: {accent};
      "
    >
      {value}
    </div>

    {#if subtitle}
      <div
        class="font-bold uppercase mt-1"
        style="
          font-size: 10px;
          opacity: 0.6;
          color: #383832;
        "
      >
        {subtitle}
      </div>
    {/if}
  </div>
</div>
