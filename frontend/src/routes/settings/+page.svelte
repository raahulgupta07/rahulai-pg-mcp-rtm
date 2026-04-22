<script lang="ts">
  import { getSettings, saveSettings } from '$lib/api';
  import ChapterHeading from '$lib/components/ChapterHeading.svelte';

  let settings = $state<any>(null);
  let loading = $state(true);
  let error = $state('');
  let thresholdA = $state(80);
  let thresholdB = $state(95);
  let saving = $state(false);
  let saveMsg = $state('');

  $effect(() => {
    getSettings()
      .then(s => {
        settings = s;
        thresholdA = s.default_threshold_a || 80;
        thresholdB = s.default_threshold_b || 95;
        loading = false;
      })
      .catch(e => { error = e.message; loading = false; });
  });
</script>

<svelte:head>
  <title>SETTINGS — MCP AGENT</title>
</svelte:head>

<!-- Hero -->
<div style="background:#383832;color:#feffd6;padding:16px 24px;margin-bottom:24px;border-bottom:4px solid #383832;border-right:4px solid #383832;">
  <div style="font-size:1.5rem;font-weight:900;letter-spacing:-0.03em;font-family:'Space Grotesk',sans-serif;">SYSTEM CONFIGURATION</div>
  <div style="font-size:11px;opacity:0.75;margin-top:4px;font-family:'Space Grotesk',sans-serif;">MCP AGENT SETTINGS & STATUS</div>
</div>

