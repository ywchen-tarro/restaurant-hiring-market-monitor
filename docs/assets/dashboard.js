/* Restaurant Hiring Market Monitor — dashboard logic.
 *
 * Data source: ./data/posts.json (written by the scraper).
 * Optional overlay: ./benchmark.json (used by the local-only view to draw an
 * internal-reference line on the trend chart). If absent (e.g. on GitHub
 * Pages), the overlay is silently skipped.
 */
(function () {
  'use strict';

  // ────────────────────────────────────────────────────────
  // CONFIG (must mirror scraper/config.py for display purposes)
  // ────────────────────────────────────────────────────────
  const PLATFORMS = [
    { id: '168worker',     name: '168worker',    color: '#2563EB' },
    { id: 'usahuarenjie',  name: '华人街生活网',  color: '#3D6B21' },
    { id: '500work',       name: '500work',      color: '#B45309' },
    { id: 'uscanyin',      name: '北美餐饮通',    color: '#9D174D' },
    { id: 'niuyuegongzuo', name: '纽约工作网',    color: '#5B21B6' },
  ];
  const PLATFORM_BY_ID = Object.fromEntries(PLATFORMS.map(p => [p.id, p]));
  const REGIONS = ['东部', '南部', '中部', '西部'];

  // ────────────────────────────────────────────────────────
  // STATE
  // ────────────────────────────────────────────────────────
  const state = {
    data: null,        // parsed posts.json
    benchmark: null,   // optional local-only overlay
    filters: { search: '', platform: '', region: '', keyword: '' },
    charts: { pie: null, trend: null },
  };

  // i18n helper — falls back to identity if i18n.js failed to load.
  const t = (k, p) => (window.I18N ? window.I18N.t(k, p) : k);
  const regionName = (c) => (window.I18N ? window.I18N.region(c) : c);

  // ────────────────────────────────────────────────────────
  // ENTRY POINT
  // ────────────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', init);

  async function init() {
    wireTabs();
    wireFilters();
    wireLangToggle();
    window.addEventListener('langchange', () => {
      // Re-render dynamic content. data-i18n attributes already updated
      // by i18n.js itself; we only need to refresh JS-generated strings.
      if (state.data) {
        renderHeader(); renderKpis(); renderAlertBanner();
        populateSelects();  // refreshes platform options
        renderOverview(); renderTrend(); renderRegion(); renderPosts();
      }
    });
    const dataUrl = window.DASHBOARD_DATA_URL || './data/posts.json';
    const benchmarkUrl = window.DASHBOARD_BENCHMARK_URL || './benchmark.json';
    try {
      const r = await fetch(dataUrl, { cache: 'no-store' });
      if (!r.ok) throw new Error(dataUrl + ' fetch failed: ' + r.status);
      state.data = await r.json();
    } catch (err) {
      console.warn(err);
      renderEmpty();
      return;
    }
    try {
      const r = await fetch(benchmarkUrl, { cache: 'no-store' });
      if (r.ok) state.benchmark = await r.json();
    } catch (_) { /* expected on GitHub Pages */ }

    renderAll();
  }

  function wireTabs() {
    document.querySelectorAll('.tab').forEach(el => {
      el.addEventListener('click', () => {
        const id = el.dataset.tab;
        document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t === el));
        document.querySelectorAll('.tab-content').forEach(c => {
          c.classList.toggle('active', c.id === 'tab-' + id);
        });
        // Re-render charts on tab activation so canvases size correctly
        if (id === 'overview') renderOverview();
        if (id === 'trend') renderTrend();
        if (id === 'region') renderRegion();
        if (id === 'posts') renderPosts();
      });
    });
  }

  function wireFilters() {
    const $ = id => document.getElementById(id);
    $('postSearch').addEventListener('input', e => { state.filters.search = e.target.value.trim(); renderPosts(); });
    $('postPlatform').addEventListener('change', e => { state.filters.platform = e.target.value; renderPosts(); });
    $('postRegion').addEventListener('change', e => { state.filters.region = e.target.value; renderPosts(); });
    $('regionPlatform').addEventListener('change', renderRegion);
    $('trendRange').addEventListener('change', renderTrend);
  }

  function wireLangToggle() {
    const btn = document.getElementById('langToggle');
    if (!btn || !window.I18N) return;
    btn.addEventListener('click', () => window.I18N.toggle());
  }

  function renderEmpty() {
    document.getElementById('kpiTotal').textContent = '—';
    document.getElementById('lastRunText').textContent = t('statusNeverRun');
    document.querySelector('#platformList').innerHTML =
      '<div class="empty-state">' + t('noData') + ' — ' + t('noDataHelp') + '</div>';
  }

  function renderAll() {
    renderHeader();
    renderKpis();
    populateSelects();
    renderOverview();
    renderTrend();
    renderRegion();
    renderPosts();
    renderAlertBanner();
  }

  // ────────────────────────────────────────────────────────
  // HEADER + KPIs
  // ────────────────────────────────────────────────────────
  function renderHeader() {
    const d = state.data;
    const lang = window.I18N ? window.I18N.getLang() : 'en';
    const locale = lang === 'zh' ? 'zh-CN' : 'en-US';
    document.getElementById('lastRunText').textContent =
      t('lastRunPrefix') + ': ' + new Date(d.meta.last_updated).toLocaleString(locale);
    document.getElementById('nextRunText').textContent =
      `${t('dataWindowLabel')}: ${d.meta.date_from} ~ ${d.meta.date_to} (${d.meta.scrape_days_back}d)`;
  }

  function renderKpis() {
    const d = state.data;
    // Show unique_posts as the headline when dedup found duplicates;
    // otherwise show total_posts.
    const total = d.meta.total_posts;
    const unique = d.meta.unique_posts != null ? d.meta.unique_posts : total;
    document.getElementById('kpiTotal').textContent = unique;
    const subEl = document.getElementById('kpiTotalSub');
    const deltaTxt = totalDeltaText();
    if (unique < total) {
      subEl.textContent = `${total} ${t('rangeAll').toLowerCase()} · ${deltaTxt}`;
    } else {
      subEl.textContent = deltaTxt;
    }

    document.getElementById('kpiWindow').textContent = `${d.meta.scrape_days_back}d`;
    document.getElementById('kpiWindowSub').textContent = d.meta.date_from;

    // Top platform
    const platRanked = PLATFORMS
      .map(p => ({ ...p, total: (d.by_platform[p.id] || {}).total || 0 }))
      .sort((a, b) => b.total - a.total);
    const top = platRanked[0];
    document.getElementById('kpiTopPlatform').textContent = top.name;
    document.getElementById('kpiTopPlatformSub').textContent = `${top.total}`;

    // Top region
    const regRanked = REGIONS
      .map(r => ({ r, total: (d.by_region[r] || {}).total || 0 }))
      .sort((a, b) => b.total - a.total);
    const topReg = regRanked[0];
    document.getElementById('kpiTopRegion').textContent = regionName(topReg.r);
    const topStates = (d.by_region[topReg.r] || {}).top_states || {};
    const topStateName = Object.keys(topStates)[0] || '';
    document.getElementById('kpiTopRegionSub').textContent =
      t('kpiTopRegionSub', { total: topReg.total, state: topStateName || '—' });

    // Rising alerts: count platforms with notable Δ vs previous history entry
    const { rising, falling } = computeAlerts();
    const totalSignals = rising.length + falling.length;
    document.getElementById('kpiAlerts').textContent = totalSignals;
    document.getElementById('kpiAlerts').style.color =
      rising.length > falling.length ? 'var(--accent2)' : (falling.length > 0 ? 'var(--warn)' : 'var(--muted)');
    const sub = document.getElementById('kpiAlertsSub');
    if (sub) sub.textContent = t('kpiAlertsBreakdown', { rising: rising.length, falling: falling.length });
  }

  function totalDeltaText() {
    const h = state.data.history || [];
    if (h.length < 2) return t('kpiTotalSubFirst');
    const cur = h[h.length - 1].total;
    const prev = h[h.length - 2].total;
    if (prev === 0) return '—';
    const pct = ((cur - prev) / prev) * 100;
    const arrow = pct >= 0 ? '▲' : '▼';
    return `${arrow} ${Math.abs(pct).toFixed(1)}%`;
  }

  function computeAlerts() {
    const h = state.data.history || [];
    if (h.length < 2) return { rising: [], falling: [] };
    const cur = h[h.length - 1].by_platform;
    const prev = h[h.length - 2].by_platform;
    const rising = [], falling = [];
    for (const p of PLATFORMS) {
      const c = cur[p.id] || 0;
      const v = prev[p.id] || 0;
      if (v < 10) continue;  // ignore noisy small bases
      const delta = (c - v) / v;
      if (delta >= 0.20) rising.push({ platform: p, current: c, prev: v, pct: delta * 100 });
      else if (delta <= -0.20) falling.push({ platform: p, current: c, prev: v, pct: delta * 100 });
    }
    return { rising, falling };
  }

  function isStale() {
    const lu = state.data && state.data.meta && state.data.meta.last_updated;
    if (!lu) return false;
    const ageMs = Date.now() - new Date(lu).getTime();
    return ageMs > 4 * 24 * 3600 * 1000;
  }

  function renderAlertBanner() {
    const { rising, falling } = computeAlerts();
    const warnings = (state.data && state.data.meta && state.data.meta.warnings) || [];
    const banner = document.getElementById('alertBanner');
    const text = document.getElementById('alertText');

    const messages = [];
    if (isStale()) {
      const days = Math.floor((Date.now() - new Date(state.data.meta.last_updated).getTime()) / (24 * 3600 * 1000));
      messages.push('⏰ ' + t('staleData', { days }));
    }
    warnings.forEach(w => messages.push(`⚠ ${w}`));
    rising.forEach(a => messages.push(`▲ ${a.platform.name} ${t('rising')} +${a.pct.toFixed(0)}% (${a.prev} → ${a.current})`));
    falling.forEach(a => messages.push(`▼ ${a.platform.name} ${t('cooling')} ${a.pct.toFixed(0)}% (${a.prev} → ${a.current})`));

    if (messages.length === 0) {
      banner.classList.remove('shown');
      return;
    }
    banner.classList.add('shown');
    text.innerHTML = messages.map(m => escapeHtml(m)).join(' &nbsp;·&nbsp; ');
  }

  function populateSelects() {
    // Idempotent: clear and re-populate so a language change refreshes
    // the "All platforms" option text. Other options are platform brand
    // names that don't translate.
    const pp = document.getElementById('postPlatform');
    const rp = document.getElementById('regionPlatform');

    // Keep first <option> (the data-i18n "all" one) — i18n.js handles
    // its translation. Drop everything after it.
    [pp, rp].forEach(sel => {
      while (sel.children.length > 1) sel.removeChild(sel.lastChild);
    });

    PLATFORMS.forEach(p => {
      const o1 = document.createElement('option');
      o1.value = p.id; o1.textContent = p.name; pp.appendChild(o1);
      const o2 = document.createElement('option');
      o2.value = p.id; o2.textContent = p.name; rp.appendChild(o2);
    });
  }

  // ────────────────────────────────────────────────────────
  // OVERVIEW TAB
  // ────────────────────────────────────────────────────────
  function renderOverview() {
    const d = state.data;
    if (!d) return;

    const totals = PLATFORMS.map(p => ({
      ...p,
      total: (d.by_platform[p.id] || {}).total || 0,
    }));
    const sum = totals.reduce((s, p) => s + p.total, 0);
    const max = Math.max(...totals.map(p => p.total), 1);

    // Per-platform deltas from history
    const h = d.history || [];
    const prev = h.length >= 2 ? h[h.length - 2].by_platform : {};

    // Platform list
    const list = document.getElementById('platformList');
    list.innerHTML = '';
    totals.sort((a, b) => b.total - a.total).forEach(p => {
      const prevCount = prev[p.id] || 0;
      let trendTxt = '—';
      let trendCls = 'neu';
      if (prevCount > 0) {
        const pct = ((p.total - prevCount) / prevCount) * 100;
        trendTxt = (pct >= 0 ? '+' : '') + pct.toFixed(0) + '%';
        trendCls = pct > 0 ? 'up' : (pct < 0 ? 'down' : 'neu');
      } else if (h.length >= 2 && p.total > 0) {
        trendTxt = t('trendNew');
        trendCls = 'up';
      }
      const row = document.createElement('div');
      row.className = 'platform-row';
      row.innerHTML = `
        <span class="p-dot" style="background:${p.color}"></span>
        <span class="p-name">${p.name}</span>
        <div class="p-bar-wrap"><div class="p-bar" style="width:${(p.total / max) * 100}%; background:${p.color}"></div></div>
        <span class="p-count">${p.total}</span>
        <span class="p-trend ${trendCls}">${trendTxt}</span>
      `;
      list.appendChild(row);
    });

    // Donut
    if (state.charts.pie) state.charts.pie.destroy();
    const ctx = document.getElementById('pieChart');
    if (sum === 0) {
      ctx.parentElement.querySelector('#pieLegend').innerHTML =
        '<div class="empty-state">' + escapeHtml(t('noData')) + '</div>';
      return;
    }
    state.charts.pie = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: totals.map(p => p.name),
        datasets: [{
          data: totals.map(p => p.total),
          backgroundColor: totals.map(p => p.color),
          borderColor: '#13161d',
          borderWidth: 2,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        cutout: '60%',
      },
    });
    // legend below
    const legend = document.getElementById('pieLegend');
    legend.innerHTML = '';
    totals.forEach(p => {
      const pct = sum ? ((p.total / sum) * 100).toFixed(1) : '0.0';
      const row = document.createElement('div');
      row.style.cssText = 'display:flex; align-items:center; gap:8px; font-size:12px;';
      row.innerHTML = `
        <span style="width:10px; height:10px; background:${p.color}; border-radius:2px; display:inline-block;"></span>
        <span style="flex:1; color:var(--text)">${p.name}</span>
        <span style="font-family:var(--mono); color:var(--muted)">${pct}%</span>
      `;
      legend.appendChild(row);
    });
  }

  // ────────────────────────────────────────────────────────
  // TREND TAB
  // ────────────────────────────────────────────────────────
  function renderTrend() {
    const d = state.data;
    if (!d) return;
    const range = parseInt(document.getElementById('trendRange').value, 10);
    let history = (d.history || []).slice();
    if (range > 0) history = history.slice(-range);

    if (history.length === 0) {
      document.getElementById('trendNotice').style.display = 'block';
      document.getElementById('trendNotice').textContent = t('noRecentData');
    } else if (history.length === 1) {
      document.getElementById('trendNotice').style.display = 'block';
      document.getElementById('trendNotice').textContent = t('noRecentData');
    } else {
      document.getElementById('trendNotice').style.display = 'none';
    }

    const labels = history.map(h => h.run_date);
    const datasets = PLATFORMS.map(p => ({
      label: p.name,
      data: history.map(h => (h.by_platform || {})[p.id] || 0),
      borderColor: p.color,
      backgroundColor: p.color + '33',
      tension: 0.25,
      pointRadius: 3,
      pointHoverRadius: 5,
      borderWidth: 2,
    }));

    // Optional benchmark overlay (local-only)
    if (state.benchmark && Array.isArray(state.benchmark.series)) {
      const benchByMonth = Object.fromEntries(
        state.benchmark.series.map(p => [p.month, p.value])
      );
      const benchValues = labels.map(d => {
        const month = (d || '').slice(0, 7);
        return benchByMonth[month] != null ? benchByMonth[month] : null;
      });
      datasets.push({
        label: state.benchmark.label || 'Benchmark',
        data: benchValues,
        borderColor: state.benchmark.color || '#ff8c42',
        borderDash: [6, 4],
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.1,
        yAxisID: 'y2',
        spanGaps: true,
      });
    }

    if (state.charts.trend) state.charts.trend.destroy();
    const ctx = document.getElementById('trendChart');
    const scales = {
      x: { ticks: { color: '#6b7494', font: { family: 'DM Mono' } }, grid: { color: '#252a38' } },
      y: { ticks: { color: '#6b7494', font: { family: 'DM Mono' } }, grid: { color: '#252a38' }, beginAtZero: true },
    };
    if (state.benchmark) {
      scales.y2 = {
        position: 'right',
        ticks: { color: '#ff8c42', font: { family: 'DM Mono' } },
        grid: { drawOnChartArea: false },
        beginAtZero: true,
      };
    }
    state.charts.trend = new Chart(ctx, {
      type: 'line',
      data: { labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: '#e8ecf4', font: { family: 'Noto Sans SC' } } },
          tooltip: { mode: 'index', intersect: false },
        },
        scales,
      },
    });
  }

  // ────────────────────────────────────────────────────────
  // REGION TAB
  // ────────────────────────────────────────────────────────
  function renderRegion() {
    const d = state.data;
    if (!d) return;
    const platformFilter = document.getElementById('regionPlatform').value;

    let byRegion;
    if (platformFilter === 'all') {
      byRegion = d.by_region;
    } else {
      // Recompute from posts[] for the selected platform
      const filtered = (d.posts || []).filter(p => p.platform === platformFilter);
      byRegion = {};
      REGIONS.forEach(r => {
        const rp = filtered.filter(p => p.region === r);
        const sCounts = {};
        rp.forEach(p => { if (p.state) sCounts[p.state] = (sCounts[p.state] || 0) + 1; });
        const top = Object.entries(sCounts).sort((a, b) => b[1] - a[1]).slice(0, 5);
        byRegion[r] = { total: rp.length, top_states: Object.fromEntries(top) };
      });
    }

    const grid = document.getElementById('regionGrid');
    grid.innerHTML = '';
    REGIONS.forEach(r => {
      const info = byRegion[r] || { total: 0, top_states: {} };
      const states = Object.entries(info.top_states || {});
      const maxState = Math.max(1, ...states.map(([, c]) => c));
      const block = document.createElement('div');
      block.className = 'region-block';
      const stateRows = states.length
        ? states.map(([n, c], i) => `
            <div class="state-row">
              <span class="state-name">${escapeHtml(n)}</span>
              <div class="state-bar-wrap"><div class="state-bar ${i === 0 ? 'peak' : ''}" style="width:${(c / maxState) * 100}%"></div></div>
              <span class="state-count">${c}</span>
            </div>`).join('')
        : `<div class="empty-state" style="padding:14px; font-size:12px;">${escapeHtml(t('noData'))}</div>`;
      block.innerHTML = `
        <div class="region-head">
          <span class="region-name">${escapeHtml(regionName(r))}</span>
          <span class="region-total">${info.total}</span>
        </div>
        <div class="state-list">${stateRows}</div>
      `;
      grid.appendChild(block);
    });
  }

  // ────────────────────────────────────────────────────────
  // POSTS TAB
  // ────────────────────────────────────────────────────────
  function renderPosts() {
    const d = state.data;
    if (!d) return;
    const posts = d.posts || [];

    // Keyword chips — re-render on language change too
    const kwFilter = document.getElementById('kwFilter');
    kwFilter.innerHTML = '';
    const top = Object.entries(d.by_keyword || {}).slice(0, 12);
    const allChip = chip(t('rangeAll'), '', state.filters.keyword === '');
    kwFilter.appendChild(allChip);
    top.forEach(([kw, n]) => {
      kwFilter.appendChild(chip(`${kw} · ${n}`, kw, state.filters.keyword === kw));
    });

    const f = state.filters;
    const filtered = posts.filter(p => {
      if (f.search && !p.title.toLowerCase().includes(f.search.toLowerCase())) return false;
      if (f.platform && p.platform !== f.platform) return false;
      if (f.region && p.region !== f.region) return false;
      if (f.keyword && !(p.keywords_matched || []).includes(f.keyword)) return false;
      return true;
    });

    const feed = document.getElementById('postsFeed');
    if (filtered.length === 0) {
      feed.innerHTML = `<div class="empty-state">${escapeHtml(t('noPosts'))}</div>`;
      return;
    }

    // Sort by date desc (string ISO sort works)
    filtered.sort((a, b) => (b.date || '').localeCompare(a.date || ''));

    feed.innerHTML = '';
    filtered.slice(0, 300).forEach(p => {
      const platMeta = PLATFORM_BY_ID[p.platform] || { name: p.platform, color: '#888' };
      const url = safeUrl(p.url);
      const titleHtml = escapeHtml(p.title);
      const titleEl = url
        ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${titleHtml}</a>`
        : titleHtml;
      const el = document.createElement('div');
      el.className = 'post-item';
      el.innerHTML = `
        <div class="post-meta">
          <span class="post-platform" style="background:${platMeta.color}33; color:${platMeta.color}">${escapeHtml(platMeta.name)}</span>
          <span class="post-time">${escapeHtml(p.date || '—')}</span>
        </div>
        <div class="post-title">${titleEl}</div>
        <div class="post-region">${escapeHtml(regionName(p.region) || t('unknownRegion'))} · ${escapeHtml(p.state || '—')} ${(p.keywords_matched || []).map(k => `<span class="kw-tag">${escapeHtml(k)}</span>`).join('')}</div>
      `;
      feed.appendChild(el);
    });
  }

  function chip(label, value, active) {
    const el = document.createElement('button');
    el.className = 'kw-chip' + (active ? ' active' : '');
    el.textContent = label;
    el.addEventListener('click', () => {
      state.filters.keyword = value;
      // refresh active states
      document.querySelectorAll('#kwFilter .kw-chip').forEach(c => c.classList.remove('active'));
      el.classList.add('active');
      renderPosts();
    });
    return el;
  }

  function escapeHtml(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
  }

  // Only http(s) URLs are safe to set as an href — anything else (javascript:,
  // data:, file:) could trigger XSS / drive-by behavior when clicked.
  function safeUrl(u) {
    if (typeof u !== 'string') return null;
    return /^https?:\/\//i.test(u) ? u : null;
  }
})();
