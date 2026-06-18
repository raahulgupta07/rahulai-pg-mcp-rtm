<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  // Analytics merged into the Ops Cockpit — redirect for old links/bookmarks.
  onMount(() => goto('/cockpit', { replaceState: true }));
</script>

<p style="padding:2rem;color:var(--text-muted);">Redirecting to the Cockpit…</p>
