<script lang="ts">
  import { getCoverage } from '$lib/api';

  let data = $state<any>(null);
  let loading = $state(true);
  let error = $state('');
  let sortCol = $state('total');
  let sortDir = $state<'asc' | 'desc'>('desc');
  let filterStatus = $state('All');

  $effect(() => {
    loadData();
  });

  async function loadData() {
    loading = true;
    error = '';
    try {
      data = await getCoverage();
    } catch (e: any) {
      error = e.message || 'Failed to load coverage data';
    } finally {
      loading = false;
    }
  }

  function getStatus(row: { total: number; a: number; b: number; c: number }): string {
    if (row.a > 3) return 'STRONG';
    if (row.a > 0) return 'MODERATE';
    if (row.b > 0 || row.c > 0) return 'WEAK';
    return 'GAP';
  }

  function statusColor(status: string): string {
    switch (status) {
      case 'STRONG': return '#007518';
      case 'MODERATE': return '#ff9d00';
      case 'WEAK': return '#be2d06';
      case 'GAP': return '#383832';
      default: return '#383832';
    }
  }

  function statusBg(status: string): string {
    switch (status) {
      case 'STRONG': return '#00fc4022';
      case 'MODERATE': return '#ff9d0022';
      case 'WEAK': return '#be2d0622';
      case 'GAP': return '#383832';
      default: return 'transparent';
    }
  }

  let townships = $derived(() => {
    if (!data?.summary) return [];
    return Object.entries(data.summary)
      .map(([name, vals]: [string, any]) => ({
        name,
        total: vals.total,
        a: vals.a,
        b: vals.b,
        c: vals.c,
        status: getStatus(vals),
      }))
      .filter((t: any) => filterStatus === 'All' || t.status === filterStatus)
      .sort((x: any, y: any) => {
        const aVal = sortCol === 'name' ? x.name : sortCol === 'status' ? x.status : x[sortCol];
        const bVal = sortCol === 'name' ? y.name : sortCol === 'status' ? y.status : y[sortCol];
        if (typeof aVal === 'string') {
          return sortDir === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
        }
        return sortDir === 'asc' ? aVal - bVal : bVal - aVal;
      });
  });

  let kpis = $derived(() => {
    const rows = townships();
    return {
      totalTownships: rows.length,
      strong: rows.filter((t: any) => t.status === 'STRONG').length,
      moderate: rows.filter((t: any) => t.status === 'MODERATE').length,
      weak: rows.filter((t: any) => t.status === 'WEAK').length,
      gaps: rows.filter((t: any) => t.status === 'GAP').length,
      totalOutlets: rows.reduce((s: number, t: any) => s + t.total, 0),
      withGeo: data?.total_with_geo ?? 0,
      withoutGeo: data?.total_without_geo ?? 0,
    };
  });

  function toggleSort(col: string) {
    if (sortCol === col) {
      sortDir = sortDir === 'asc' ? 'desc' : 'asc';
    } else {
      sortCol = col;
      sortDir = 'desc';
    }
  }
</script>

<svelte:head>
  <title>Coverage Analysis | MCP Agent</title>
</svelte:head>

