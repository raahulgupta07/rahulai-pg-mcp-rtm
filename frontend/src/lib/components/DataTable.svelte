<script lang="ts">
  let { title = "", data = [], columns = [], maxHeight = "500px" } = $props();

  let sortCol = $state(null);
  let sortAsc = $state(true);

  function handleSort(col) {
    if (sortCol === col) {
      sortAsc = !sortAsc;
    } else {
      sortCol = col;
      sortAsc = true;
    }
  }

  let sortedData = $derived(() => {
    if (!sortCol) return data;
    const sorted = [...data].sort((a, b) => {
      const va = a[sortCol] ?? "";
      const vb = b[sortCol] ?? "";
      if (typeof va === "number" && typeof vb === "number") {
        return sortAsc ? va - vb : vb - va;
      }
      const sa = String(va).toLowerCase();
      const sb = String(vb).toLowerCase();
      if (sa < sb) return sortAsc ? -1 : 1;
      if (sa > sb) return sortAsc ? 1 : -1;
      return 0;
    });
    return sorted;
  });

  let rows = $derived(sortedData());
</script>

<div
  style="
    border-top: 2px solid #383832;
    border-left: 2px solid #383832;
    border-bottom: 4px solid #383832;
    border-right: 4px solid #383832;
    border-radius: 0;
    box-shadow: 4px 4px 0px 0px #383832;
    font-family: 'Space Grotesk', sans-serif;
    overflow: hidden;
  "
>
  <!-- Title bar -->
  <div
    class="flex items-center justify-between px-3 py-2"
    style="background: #383832; color: #feffd6;"
  >
    <span class="font-black uppercase tracking-widest" style="font-size: 11px;">
      {title}
    </span>
    <span
      class="font-mono font-bold uppercase tracking-widest"
      style="font-size: 10px; opacity: 0.7;"
    >
      {data.length} ROWS
    </span>
  </div>

  <!-- Scrollable table area -->
  <div style="max-height: {maxHeight}; overflow-y: auto;">
    <table class="w-full" style="border-collapse: collapse;">
      <thead>
        <tr>
          {#each columns as col}
            <th
              class="text-left px-3 py-2 font-black uppercase tracking-widest cursor-pointer select-none"
              style="
                background: #ebe8dd;
                font-size: 10px;
                color: #383832;
                border-bottom: 2px solid #383832;
                position: sticky;
                top: 0;
                z-index: 1;
              "
              onclick={() => handleSort(col)}
            >
              {col}
              {#if sortCol === col}
                <span style="margin-left: 4px;">{sortAsc ? "▲" : "▼"}</span>
              {/if}
            </th>
          {/each}
        </tr>
      </thead>
      <tbody>
        {#each rows as row, i}
          <tr style="background: {i % 2 === 0 ? 'white' : '#fcf9ef'};">
            {#each columns as col}
              <td
                class="px-3 py-1.5 font-mono"
                style="
                  font-size: 10px;
                  color: #383832;
                  border-bottom: 1px solid #ebe8dd;
                "
              >
                {row[col] ?? ""}
              </td>
            {/each}
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
</div>
