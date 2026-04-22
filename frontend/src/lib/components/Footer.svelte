<script lang="ts">
  let { pipeline = "IDLE", branches = 0, jobs = 0 } = $props();
</script>

<footer
  class="fixed bottom-0 left-0 right-0 z-50 flex items-stretch"
  style="
    background: #feffd6;
    border-top: 3px solid #383832;
    height: 40px;
    font-family: 'Space Grotesk', monospace;
  "
>
  <!-- SYS_OK -->
  <div
    class="flex items-center px-3 font-bold uppercase tracking-widest"
    style="
      background: #007518;
      color: white;
      font-size: 11px;
      border-right: 2px solid #383832;
    "
  >
    SYS_OK
  </div>

  <!-- PIPELINE -->
  <div
    class="flex items-center px-3 font-bold uppercase tracking-widest"
    style="
      font-size: 11px;
      color: #383832;
      border-right: 2px solid #383832;
    "
  >
    PIPELINE: {pipeline}
  </div>

  <!-- BRANCHES -->
  <div
    class="flex items-center px-3 font-bold uppercase tracking-widest"
    style="
      font-size: 11px;
      color: #383832;
      border-right: 2px solid #383832;
    "
  >
    BRANCHES: {branches}
  </div>

  <!-- MODEL -->
  <div
    class="flex items-center px-3 font-bold uppercase tracking-widest"
    style="
      font-size: 11px;
      color: #383832;
    "
  >
    MODEL: HAIKU
  </div>
</footer>
