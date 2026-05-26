<script lang="ts">
  let { title = "", data = [], columns = [], maxHeight = "500px" } = $props();

  let sortCol = $state<string | null>(null);
  let sortAsc = $state(true);

  function handleSort(col: string) {
    if (sortCol === col) {
      sortAsc = !sortAsc;
    } else {
      sortCol = col;
      sortAsc = true;
    }
  }

  let rows = $derived.by(() => {
    if (!sortCol) return data;
    return [...data].sort((a: any, b: any) => {
      const va = a[sortCol!] ?? "";
      const vb = b[sortCol!] ?? "";
      if (typeof va === "number" && typeof vb === "number") {
        return sortAsc ? va - vb : vb - va;
      }
      const sa = String(va).toLowerCase();
      const sb = String(vb).toLowerCase();
      if (sa < sb) return sortAsc ? -1 : 1;
      if (sa > sb) return sortAsc ? 1 : -1;
      return 0;
    });
  });
</script>

<div class="data-table-wrap">
  {#if title}
    <div class="data-table-head">
      <span class="title">{title}</span>
      <span class="meta">{data.length} rows</span>
    </div>
  {/if}

  <div style="max-height: {maxHeight}; overflow: auto;">
    <table class="data-table">
      <thead>
        <tr>
          {#each columns as col}
            <th class="sortable" onclick={() => handleSort(col)}>
              {col}
              {#if sortCol === col}
                <span style="margin-left:3px;font-size:9px;">{sortAsc ? "▲" : "▼"}</span>
              {/if}
            </th>
          {/each}
        </tr>
      </thead>
      <tbody>
        {#each rows as row}
          <tr>
            {#each columns as col}
              <td>{row[col] ?? ""}</td>
            {/each}
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
</div>