<div style="padding: 2rem; max-width: 1400px; margin: 0 auto;">

  <!-- HERO -->
  <div style="border: 4px solid #383832; background: #383832; color: #feffd6; padding: 2rem 2.5rem; margin-bottom: 2rem; box-shadow: 6px 6px 0 #007518;">
    <div style="display: flex; align-items: center; gap: 1rem; margin-bottom: 0.5rem;">
      <span style="font-size: 1.5rem;">&#9635;</span>
      <h1 style="font-family: 'Space Grotesk', sans-serif; font-weight: 900; font-size: 2rem; letter-spacing: 2px; margin: 0;">
        COVERAGE GAP ANALYSIS
      </h1>
    </div>
    <p style="font-family: 'Space Grotesk', sans-serif; font-size: 0.85rem; opacity: 0.7; margin: 0; letter-spacing: 1px;">
      TOWNSHIP-LEVEL OUTLET DISTRIBUTION AND COVERAGE STATUS
    </p>
  </div>

  {#if loading}
    <div style="border: 2px solid #383832; padding: 3rem; text-align: center; font-family: 'Space Grotesk', monospace; font-weight: 700; letter-spacing: 2px;">
      LOADING COVERAGE DATA...
    </div>
  {:else if error}
    <div style="border: 2px solid #be2d06; background: #be2d0611; padding: 2rem; font-family: 'Space Grotesk', monospace; color: #be2d06; font-weight: 700;">
      ERROR: {error}
    </div>
  {:else if !data || !data.summary || Object.keys(data.summary).length === 0}
    <div style="border: 2px solid #383832; padding: 3rem; text-align: center; font-family: 'Space Grotesk', monospace;">
      <p style="font-weight: 700; font-size: 1.1rem; margin-bottom: 0.5rem;">NO COVERAGE DATA AVAILABLE</p>
      <p style="opacity: 0.6; font-size: 0.85rem;">Run a classification job first, then return here to view coverage analysis.</p>
    </div>
  {:else}

    <!-- KPI CARDS -->
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin-bottom: 2rem;">
      <!-- Total Townships -->
      <div style="border: 2px solid #383832; padding: 1.25rem; background: #feffd6; box-shadow: 4px 4px 0 #383832;">
        <div style="font-family: 'Space Grotesk', sans-serif; font-size: 0.65rem; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; opacity: 0.6; margin-bottom: 0.25rem;">TOWNSHIPS</div>
        <div style="font-family: 'Space Grotesk', monospace; font-size: 2rem; font-weight: 900; color: #383832;">{kpis().totalTownships}</div>
      </div>

      <!-- Strong -->
      <div style="border: 2px solid #007518; padding: 1.25rem; background: #00fc4011; box-shadow: 4px 4px 0 #007518;">
        <div style="font-family: 'Space Grotesk', sans-serif; font-size: 0.65rem; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: #007518; margin-bottom: 0.25rem;">STRONG</div>
        <div style="font-family: 'Space Grotesk', monospace; font-size: 2rem; font-weight: 900; color: #007518;">{kpis().strong}</div>
      </div>

      <!-- Moderate -->
      <div style="border: 2px solid #ff9d00; padding: 1.25rem; background: #ff9d0011; box-shadow: 4px 4px 0 #ff9d00;">
        <div style="font-family: 'Space Grotesk', sans-serif; font-size: 0.65rem; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: #ff9d00; margin-bottom: 0.25rem;">MODERATE</div>
        <div style="font-family: 'Space Grotesk', monospace; font-size: 2rem; font-weight: 900; color: #ff9d00;">{kpis().moderate}</div>
      </div>

      <!-- Weak -->
      <div style="border: 2px solid #be2d06; padding: 1.25rem; background: #be2d0611; box-shadow: 4px 4px 0 #be2d06;">
        <div style="font-family: 'Space Grotesk', sans-serif; font-size: 0.65rem; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: #be2d06; margin-bottom: 0.25rem;">WEAK</div>
        <div style="font-family: 'Space Grotesk', monospace; font-size: 2rem; font-weight: 900; color: #be2d06;">{kpis().weak}</div>
      </div>

      <!-- Gaps -->
      <div style="border: 2px solid #383832; padding: 1.25rem; background: #383832; color: #feffd6; box-shadow: 4px 4px 0 #9d4867;">
        <div style="font-family: 'Space Grotesk', sans-serif; font-size: 0.65rem; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; opacity: 0.7; margin-bottom: 0.25rem;">GAPS</div>
        <div style="font-family: 'Space Grotesk', monospace; font-size: 2rem; font-weight: 900;">{kpis().gaps}</div>
      </div>

      <!-- Total Outlets -->
      <div style="border: 2px solid #006f7c; padding: 1.25rem; background: #006f7c11; box-shadow: 4px 4px 0 #006f7c;">
        <div style="font-family: 'Space Grotesk', sans-serif; font-size: 0.65rem; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: #006f7c; margin-bottom: 0.25rem;">TOTAL OUTLETS</div>
        <div style="font-family: 'Space Grotesk', monospace; font-size: 2rem; font-weight: 900; color: #006f7c;">{kpis().totalOutlets.toLocaleString()}</div>
      </div>
    </div>

    <!-- GEO STATUS BAR -->
    {#if kpis().withGeo > 0 || kpis().withoutGeo > 0}
      <div style="border: 2px solid #383832; padding: 0.75rem 1.25rem; margin-bottom: 1.5rem; display: flex; gap: 2rem; font-family: 'Space Grotesk', monospace; font-size: 0.75rem; letter-spacing: 1px; background: #feffd6;">
        <span>GEO_MAPPED: <strong style="color: #007518;">{kpis().withGeo}</strong></span>
        <span>NO_GEO: <strong style="color: #be2d06;">{kpis().withoutGeo}</strong></span>
      </div>
    {/if}

    <!-- FILTER BAR -->
    <div style="display: flex; gap: 0.5rem; margin-bottom: 1rem; flex-wrap: wrap;">
      {#each ['All', 'STRONG', 'MODERATE', 'WEAK', 'GAP'] as status}
        <button
          onclick={() => filterStatus = status}
          style="
            font-family: 'Space Grotesk', sans-serif;
            font-weight: 700;
            font-size: 0.75rem;
            letter-spacing: 1px;
            padding: 0.5rem 1rem;
            border: 2px solid {status === 'All' ? '#383832' : statusColor(status)};
            background: {filterStatus === status ? (status === 'All' ? '#383832' : statusColor(status)) : 'transparent'};
            color: {filterStatus === status ? '#feffd6' : (status === 'All' ? '#383832' : statusColor(status))};
            cursor: pointer;
            text-transform: uppercase;
          "
        >
          {status}
        </button>
      {/each}
    </div>

    <!-- TOWNSHIP TABLE -->
    <div style="border: 2px solid #383832; overflow: hidden;">
      <!-- Table Header Bar -->
      <div style="background: #383832; color: #feffd6; padding: 0.75rem 1.25rem; font-family: 'Space Grotesk', sans-serif; font-weight: 900; font-size: 0.85rem; letter-spacing: 2px;">
        TOWNSHIP COVERAGE BREAKDOWN ({townships().length} AREAS)
      </div>

      <div style="overflow-x: auto;">
        <table style="width: 100%; border-collapse: collapse; font-family: 'Space Grotesk', sans-serif;">
          <thead>
            <tr style="background: #feffd6; border-bottom: 2px solid #383832;">
              {#each [
                { key: 'name', label: 'TOWNSHIP' },
                { key: 'total', label: 'TOTAL' },
                { key: 'a', label: 'CLASS A' },
                { key: 'b', label: 'CLASS B' },
                { key: 'c', label: 'CLASS C' },
                { key: 'status', label: 'STATUS' },
              ] as col}
                <th
                  onclick={() => toggleSort(col.key)}
                  style="
                    padding: 0.75rem 1rem;
                    text-align: {col.key === 'name' ? 'left' : 'center'};
                    font-size: 0.7rem;
                    font-weight: 700;
                    letter-spacing: 2px;
                    cursor: pointer;
                    user-select: none;
                    white-space: nowrap;
                    border-right: 1px solid #38383222;
                  "
                >
                  {col.label}
                  {#if sortCol === col.key}
                    <span style="opacity: 0.5;">{sortDir === 'asc' ? ' ^' : ' v'}</span>
                  {/if}
                </th>
              {/each}
            </tr>
          </thead>
          <tbody>
            {#each townships() as row, i}
              <tr style="border-bottom: 1px solid #38383222; background: {i % 2 === 0 ? '#feffd6' : '#feffd6cc'};">
                <td style="padding: 0.6rem 1rem; font-weight: 700; font-size: 0.85rem; border-right: 1px solid #38383222;">
                  {row.name}
                </td>
                <td style="padding: 0.6rem 1rem; text-align: center; font-family: monospace; font-weight: 700; font-size: 0.9rem; border-right: 1px solid #38383222;">
                  {row.total}
                </td>
                <td style="padding: 0.6rem 1rem; text-align: center; font-family: monospace; font-weight: 700; font-size: 0.9rem; color: #007518; border-right: 1px solid #38383222;">
                  {row.a}
                </td>
                <td style="padding: 0.6rem 1rem; text-align: center; font-family: monospace; font-weight: 700; font-size: 0.9rem; color: #006f7c; border-right: 1px solid #38383222;">
                  {row.b}
                </td>
                <td style="padding: 0.6rem 1rem; text-align: center; font-family: monospace; font-weight: 700; font-size: 0.9rem; color: #9d4867; border-right: 1px solid #38383222;">
                  {row.c}
                </td>
                <td style="padding: 0.6rem 1rem; text-align: center;">
                  <span style="
                    display: inline-block;
                    padding: 0.25rem 0.75rem;
                    font-size: 0.7rem;
                    font-weight: 900;
                    letter-spacing: 2px;
                    border: 2px solid {statusColor(row.status)};
                    background: {statusBg(row.status)};
                    color: {row.status === 'GAP' ? '#feffd6' : statusColor(row.status)};
                  ">
                    {row.status}
                  </span>
                </td>
              </tr>
            {/each}

            {#if townships().length === 0}
              <tr>
                <td colspan="6" style="padding: 2rem; text-align: center; font-family: monospace; opacity: 0.5; font-size: 0.85rem;">
                  NO TOWNSHIPS MATCH FILTER
                </td>
              </tr>
            {/if}
          </tbody>
        </table>
      </div>
    </div>

    <!-- COVERAGE DISTRIBUTION BAR -->
    {#if kpis().totalTownships > 0}
      <div style="margin-top: 2rem; border: 2px solid #383832; overflow: hidden;">
        <div style="background: #383832; color: #feffd6; padding: 0.75rem 1.25rem; font-family: 'Space Grotesk', sans-serif; font-weight: 900; font-size: 0.85rem; letter-spacing: 2px;">
          COVERAGE DISTRIBUTION
        </div>
        <div style="padding: 1.5rem;">
          <!-- Stacked bar -->
          <div style="display: flex; height: 2.5rem; border: 2px solid #383832; overflow: hidden;">
            {#if kpis().strong > 0}
              <div style="width: {(kpis().strong / kpis().totalTownships) * 100}%; background: #007518; display: flex; align-items: center; justify-content: center;">
                <span style="font-family: 'Space Grotesk', monospace; font-size: 0.7rem; font-weight: 900; color: #feffd6; letter-spacing: 1px;">{kpis().strong}</span>
              </div>
            {/if}
            {#if kpis().moderate > 0}
              <div style="width: {(kpis().moderate / kpis().totalTownships) * 100}%; background: #ff9d00; display: flex; align-items: center; justify-content: center;">
                <span style="font-family: 'Space Grotesk', monospace; font-size: 0.7rem; font-weight: 900; color: #383832; letter-spacing: 1px;">{kpis().moderate}</span>
              </div>
            {/if}
            {#if kpis().weak > 0}
              <div style="width: {(kpis().weak / kpis().totalTownships) * 100}%; background: #be2d06; display: flex; align-items: center; justify-content: center;">
                <span style="font-family: 'Space Grotesk', monospace; font-size: 0.7rem; font-weight: 900; color: #feffd6; letter-spacing: 1px;">{kpis().weak}</span>
              </div>
            {/if}
            {#if kpis().gaps > 0}
              <div style="width: {(kpis().gaps / kpis().totalTownships) * 100}%; background: #383832; display: flex; align-items: center; justify-content: center;">
                <span style="font-family: 'Space Grotesk', monospace; font-size: 0.7rem; font-weight: 900; color: #feffd6; letter-spacing: 1px;">{kpis().gaps}</span>
              </div>
            {/if}
          </div>
          <!-- Legend -->
          <div style="display: flex; gap: 1.5rem; margin-top: 0.75rem; font-family: 'Space Grotesk', sans-serif; font-size: 0.7rem; font-weight: 700; letter-spacing: 1px; flex-wrap: wrap;">
            <span style="display: flex; align-items: center; gap: 0.4rem;">
              <span style="width: 12px; height: 12px; background: #007518; border: 1px solid #383832; display: inline-block;"></span>
              STRONG (A &gt; 3)
            </span>
            <span style="display: flex; align-items: center; gap: 0.4rem;">
              <span style="width: 12px; height: 12px; background: #ff9d00; border: 1px solid #383832; display: inline-block;"></span>
              MODERATE (A &gt; 0)
            </span>
            <span style="display: flex; align-items: center; gap: 0.4rem;">
              <span style="width: 12px; height: 12px; background: #be2d06; border: 1px solid #383832; display: inline-block;"></span>
              WEAK (B/C ONLY)
            </span>
            <span style="display: flex; align-items: center; gap: 0.4rem;">
              <span style="width: 12px; height: 12px; background: #383832; border: 1px solid #383832; display: inline-block;"></span>
              GAP (NO OUTLETS)
            </span>
          </div>
        </div>
      </div>
    {/if}

  {/if}
</div>
