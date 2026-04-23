<script lang="ts">
  let health = $state({ status: 'ok', pipeline: 'idle', model: '', jobs: 0, last_run: null as string | null, outlets: 0 });

  $effect(() => {
    fetch('/api/health').then(r => r.json()).then(d => health = d).catch(() => {});
    const interval = setInterval(() => {
      fetch('/api/health').then(r => r.json()).then(d => health = d).catch(() => {});
    }, 30000);
    return () => clearInterval(interval);
  });

  function timeAgo(dateStr: string | null): string {
    if (!dateStr) return '--';
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  }

  function shortModel(model: string): string {
    if (!model) return '--';
    const parts = model.split('/');
    const name = parts[parts.length - 1];
    if (name.includes('gemini')) return 'GEMINI';
    if (name.includes('haiku')) return 'HAIKU';
    if (name.includes('sonnet')) return 'SONNET';
    if (name.includes('opus')) return 'OPUS';
    if (name.includes('gpt')) return 'GPT';
    return name.toUpperCase().slice(0, 12);
  }
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
      background: {health.status === 'ok' ? '#007518' : '#be2d06'};
      color: white;
      font-size: 11px;
      border-right: 2px solid #383832;
    "
  >
    {health.status === 'ok' ? 'SYS_OK' : 'SYS_ERR'}
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
    PIPELINE: {(health.pipeline || 'IDLE').toUpperCase()}
  </div>

  <!-- JOBS -->
  <div
    class="flex items-center px-3 font-bold uppercase tracking-widest"
    style="
      font-size: 11px;
      color: #383832;
      border-right: 2px solid #383832;
    "
  >
    JOBS: {health.jobs}
  </div>

  <!-- LAST RUN -->
  <div
    class="flex items-center px-3 font-bold uppercase tracking-widest"
    style="
      font-size: 11px;
      color: #383832;
      border-right: 2px solid #383832;
    "
  >
    LAST: {timeAgo(health.last_run)}
  </div>

  <!-- MODEL -->
  <div
    class="flex items-center px-3 font-bold uppercase tracking-widest"
    style="
      font-size: 11px;
      color: #383832;
    "
  >
    MODEL: {shortModel(health.model)}
  </div>
</footer>
