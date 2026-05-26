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
    daily: null,       // parsed daily.json (per-day time series)
    benchmark: null,   // optional local-only overlay
    filters: { search: '', platform: '', region: '', keyword: '', date: '' },
    charts: { pie: null, trend: null },
  };

  // i18n helpers — fall back to identity if i18n.js failed to load.
  const t = (k, p) => (window.I18N ? window.I18N.t(k, p) : k);
  const regionName = (c) => (window.I18N ? window.I18N.region(c) : c);
  const stateName = (s) => (window.I18N ? window.I18N.state(s) : s);
  const platformName = (id) => (window.I18N ? window.I18N.platform(id) : id);

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
        renderHeatmap();
        renderOverview(); renderTrend(); renderRegion(); renderPosts();
      }
    });
    const dataUrl = window.DASHBOARD_DATA_URL || './data/posts.json';
    const benchmarkUrl = window.DASHBOARD_BENCHMARK_URL || './benchmark.json';
    const dailyUrl = window.DASHBOARD_DAILY_URL ||
      (dataUrl.endsWith('posts.json') ? dataUrl.replace('posts.json', 'daily.json') : './data/daily.json');
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
      const r = await fetch(dailyUrl, { cache: 'no-store' });
      if (r.ok) state.daily = await r.json();
    } catch (_) { /* daily.json is optional; tolerate absence */ }
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
    const dateSel = $('postDate');
    if (dateSel) dateSel.addEventListener('change', e => { state.filters.date = e.target.value; renderPosts(); });
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
    renderHeatmap();
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

    // KPI: today vs 7d average (reads daily.json)
    renderTodayKpi();

    // Top platform
    const platRanked = PLATFORMS
      .map(p => ({ ...p, total: (d.by_platform[p.id] || {}).total || 0 }))
      .sort((a, b) => b.total - a.total);
    const top = platRanked[0];
    document.getElementById('kpiTopPlatform').textContent = platformName(top.id);
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
      t('kpiTopRegionSub', { total: topReg.total, state: stateName(topStateName) || '—' });

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

  function renderTodayKpi() {
    const days = state.daily && state.daily.days;
    const valEl = document.getElementById('kpiToday');
    const subEl = document.getElementById('kpiTodaySub');
    if (!days) {
      if (valEl) valEl.textContent = '—';
      if (subEl) subEl.textContent = '';
      return;
    }
    const dateKeys = Object.keys(days).sort();
    if (!dateKeys.length) {
      valEl.textContent = '—';
      subEl.textContent = t('kpiTodayNone');
      return;
    }
    const latest = dateKeys[dateKeys.length - 1];
    const todayTotal = days[latest] ? days[latest].total : 0;
    // 7-day prior window: last 7 days INCLUDING today
    const last7 = dateKeys.slice(-7).map(k => days[k].total || 0);
    const avg = last7.length ? (last7.reduce((s, n) => s + n, 0) / last7.length) : 0;
    const avgRounded = avg.toFixed(1);
    let deltaTxt = '—';
    if (avg > 0) {
      const pct = ((todayTotal - avg) / avg) * 100;
      const arrow = pct >= 0 ? '▲' : '▼';
      deltaTxt = `${arrow} ${Math.abs(pct).toFixed(0)}%`;
    }
    valEl.textContent = todayTotal;
    valEl.style.color = avg > 0
      ? (todayTotal >= avg ? 'var(--accent2)' : 'var(--warn)')
      : 'var(--text)';
    subEl.textContent = t('kpiTodaySub', { avg: avgRounded, delta: deltaTxt });
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
      const label = platformName(p.id);
      const o1 = document.createElement('option');
      o1.value = p.id; o1.textContent = label; pp.appendChild(o1);
      const o2 = document.createElement('option');
      o2.value = p.id; o2.textContent = label; rp.appendChild(o2);
    });
  }

  // ────────────────────────────────────────────────────────
  // HEATMAP CALENDAR (GitHub-style, last 35 days)
  // ────────────────────────────────────────────────────────
  function renderHeatmap() {
    const container = document.getElementById('heatmap');
    if (!container) return;
    const days = state.daily && state.daily.days;
    if (!days || !Object.keys(days).length) {
      container.innerHTML = `<div class="empty-state" style="grid-column: 1/-1;">${escapeHtml(t('noData'))}</div>`;
      return;
    }

    // Build the last 35 days ending today (today's local date)
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const fmtIso = (d) => d.toISOString().slice(0, 10);
    const fmtShort = (d) => {
      const m = String(d.getMonth() + 1).padStart(2, '0');
      const day = String(d.getDate()).padStart(2, '0');
      return `${m}/${day}`;
    };

    // 35 days laid out by week — 5 rows × 7 cols.
    // Week boundary: Sunday start (to match calendar convention).
    // The grid ends on today and goes back 34 days, then pads to the
    // start of the week containing the earliest day.
    const dates = [];
    for (let i = 34; i >= 0; i--) {
      const d = new Date(today);
      d.setDate(d.getDate() - i);
      dates.push(d);
    }

    // Find max for color scale
    const counts = dates.map(d => (days[fmtIso(d)] || { total: 0 }).total || 0);
    const max = Math.max(1, ...counts);

    // Color tier function (5 tiers, dark surface → accent → warm)
    const tier = (n) => {
      if (n === 0) return '#1a1e28';
      const ratio = Math.min(1, n / max);
      // Stops: dark-surface, dim-blue, blue, light-blue, warm-orange
      if (ratio < 0.2) return '#1e3a8a';
      if (ratio < 0.4) return '#2563EB';
      if (ratio < 0.6) return '#3d7fff';
      if (ratio < 0.85) return '#7bb0ff';
      return '#ff8c42';
    };

    // Build grid: organize by weekday columns and week rows
    // Row 0 is the earliest week; columns are weekday (0=Sun ... 6=Sat)
    const grid = [];
    let curWeek = [];
    dates.forEach(d => {
      if (curWeek.length === 0 && d.getDay() !== 0) {
        // Pad the front of the first week with empty cells
        for (let p = 0; p < d.getDay(); p++) curWeek.push(null);
      }
      curWeek.push(d);
      if (curWeek.length === 7) {
        grid.push(curWeek);
        curWeek = [];
      }
    });
    if (curWeek.length) {
      while (curWeek.length < 7) curWeek.push(null);
      grid.push(curWeek);
    }

    const lang = window.I18N ? window.I18N.getLang() : 'en';
    const dayLabels = lang === 'zh'
      ? ['日','一','二','三','四','五','六']
      : ['S','M','T','W','T','F','S'];

    // Render
    let html = '<div></div>';  // top-left empty corner
    dayLabels.forEach(l => { html += `<div class="hm-col-label">${escapeHtml(l)}</div>`; });

    grid.forEach((week, weekIdx) => {
      // Row label: month of the first non-null day in the week
      const firstReal = week.find(d => d !== null);
      const lbl = firstReal ? fmtShort(firstReal) : '';
      html += `<div class="hm-row-label">${escapeHtml(lbl)}</div>`;
      week.forEach(d => {
        if (d === null) {
          html += '<div class="hm-day hm-day-empty"></div>';
          return;
        }
        const iso = fmtIso(d);
        const info = days[iso] || { total: 0, by_platform: {}, by_region: {} };
        const c = info.total || 0;
        const fill = tier(c);
        const tip = `${iso} · ${c} ${c === 1 ? 'post' : 'posts'}`;
        html += `<div class="hm-day" style="background:${fill}" title="${escapeHtml(tip)}" data-iso="${iso}" data-count="${c}"></div>`;
      });
    });

    // Legend row
    html += '<div></div>';
    const legendStops = ['#1a1e28','#1e3a8a','#2563EB','#3d7fff','#7bb0ff','#ff8c42'];
    const legendCells = legendStops.map(c => `<span class="hm-legend-cell" style="background:${c}"></span>`).join('');
    html += `<div class="hm-legend" style="grid-column: 2 / span 7;">
      <span>0</span><span class="hm-legend-scale">${legendCells}</span><span>${max}</span>
    </div>`;

    container.innerHTML = html;
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
        <span class="p-name">${escapeHtml(platformName(p.id))}</span>
        <div class="p-bar-wrap"><div class="p-bar" style="width:${(p.total / max) * 100}%; background:${p.color}"></div></div>
        <span class="p-count">${p.total}</span>
        <span class="p-trend ${trendCls}">${escapeHtml(trendTxt)}</span>
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
        labels: totals.map(p => platformName(p.id)),
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
        <span style="flex:1; color:var(--text)">${escapeHtml(platformName(p.id))}</span>
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
    const rangeRaw = parseInt(document.getElementById('trendRange').value, 10);

    // Prefer the per-day series from daily.json. Fall back to the
    // per-run history[] when daily.json is unavailable.
    const days = state.daily && state.daily.days;
    let labels, datasets;
    const noticeEl = document.getElementById('trendNotice');

    if (days && Object.keys(days).length > 0) {
      // Range here is "last N runs" semantics ported to days — treat as
      // "last N×~3 days" (Mon/Thu cadence) or just last N days.
      // Simpler: if range is 8 -> last 14 days; 12 -> 30 days; -1 -> all.
      const dateKeys = Object.keys(days).sort();
      let sliced;
      if (rangeRaw === 8) sliced = dateKeys.slice(-14);
      else if (rangeRaw === 12) sliced = dateKeys.slice(-30);
      else sliced = dateKeys;

      labels = sliced;
      datasets = PLATFORMS.map(p => ({
        label: platformName(p.id),
        data: sliced.map(k => ((days[k] || {}).by_platform || {})[p.id] || 0),
        borderColor: p.color,
        backgroundColor: p.color + '33',
        tension: 0.25,
        pointRadius: 2,
        pointHoverRadius: 5,
        borderWidth: 2,
      }));

      // 7-day moving average overlay on the per-day totals
      const totals = sliced.map(k => (days[k] || {}).total || 0);
      const ma7 = totals.map((_, i) => {
        const start = Math.max(0, i - 6);
        const window = totals.slice(start, i + 1);
        return window.reduce((s, n) => s + n, 0) / window.length;
      });
      datasets.push({
        label: t('trendOverlay'),
        data: ma7,
        borderColor: '#e8ecf4',
        borderDash: [6, 4],
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.2,
        fill: false,
      });

      if (sliced.length < 2) {
        noticeEl.style.display = 'block';
        noticeEl.textContent = t('noRecentData');
      } else {
        noticeEl.style.display = 'none';
      }
    } else {
      // Fallback to per-run history
      let history = (d.history || []).slice();
      if (rangeRaw > 0) history = history.slice(-rangeRaw);
      if (history.length <= 1) {
        noticeEl.style.display = 'block';
        noticeEl.textContent = t('noRecentData');
      } else {
        noticeEl.style.display = 'none';
      }
      labels = history.map(h => h.run_date);
      datasets = PLATFORMS.map(p => ({
        label: platformName(p.id),
        data: history.map(h => (h.by_platform || {})[p.id] || 0),
        borderColor: p.color,
        backgroundColor: p.color + '33',
        tension: 0.25,
        pointRadius: 3,
        pointHoverRadius: 5,
        borderWidth: 2,
      }));
    }

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
  // REGION MAP (choropleth)
  // ────────────────────────────────────────────────────────
  const MAP_DEPS_CDN = {
    d3: 'https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js',
    topojson: 'https://cdn.jsdelivr.net/npm/topojson-client@3/dist/topojson-client.min.js',
    usAtlas: 'https://cdn.jsdelivr.net/npm/us-atlas@3/states-10m.json',
  };
  let _mapDepsPromise = null;
  let _usTopo = null;

  function _loadScript(src) {
    return new Promise((resolve, reject) => {
      // Idempotent: don't re-add if already present
      if (document.querySelector(`script[src="${src}"]`)) {
        resolve(); return;
      }
      const s = document.createElement('script');
      s.src = src;
      s.onload = () => resolve();
      s.onerror = () => reject(new Error('Failed to load ' + src));
      document.head.appendChild(s);
    });
  }

  async function _ensureMapDeps() {
    if (_mapDepsPromise) return _mapDepsPromise;
    _mapDepsPromise = (async () => {
      await _loadScript(MAP_DEPS_CDN.d3);
      await _loadScript(MAP_DEPS_CDN.topojson);
      if (!_usTopo) {
        const r = await fetch(MAP_DEPS_CDN.usAtlas, { cache: 'force-cache' });
        if (!r.ok) throw new Error('us-atlas fetch failed: ' + r.status);
        _usTopo = await r.json();
      }
    })();
    return _mapDepsPromise;
  }

  async function renderRegionMap() {
    const container = document.getElementById('regionMap');
    if (!container || !state.data) return;

    // Filter posts by selected platform (same as renderRegion below)
    const platformFilter = document.getElementById('regionPlatform').value;
    let posts = state.data.posts || [];
    if (platformFilter && platformFilter !== 'all') {
      posts = posts.filter(p => p.platform === platformFilter);
    }

    // Aggregate by USPS state code
    const counts = {};
    posts.forEach(p => {
      if (!p.state) return;
      const usps = window.I18N && window.I18N.uspsFor(p.state);
      if (!usps) return;
      counts[usps] = (counts[usps] || 0) + 1;
    });

    try {
      await _ensureMapDeps();
    } catch (err) {
      container.innerHTML = `<div class="empty-state">${escapeHtml(t('noData'))}</div>`;
      console.warn('Map deps failed to load:', err);
      return;
    }

    const d3 = window.d3;
    const topojson = window.topojson;
    if (!d3 || !topojson) return;

    const states = topojson.feature(_usTopo, _usTopo.objects.states);
    const max = Math.max(1, ...Object.values(counts));
    // Custom interpolation: dark surface -> accent blue -> warm
    const color = d3.scaleSequentialPow()
      .exponent(0.5)
      .domain([0, max])
      .interpolator(d3.interpolateRgbBasis(['#1a1e28', '#1e3a8a', '#3d7fff', '#ff8c42']));

    // Clear and rebuild
    container.innerHTML = '';

    const width = container.clientWidth;
    const height = container.clientHeight;

    const svg = d3.select(container).append('svg')
      .attr('viewBox', `0 0 ${width} ${height}`)
      .attr('preserveAspectRatio', 'xMidYMid meet');

    const projection = d3.geoAlbersUsa().fitSize([width, height], states);
    const path = d3.geoPath(projection);

    const tooltip = document.getElementById('regionMapTooltip');
    const showTip = (event, fips) => {
      const usps = window.I18N.fipsToUsps(fips);
      const fullName = window.I18N.uspsToFullName(usps);
      const count = counts[usps] || 0;
      tooltip.innerHTML = `
        <div class="tt-name">${escapeHtml(fullName)} (${usps})</div>
        <div class="tt-count">${count} ${count === 1 ? 'post' : 'posts'}</div>
      `;
      tooltip.classList.add('shown');
      tooltip.style.left = (event.clientX + 12) + 'px';
      tooltip.style.top = (event.clientY + 12) + 'px';
    };
    const hideTip = () => tooltip.classList.remove('shown');

    svg.append('g')
      .selectAll('path')
      .data(states.features)
      .join('path')
      .attr('class', 'state')
      .attr('d', path)
      .attr('fill', d => {
        const usps = window.I18N.fipsToUsps(d.id);
        return color(counts[usps] || 0);
      })
      .on('mousemove', (e, d) => showTip(e, d.id))
      .on('mouseleave', hideTip);

    // Labels on states that have posts
    const labels = svg.append('g');
    states.features.forEach(d => {
      const usps = window.I18N.fipsToUsps(d.id);
      const count = counts[usps] || 0;
      if (count === 0) return;
      const [x, y] = path.centroid(d);
      if (isNaN(x) || isNaN(y)) return;
      labels.append('text')
        .attr('class', 'state-count')
        .attr('x', x)
        .attr('y', y + 2)
        .text(count);
    });

    // Legend
    const legend = document.createElement('div');
    legend.className = 'legend';
    legend.innerHTML = `<span>0</span><span class="legend-bar"></span><span>${max}</span>`;
    container.appendChild(legend);
  }

  // ────────────────────────────────────────────────────────
  // REGION TAB
  // ────────────────────────────────────────────────────────
  function renderRegion() {
    renderRegionMap().catch(err => console.warn('region map render failed:', err));
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
              <span class="state-name">${escapeHtml(stateName(n))}</span>
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
    // Build date filter cutoff once
    const now = new Date(); now.setHours(0, 0, 0, 0);
    const isoNow = now.toISOString().slice(0, 10);
    const yesterday = new Date(now); yesterday.setDate(yesterday.getDate() - 1);
    const isoYesterday = yesterday.toISOString().slice(0, 10);
    const last7Cutoff = new Date(now); last7Cutoff.setDate(last7Cutoff.getDate() - 6);
    const isoLast7 = last7Cutoff.toISOString().slice(0, 10);

    const filtered = posts.filter(p => {
      if (f.search && !p.title.toLowerCase().includes(f.search.toLowerCase())) return false;
      if (f.platform && p.platform !== f.platform) return false;
      if (f.region && p.region !== f.region) return false;
      if (f.keyword && !(p.keywords_matched || []).includes(f.keyword)) return false;
      if (f.date) {
        const pd = p.date || '';
        if (f.date === 'today' && pd !== isoNow) return false;
        else if (f.date === 'yesterday' && pd !== isoYesterday) return false;
        else if (f.date === '7' && pd < isoLast7) return false;
      }
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
          <span class="post-platform" style="background:${platMeta.color}33; color:${platMeta.color}">${escapeHtml(platformName(p.platform))}</span>
          <span class="post-time">${escapeHtml(p.date || '—')}</span>
        </div>
        <div class="post-title">${titleEl}</div>
        <div class="post-region">${escapeHtml(regionName(p.region) || t('unknownRegion'))} · ${escapeHtml(stateName(p.state) || '—')} ${(p.keywords_matched || []).map(k => `<span class="kw-tag">${escapeHtml(k)}</span>`).join('')}</div>
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
