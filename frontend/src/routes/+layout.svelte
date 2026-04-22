<script lang="ts">
  import '../app.css';
  import Header from '$lib/components/Header.svelte';
  import Footer from '$lib/components/Footer.svelte';
  import { auth } from '$lib/stores/auth.svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';

  let { children } = $props();

  $effect(() => {
    const path = $page.url.pathname;
    if (!auth.isAuthenticated && path !== '/login') {
      goto('/login');
    }
  });
</script>

{#if auth.isAuthenticated}
  <Header currentPage={$page.url.pathname} />
  <main style="padding-top:60px;padding-bottom:48px;padding-left:24px;padding-right:24px;max-width:1920px;margin:0 auto;background:var(--surface);min-height:100vh;">
    {@render children()}
  </main>
  <Footer pipeline="IDLE" branches={0} jobs={0} />
{:else}
  {@render children()}
{/if}
