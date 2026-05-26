<script lang="ts">
  import { getCoverage } from '$lib/api';
  import { onMount, onDestroy } from 'svelte';
  import 'leaflet/dist/leaflet.css';
  import 'leaflet.markercluster/dist/MarkerCluster.css';
  import 'leaflet.markercluster/dist/MarkerCluster.Default.css';

  let data = $state<any>(null);
  let loading = $state(true);
  let error = $state('');
  let sortCol = $state('total');
  let sortDir = $state<'asc' | 'desc'>('desc');
  let filterStatus = $state('All');
  let view = $state<'map' | 'tables'>('map');

  // map filters
  let mapBranch = $state('All');
  let mapClass = $state('All');

  // leaflet refs
  let mapEl = $state<HTMLDivElement | undefined>(undefined);
  let map: any = null;
  let L = $state<any>(null);
  let clusterGroup: any = null;
  let mapReady = $state(false);
  let shownCount = $state(0);

  const CLASS_COLOR: Record<string, string> = {
    A: '#5A8F3D',
    B: '#B5853D',
    C: '#B5453D',
    F4: '#4A7D8C',
  };

  function classKey(c: string): string {
    if (!c) return 'C';
    const u = String(c).toUpperCase();
    if (u.includes('F4') || u.includes('WHOLESAL')) return 'F4';
    if (u.startsWith('A') || u === 'CLASS A') return 'A';
    if (u.startsWith('B') || u === 'CLASS B') return 'B';
    return 'C';
  }

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

  // ---- map lifecycle ----
  onMount(async () => {
    try {
      const leaflet = await import('leaflet');
      const lib = leaflet.default ?? leaflet;
      await import('leaflet.markercluster');
      L = lib;
    } catch (e: any) {
      console.error('[coverage] leaflet load failed', e);
      error = 'Map library failed to load: ' + (e?.message || e);
    }
  });

  onDestroy(() => {
    if (map) {
      map.remove();
      map = null;
    }
  });

  function initMap() {
    if (!L || !mapEl || map) return;
    map = L.map(mapEl, { preferCanvas: true }).setView([19.7, 96.1], 6);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 19,
    }).addTo(map);
    clusterGroup = (L as any).markerClusterGroup({
      chunkedLoading: true,
      maxClusterRadius: 50,
    });
    map.addLayer(clusterGroup);
    mapReady = true;
  }

  function fmtRevenue(v: number): string {
    if (v == null) return '—';
    if (v >= 1e6) return 'Ks ' + (v / 1e6).toFixed(2) + 'M';
    if (v >= 1e3) return 'Ks ' + (v / 1e3).toFixed(1) + 'K';
    return 'Ks ' + Math.round(v);
  }

  function renderMarkers() {
    if (!map || !clusterGroup || !L || !data?.outlets) return;
    clusterGroup.clearLayers();
    const bounds: any[] = [];
    let n = 0;
    for (const o of data.outlets) {
      if (o.lat == null || o.lng == null) continue;
      if (mapBranch !== 'All' && o.branch !== mapBranch) continue;
      const ck = classKey(o.classification);
      if (mapClass !== 'All' && ck !== mapClass) continue;
      const color = CLASS_COLOR[ck] || '#888';
      const m = L.circleMarker([o.lat, o.lng], {
        radius: 6,
        color: '#fff',
        weight: 1,
        fillColor: color,
        fillOpacity: 0.85,
      });
      m.bindPopup(
        `<div style="font-size:12px;line-height:1.5">
          <strong>${o.name ?? o.code ?? 'Outlet'}</strong><br/>
          <span style="color:${color};font-weight:600">${o.classification ?? '—'}</span><br/>
          Branch: ${o.branch ?? '—'}<br/>
          Township: ${o.township ?? '—'}<br/>
          Revenue: ${fmtRevenue(o.revenue)}
          ${o.contact ? `<br/>Contact: ${o.contact}` : ''}
          ${o.phone ? `<br/>Phone: ${o.phone}` : ''}
          ${o.address ? `<br/><span style="opacity:0.75">${o.address}</span>` : ''}
        </div>`
      );
      clusterGroup.addLayer(m);
      bounds.push([o.lat, o.lng]);
      n++;
    }
    shownCount = n;
    if (bounds.length) {
      map.fitBounds(bounds, { padding: [30, 30], maxZoom: 13 });
    }
  }

  // init map when view becomes map + lib loaded + data ready
  $effect(() => {
    if (view === 'map' && L && mapEl && data && !map) {
      // mapEl now in DOM
      setTimeout(() => {
        initMap();
        renderMarkers();
        if (map) map.invalidateSize();
      }, 0);
    }
  });

  // re-render on filter change
  $effect(() => {
    mapBranch; mapClass; data;
    if (map && clusterGroup) renderMarkers();
  });

  // fix size when switching back to map
  $effect(() => {
    if (view === 'map' && map) {
      setTimeout(() => map && map.invalidateSize(), 50);
    }
  });

  let geoOutlets = $derived((data?.outlets ?? []).filter((o: any) => o.lat != null && o.lng != null));
  let branches = $derived([...new Set((data?.outlets ?? []).map((o: any) => o.branch).filter(Boolean))].sort());

  // ---- township tables ----
  function getStatus(row: { total: number; a: number; b: number; c: number }): string {
    if (row.a > 3) return 'STRONG';
    if (row.a > 0) return 'MODERATE';
    if (row.b > 0 || row.c > 0) return 'WEAK';
    return 'GAP';
  }

  function statusBadgeClass(status: string): string {
    switch (status) {
      case 'STRONG': return 'badge badge-a';
      case 'MODERATE': return 'badge badge-b';
      case 'WEAK': return 'badge-info';
      case 'GAP': return 'badge badge-c';
      default: return 'badge badge-neutral';
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
  <title>Coverage Analysis | RTM Agent</title>
</svelte:head>

<div class="page animate-fade-in">

  <!-- HERO -->
  <header class="page-head">
    <h1>Coverage Gap Analysis</h1>
    <p>Outlet map plotting and township-level coverage status</p>
  </header>

  {#if loading}
    <div class="card state-card">Loading coverage data...</div>
  {:else if error}
    <div class="alert alert-danger">Error: {error}</div>
  {:else if !data || !data.summary || Object.keys(data.summary).length === 0}
    <div class="card state-card">
      <p class="state-title">No coverage data available</p>
      <p class="state-sub">Run a classification job first, then return here to view coverage analysis.</p>
    </div>
  {:else}

    <!-- VIEW TOGGLE -->
    <div class="view-toggle">
      <button class="view-btn" class:active={view === 'map'} onclick={() => view = 'map'}>Map</button>
      <button class="view-btn" class:active={view === 'tables'} onclick={() => view = 'tables'}>Tables</button>
    </div>

    {#if view === 'map'}
      <!-- ===== MAP VIEW ===== -->
      {#if geoOutlets.length === 0}
        <div class="card state-card">
          <p class="state-title">No geo-coded outlets</p>
          <p class="state-sub">This job has no Latitude/Longitude data. Re-run a classification with a CSV that includes Latitude &amp; Longitude columns.</p>
        </div>
      {:else}
        <!-- MAP FILTERS -->
        <div class="map-controls">
          <label class="ctl">
            <span>Branch</span>
            <select bind:value={mapBranch}>
              <option value="All">All branches</option>
              {#each branches as b}
                <option value={b}>{b}</option>
              {/each}
            </select>
          </label>
          <label class="ctl">
            <span>Class</span>
            <select bind:value={mapClass}>
              <option value="All">All classes</option>
              <option value="A">Class A</option>
              <option value="B">Class B</option>
              <option value="C">Class C</option>
              <option value="F4">F4 Distributor</option>
            </select>
          </label>
          <div class="map-count">
            Showing <strong>{shownCount.toLocaleString()}</strong> of {geoOutlets.length.toLocaleString()} outlets
          </div>
        </div>

        <div class="map-shell card-flush">
          <div class="map-canvas" bind:this={mapEl}></div>
          <div class="map-legend">
            <span class="lg"><span class="dot" style="background:#5A8F3D"></span>Class A</span>
            <span class="lg"><span class="dot" style="background:#B5853D"></span>Class B</span>
            <span class="lg"><span class="dot" style="background:#B5453D"></span>Class C</span>
            <span class="lg"><span class="dot" style="background:#4A7D8C"></span>F4 Wholesaler</span>
          </div>
        </div>

        {#if kpis().withoutGeo > 0}
          <p class="geo-note">{kpis().withoutGeo.toLocaleString()} outlet(s) have no coordinates and are not plotted.</p>
        {/if}
      {/if}

    {:else}
      <!-- ===== TABLES VIEW ===== -->

      <!-- KPI CARDS -->
      <div class="grid-kpi">
        <div class="kpi">
          <div class="kpi-label">Townships</div>
          <div class="kpi-value">{kpis().totalTownships}</div>
        </div>
        <div class="kpi">
          <div class="kpi-label" style="color: var(--success);">Strong</div>
          <div class="kpi-value" style="color: var(--success);">{kpis().strong}</div>
        </div>
        <div class="kpi">
          <div class="kpi-label" style="color: var(--warning);">Moderate</div>
          <div class="kpi-value" style="color: var(--warning);">{kpis().moderate}</div>
        </div>
        <div class="kpi">
          <div class="kpi-label" style="color: var(--info);">Weak</div>
          <div class="kpi-value" style="color: var(--info);">{kpis().weak}</div>
        </div>
        <div class="kpi">
          <div class="kpi-label" style="color: var(--danger);">Gaps</div>
          <div class="kpi-value" style="color: var(--danger);">{kpis().gaps}</div>
        </div>
        <div class="kpi">
          <div class="kpi-label" style="color: var(--accent);">Total Outlets</div>
          <div class="kpi-value">{kpis().totalOutlets.toLocaleString()}</div>
        </div>
      </div>

      <!-- GEO STATUS BAR -->
      {#if kpis().withGeo > 0 || kpis().withoutGeo > 0}
        <div class="card geo-bar">
          <span>Geo mapped: <strong style="color: var(--success);">{kpis().withGeo}</strong></span>
          <span>No geo: <strong style="color: var(--danger);">{kpis().withoutGeo}</strong></span>
        </div>
      {/if}

      <!-- FILTER BAR -->
      <div class="filter-bar">
        {#each ['All', 'STRONG', 'MODERATE', 'WEAK', 'GAP'] as status}
          <button
            class="filter-pill"
            class:active={filterStatus === status}
            onclick={() => filterStatus = status}
          >
            {status}
          </button>
        {/each}
      </div>

      <!-- TOWNSHIP TABLE -->
      <div class="card-flush table-card">
        <div class="data-table-head">
          Township Coverage Breakdown ({townships().length} areas)
        </div>
        <div class="data-table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                {#each [
                  { key: 'name', label: 'Township' },
                  { key: 'total', label: 'Total' },
                  { key: 'a', label: 'Class A' },
                  { key: 'b', label: 'Class B' },
                  { key: 'c', label: 'Class C' },
                  { key: 'status', label: 'Status' },
                ] as col}
                  <th
                    onclick={() => toggleSort(col.key)}
                    class="sortable"
                    style="text-align: {col.key === 'name' ? 'left' : 'center'};"
                  >
                    {col.label}
                    {#if sortCol === col.key}
                      <span class="sort-ind">{sortDir === 'asc' ? '↑' : '↓'}</span>
                    {/if}
                  </th>
                {/each}
              </tr>
            </thead>
            <tbody>
              {#each townships() as row}
                <tr>
                  <td class="cell-name">{row.name}</td>
                  <td class="cell-num">{row.total}</td>
                  <td class="cell-num" style="color: var(--class-a);">{row.a}</td>
                  <td class="cell-num" style="color: var(--class-b);">{row.b}</td>
                  <td class="cell-num" style="color: var(--class-c);">{row.c}</td>
                  <td style="text-align: center;">
                    <span class={statusBadgeClass(row.status)}>{row.status}</span>
                  </td>
                </tr>
              {/each}

              {#if townships().length === 0}
                <tr>
                  <td colspan="6" class="empty-row">No townships match filter</td>
                </tr>
              {/if}
            </tbody>
          </table>
        </div>
      </div>

      <!-- COVERAGE DISTRIBUTION BAR -->
      {#if kpis().totalTownships > 0}
        <div class="card-flush table-card">
          <div class="data-table-head">Coverage Distribution</div>
          <div class="dist-body">
            <div class="dist-bar">
              {#if kpis().strong > 0}
                <div class="dist-seg" style="width: {(kpis().strong / kpis().totalTownships) * 100}%; background: var(--success);">
                  <span>{kpis().strong}</span>
                </div>
              {/if}
              {#if kpis().moderate > 0}
                <div class="dist-seg" style="width: {(kpis().moderate / kpis().totalTownships) * 100}%; background: var(--warning);">
                  <span style="color: var(--accent-ink);">{kpis().moderate}</span>
                </div>
              {/if}
              {#if kpis().weak > 0}
                <div class="dist-seg" style="width: {(kpis().weak / kpis().totalTownships) * 100}%; background: var(--info);">
                  <span>{kpis().weak}</span>
                </div>
              {/if}
              {#if kpis().gaps > 0}
                <div class="dist-seg" style="width: {(kpis().gaps / kpis().totalTownships) * 100}%; background: var(--danger);">
                  <span>{kpis().gaps}</span>
                </div>
              {/if}
            </div>
            <div class="dist-legend">
              <span class="legend-item">
                <span class="legend-swatch" style="background: var(--success);"></span>
                Strong (A &gt; 3)
              </span>
              <span class="legend-item">
                <span class="legend-swatch" style="background: var(--warning);"></span>
                Moderate (A &gt; 0)
              </span>
              <span class="legend-item">
                <span class="legend-swatch" style="background: var(--info);"></span>
                Weak (B/C only)
              </span>
              <span class="legend-item">
                <span class="legend-swatch" style="background: var(--danger);"></span>
                Gap (no outlets)
              </span>
            </div>
          </div>
        </div>
      {/if}

    {/if}

  {/if}
</div>

<style>
  .page {
    padding: 2rem;
    width: 100%;
    margin: 0;
  }

  .page-head {
    margin-bottom: 1.75rem;
  }
  .page-head h1 {
    font-size: 1.6rem;
    font-weight: 600;
    margin: 0;
    color: var(--text);
  }
  .page-head p {
    margin: 0.35rem 0 0;
    font-size: 0.9rem;
    color: var(--text-muted);
  }

  .state-card {
    padding: 3rem;
    text-align: center;
    color: var(--text-muted);
  }
  .state-title {
    font-weight: 600;
    font-size: 1.05rem;
    color: var(--text);
    margin: 0 0 0.4rem;
  }
  .state-sub {
    font-size: 0.85rem;
    color: var(--text-muted);
    margin: 0;
  }

  /* view toggle */
  .view-toggle {
    display: flex;
    gap: 0;
    margin-bottom: 1.25rem;
    border: 1px solid var(--border);
    width: fit-content;
  }
  .view-btn {
    padding: 0.5rem 1.4rem;
    font-size: 0.82rem;
    font-weight: 600;
    background: var(--surface);
    color: var(--text-muted);
    border: none;
    cursor: pointer;
  }
  .view-btn + .view-btn {
    border-left: 1px solid var(--border);
  }
  .view-btn.active {
    background: var(--accent);
    color: #fff;
  }

  /* map */
  .map-controls {
    display: flex;
    gap: 1rem;
    align-items: flex-end;
    margin-bottom: 1rem;
    flex-wrap: wrap;
  }
  .ctl {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
  }
  .ctl span {
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--text-muted);
  }
  .ctl select {
    padding: 0.45rem 0.7rem;
    font-size: 0.82rem;
    background: var(--surface);
    color: var(--text);
    border: 1px solid var(--border);
  }
  .map-count {
    margin-left: auto;
    font-family: var(--font-mono);
    font-size: 0.8rem;
    color: var(--text-muted);
  }

  .map-shell {
    margin-bottom: 0.75rem;
  }
  .map-canvas {
    height: 620px;
    width: 100%;
    z-index: 0;
  }
  .map-legend {
    display: flex;
    gap: 1.5rem;
    padding: 0.7rem 1rem;
    border-top: 1px solid var(--border);
    flex-wrap: wrap;
  }
  .lg {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.75rem;
    color: var(--text-muted);
  }
  .dot {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    display: inline-block;
    border: 1px solid #fff;
  }
  .geo-note {
    font-size: 0.78rem;
    color: var(--text-muted);
    margin: 0.25rem 0 0;
  }

  .grid-kpi {
    margin-bottom: 1.5rem;
  }

  .geo-bar {
    display: flex;
    gap: 2rem;
    padding: 0.85rem 1.25rem;
    margin-bottom: 1.5rem;
    font-family: var(--font-mono);
    font-size: 0.8rem;
    color: var(--text-muted);
  }

  .filter-bar {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 1rem;
    flex-wrap: wrap;
  }

  .table-card {
    margin-bottom: 1.5rem;
  }

  .sortable {
    cursor: pointer;
    user-select: none;
    white-space: nowrap;
  }
  .sort-ind {
    color: var(--accent);
    margin-left: 2px;
  }

  .cell-name {
    font-weight: 600;
    color: var(--text);
  }
  .cell-num {
    text-align: center;
    font-family: var(--font-mono);
    font-weight: 600;
  }

  .badge-info {
    display: inline-block;
    padding: 0.2rem 0.6rem;
    border-radius: var(--r-pill);
    font-size: 0.7rem;
    font-weight: 600;
    background: var(--info-soft);
    color: var(--info);
  }

  .empty-row {
    padding: 2rem;
    text-align: center;
    color: var(--text-faint);
    font-size: 0.85rem;
  }

  .dist-body {
    padding: 1.5rem;
  }
  .dist-bar {
    display: flex;
    height: 2.5rem;
    border-radius: var(--r-md);
    overflow: hidden;
    border: 1px solid var(--border);
  }
  .dist-seg {
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .dist-seg span {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    font-weight: 600;
    color: #fff;
  }
  .dist-legend {
    display: flex;
    gap: 1.5rem;
    margin-top: 0.85rem;
    font-size: 0.75rem;
    color: var(--text-muted);
    flex-wrap: wrap;
  }
  .legend-item {
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }
  .legend-swatch {
    width: 12px;
    height: 12px;
    border-radius: var(--r-sm);
    display: inline-block;
  }
</style>