{#if loading}
  <!-- Loading skeleton -->
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:24px;padding:0 24px 24px;">
    {#each [1, 2] as _}
      <div style="
        background:#f5f5ee;
        border-top:2px solid #383832;border-left:2px solid #383832;
        border-bottom:4px solid #383832;border-right:4px solid #383832;
        box-shadow:4px 4px 0px 383832;
        min-height:280px;
        animation:pulse 1.5s ease-in-out infinite;
      ">
        <div style="background:#383832;height:36px;"></div>
        <div style="padding:20px;">
          {#each [1, 2, 3, 4] as __}
            <div style="background:#e0e0d8;height:16px;margin-bottom:16px;width:{60 + Math.random() * 30}%;"></div>
          {/each}
        </div>
      </div>
    {/each}
  </div>
  <div style="padding:0 24px 24px;">
    <div style="
      background:#f5f5ee;
      border-top:2px solid #383832;border-left:2px solid #383832;
      border-bottom:4px solid #383832;border-right:4px solid #383832;
      box-shadow:4px 4px 0px #383832;
      min-height:100px;
      animation:pulse 1.5s ease-in-out infinite;
    ">
      <div style="background:#383832;height:36px;"></div>
      <div style="padding:20px;">
        <div style="background:#e0e0d8;height:16px;margin-bottom:12px;width:70%;"></div>
        <div style="background:#e0e0d8;height:16px;width:50%;"></div>
      </div>
    </div>
  </div>

{:else if error}
  <!-- Error state -->
  <div style="margin:0 24px;padding:20px;background:#fff0f0;border-top:2px solid #be2d06;border-left:2px solid #be2d06;border-bottom:4px solid #be2d06;border-right:4px solid #be2d06;box-shadow:4px 4px 0px #be2d06;font-family:'Space Grotesk',sans-serif;">
    <div style="font-weight:900;font-size:14px;color:#be2d06;text-transform:uppercase;margin-bottom:8px;">FAILED TO LOAD SETTINGS</div>
    <div style="font-size:13px;color:#383832;font-family:monospace;">{error}</div>
  </div>

{:else if settings}
  <!-- Two-column grid -->
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:24px;padding:0 24px 24px;font-family:'Space Grotesk',sans-serif;">

    <!-- Left card: LLM PROVIDER -->
    <div style="
      background:#feffd6;
      border-top:2px solid #383832;border-left:2px solid #383832;
      border-bottom:4px solid #383832;border-right:4px solid #383832;
      box-shadow:4px 4px 0px #383832;
    ">
      <!-- Dark bar title -->
      <div style="background:#383832;color:#feffd6;padding:10px 16px;font-weight:900;font-size:12px;letter-spacing:0.05em;text-transform:uppercase;">
        <span style="color:#ff9d00;margin-right:8px;">&#x25C6;</span>LLM PROVIDER
      </div>

      <div style="padding:20px;">
        <!-- MODEL -->
        <div style="margin-bottom:16px;">
          <div style="font-size:10px;font-weight:900;text-transform:uppercase;color:#383832;opacity:0.6;margin-bottom:4px;letter-spacing:0.05em;">MODEL</div>
          <div style="
            background:#f5f5ee;padding:8px 12px;font-family:monospace;font-size:13px;color:#383832;
            border:2px solid #383832;
          ">{settings.model}</div>
        </div>

        <!-- API KEY -->
        <div style="margin-bottom:16px;">
          <div style="font-size:10px;font-weight:900;text-transform:uppercase;color:#383832;opacity:0.6;margin-bottom:4px;letter-spacing:0.05em;">API KEY</div>
          {#if settings.api_configured}
            <span style="
              display:inline-block;padding:4px 10px;font-size:11px;font-weight:900;text-transform:uppercase;
              background:#007518;color:#feffd6;letter-spacing:0.05em;
            ">CONFIGURED</span>
          {:else}
            <span style="
              display:inline-block;padding:4px 10px;font-size:11px;font-weight:900;text-transform:uppercase;
              background:#be2d06;color:#feffd6;letter-spacing:0.05em;
            ">NOT SET</span>
          {/if}
        </div>

        <!-- BASE URL -->
        <div style="margin-bottom:20px;">
          <div style="font-size:10px;font-weight:900;text-transform:uppercase;color:#383832;opacity:0.6;margin-bottom:4px;letter-spacing:0.05em;">BASE URL</div>
          <div style="
            background:#f5f5ee;padding:8px 12px;font-family:monospace;font-size:12px;color:#383832;
            border:2px solid #383832;word-break:break-all;
          ">{settings.base_url}</div>
        </div>

        <!-- Divider -->
        <div style="border-top:2px solid #383832;margin-bottom:16px;"></div>

        <!-- PARETO DEFAULTS -->
        <div style="font-size:10px;font-weight:900;text-transform:uppercase;color:#383832;opacity:0.6;margin-bottom:12px;letter-spacing:0.05em;">PARETO DEFAULTS</div>

        <div style="display:flex;gap:24px;margin-bottom:16px;">
          <div style="flex:1;">
            <label style="font-size:10px;font-weight:900;text-transform:uppercase;color:#383832;display:block;margin-bottom:4px;letter-spacing:0.05em;">
              CLASS A CUTOFF: <span style="color:#007518;">{thresholdA}%</span>
            </label>
            <input type="range" min="50" max="95" bind:value={thresholdA}
              style="width:100%;accent-color:#007518;cursor:pointer;" />
          </div>
          <div style="flex:1;">
            <label style="font-size:10px;font-weight:900;text-transform:uppercase;color:#383832;display:block;margin-bottom:4px;letter-spacing:0.05em;">
              CLASS B CUTOFF: <span style="color:#ff9d00;">{thresholdB}%</span>
            </label>
            <input type="range" min={thresholdA + 1} max="99" bind:value={thresholdB}
              style="width:100%;accent-color:#ff9d00;cursor:pointer;" />
          </div>
        </div>

        {#if saveMsg}
          <div style="margin-bottom:12px;font-size:11px;font-weight:700;color:#007518;">{saveMsg}</div>
        {/if}

        <button
          onclick={async () => {
            saving = true;
            saveMsg = '';
            try {
              await saveSettings({ threshold_a: thresholdA, threshold_b: thresholdB });
              saveMsg = 'THRESHOLDS SAVED';
              if (settings) {
                settings.default_threshold_a = thresholdA;
                settings.default_threshold_b = thresholdB;
              }
            } catch (e) {
              saveMsg = 'SAVE FAILED';
            }
            saving = false;
          }}
          disabled={saving}
          style="width:100%;padding:10px;font-size:11px;font-weight:900;letter-spacing:0.1em;text-transform:uppercase;cursor:pointer;border:2px solid #383832;box-shadow:3px 3px 0 #383832;background:#00fc40;color:#383832;"
        >
          {saving ? 'SAVING...' : 'SAVE THRESHOLDS'}
        </button>
      </div>
    </div>

    <!-- Right card: API STATUS -->
    <div style="
      background:#feffd6;
      border-top:2px solid #383832;border-left:2px solid #383832;
      border-bottom:4px solid #383832;border-right:4px solid #383832;
      box-shadow:4px 4px 0px #383832;
    ">
      <!-- Dark bar title -->
      <div style="background:#383832;color:#feffd6;padding:10px 16px;font-weight:900;font-size:12px;letter-spacing:0.05em;text-transform:uppercase;">
        <span style="color:#ff9d00;margin-right:8px;">&#x25C6;</span>SYSTEM STATUS
      </div>

      <div style="padding:20px;">
        <!-- STATUS -->
        <div style="margin-bottom:16px;display:flex;justify-content:space-between;align-items:center;">
          <div style="font-size:10px;font-weight:900;text-transform:uppercase;color:#383832;opacity:0.6;letter-spacing:0.05em;">STATUS</div>
          <span style="
            display:inline-block;padding:4px 10px;font-size:11px;font-weight:900;text-transform:uppercase;
            background:#007518;color:#feffd6;letter-spacing:0.05em;
          ">ONLINE</span>
        </div>

        <!-- MODEL -->
        <div style="margin-bottom:16px;display:flex;justify-content:space-between;align-items:center;">
          <div style="font-size:10px;font-weight:900;text-transform:uppercase;color:#383832;opacity:0.6;letter-spacing:0.05em;">MODEL</div>
          <div style="font-family:monospace;font-size:13px;color:#383832;font-weight:700;">{settings.model}</div>
        </div>

        <!-- PIPELINE -->
        <div style="margin-bottom:16px;display:flex;justify-content:space-between;align-items:center;">
          <div style="font-size:10px;font-weight:900;text-transform:uppercase;color:#383832;opacity:0.6;letter-spacing:0.05em;">PIPELINE</div>
          <div style="font-family:monospace;font-size:13px;color:#383832;font-weight:700;">IDLE</div>
        </div>

        <!-- DATABASE -->
        <div style="margin-bottom:16px;display:flex;justify-content:space-between;align-items:center;">
          <div style="font-size:10px;font-weight:900;text-transform:uppercase;color:#383832;opacity:0.6;letter-spacing:0.05em;">DATABASE</div>
          <span style="
            display:inline-block;padding:4px 10px;font-size:11px;font-weight:900;text-transform:uppercase;
            background:#007518;color:#feffd6;letter-spacing:0.05em;
          ">CONNECTED</span>
        </div>

        <!-- TOTAL JOBS -->
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <div style="font-size:10px;font-weight:900;text-transform:uppercase;color:#383832;opacity:0.6;letter-spacing:0.05em;">TOTAL JOBS</div>
          <div style="font-size:1.5rem;font-weight:900;color:#007518;">{settings.total_jobs}</div>
        </div>
      </div>
    </div>
  </div>

  <!-- Bottom card: ABOUT (full width) -->
  <div style="margin:0 24px 24px;font-family:'Space Grotesk',sans-serif;">
    <div style="
      background:#feffd6;
      border-top:2px solid #383832;border-left:2px solid #383832;
      border-bottom:4px solid #383832;border-right:4px solid #383832;
      box-shadow:4px 4px 0px #383832;
    ">
      <!-- Dark bar title -->
      <div style="background:#383832;color:#feffd6;padding:10px 16px;font-weight:900;font-size:12px;letter-spacing:0.05em;text-transform:uppercase;">
        <span style="color:#ff9d00;margin-right:8px;">&#x25C6;</span>ABOUT
      </div>

      <div style="padding:20px;">
        <div style="font-weight:900;font-size:18px;color:#383832;margin-bottom:8px;letter-spacing:-0.02em;">MCP AGENT V{settings.version}</div>
        <div style="font-size:13px;color:#383832;margin-bottom:4px;">P&G Route-to-Market Outlet Classification</div>
        <div style="font-size:13px;color:#383832;margin-bottom:4px;">Built by <span style="font-weight:900;">{settings.team}</span> — {settings.org}</div>
        <div style="font-size:13px;color:#383832;">Powered by <span style="font-weight:700;font-family:monospace;">{settings.model}</span> via OpenRouter</div>
      </div>
    </div>
  </div>
{/if}

<style>
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }
</style>
