<script lang="ts">
  import { auth } from '$lib/stores/auth.svelte';

  let { currentPage = "" } = $props();

  const baseNavItems = [
    { label: "CLASSIFY", href: "/" },
    { label: "HISTORY", href: "/history" },
    { label: "RTM DATA", href: "/rtm" },
    { label: "DOCS", href: "/docs" },
    { label: "SETTINGS", href: "/users" },
  ];

  let navItems = $derived(
    baseNavItems
  );

  function isActive(itemHref: string): boolean {
    if (itemHref === '/') return currentPage === '/';
    return currentPage.startsWith(itemHref);
  }

  let userInitial = $derived(
    auth.user?.display_name?.charAt(0)?.toUpperCase() ||
    auth.user?.username?.charAt(0)?.toUpperCase() ||
    '?'
  );
</script>

<header style="
  position: fixed; top: 0; left: 0; right: 0; z-index: 50;
  background: #feffd6;
  border-bottom: 3px solid #383832;
  height: 56px;
  font-family: 'Space Grotesk', sans-serif;
  display: flex; align-items: center; justify-content: space-between; padding: 0 16px;
">
  <!-- Left: Brand badge -->
  <div style="
    background: #383832; color: #00fc40;
    padding: 4px 16px; font-weight: 900; font-size: 1.25rem;
    letter-spacing: -0.5px; user-select: none;
    border: 2px solid #383832; box-shadow: 3px 3px 0 #383832;
  ">
    MCP AGENT
  </div>

  <!-- Center: Nav buttons -->
  <nav style="
    position: absolute; left: 50%; transform: translateX(-50%);
    display: flex; align-items: center; gap: 6px;
  ">
    {#each navItems as item}
      <a
        href={item.href}
        style="
          display: inline-block;
          padding: 8px 20px;
          font-size: 11px;
          font-weight: 900;
          letter-spacing: 0.1em;
          text-transform: uppercase;
          text-decoration: none;
          font-family: 'Space Grotesk', sans-serif;
          border: 2px solid #383832;
          cursor: pointer;
          transition: transform 0.1s, box-shadow 0.1s;
          {isActive(item.href)
            ? 'background: #383832; color: #feffd6; box-shadow: 3px 3px 0 #383832;'
            : 'background: #feffd6; color: #383832; box-shadow: 3px 3px 0 #383832;'}
        "
        onmouseenter={(e) => {
          if (!isActive(item.href)) {
            e.currentTarget.style.background = '#007518';
            e.currentTarget.style.color = 'white';
            e.currentTarget.style.borderColor = '#007518';
          }
        }}
        onmouseleave={(e) => {
          if (!isActive(item.href)) {
            e.currentTarget.style.background = '#feffd6';
            e.currentTarget.style.color = '#383832';
            e.currentTarget.style.borderColor = '#383832';
          }
        }}
        onmousedown={(e) => {
          e.currentTarget.style.transform = 'translate(2px, 2px)';
          e.currentTarget.style.boxShadow = '1px 1px 0 #383832';
        }}
        onmouseup={(e) => {
          e.currentTarget.style.transform = 'translate(0, 0)';
          e.currentTarget.style.boxShadow = '3px 3px 0 #383832';
        }}
      >
        {item.label}
      </a>
    {/each}
  </nav>

  <!-- Right: User avatar + logout -->
  {#if auth.user}
    <div style="display:flex;align-items:center;gap:8px;">
      <div style="
        width: 32px; height: 32px; background: #9d4867;
        display: flex; align-items: center; justify-content: center;
        border: 2px solid #383832; font-size: 12px; font-weight: 900; color: white;
      ">
        {userInitial}
      </div>
      <button
        onclick={() => auth.logout()}
        style="
          padding: 6px 12px; background: #be2d06; color: white;
          border: 2px solid #383832; font-family: 'Space Grotesk', sans-serif;
          font-size: 10px; font-weight: 900; letter-spacing: 0.08em; cursor: pointer;
          box-shadow: 2px 2px 0 #383832;
        "
        onmousedown={(e) => {
          e.currentTarget.style.transform = 'translate(1px, 1px)';
          e.currentTarget.style.boxShadow = '1px 1px 0 #383832';
        }}
        onmouseup={(e) => {
          e.currentTarget.style.transform = 'translate(0, 0)';
          e.currentTarget.style.boxShadow = '2px 2px 0 #383832';
        }}
      >
        LOGOUT
      </button>
    </div>
  {/if}
</header>
