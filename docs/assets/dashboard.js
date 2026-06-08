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
    { id: 'us168',         name: '华人168',      color: '#5B21B6' },
    { id: 'meiguogongzuo', name: '美国工作网',    color: '#0891B2' },
  ];
  const PLATFORM_BY_ID = Object.fromEntries(PLATFORMS.map(p => [p.id, p]));
  const REGIONS = ['东部', '南部', '中部', '西部'];
  const MIRROR_GROUPS = [
    new Set(['168worker', '500work']),
  ];
  const SELF_DEDUP_PLATFORMS = new Set(['meiguogongzuo']);

  // ────────────────────────────────────────────────────────
  // STATE
  // ────────────────────────────────────────────────────────
  const state = {
    data: null,        // parsed posts.json
    daily: null,       // parsed daily.json (per-day time series)
    cityCatalog: null, // parsed cities.json (map city metadata)
    benchmark: null,   // optional local-only overlay
    filters: { search: '', platform: '', region: '', keyword: '', date: '' },
    charts: { pie: null, trend: null },
  };

  // i18n helpers — fall back to identity if i18n.js failed to load.
  const t = (k, p) => (window.I18N ? window.I18N.t(k, p) : k);
  const regionName = (c) => (window.I18N ? window.I18N.region(c) : c);
  const stateName = (s) => (window.I18N ? window.I18N.state(s) : s);
  const cityName = (s) => {
    if (!s) return '';
    const translated = window.I18N && window.I18N.city ? window.I18N.city(s) : s;
    if (translated !== s) return translated;
    const lang = window.I18N && window.I18N.getLang ? window.I18N.getLang() : 'zh';
    const catalogEntry = state.cityCatalog && state.cityCatalog.cities && state.cityCatalog.cities[s];
    if (lang === 'en' && catalogEntry && catalogEntry.en) return catalogEntry.en;
    return s;
  };
  const platformName = (id) => (window.I18N ? window.I18N.platform(id) : id);

  function normalizedTitle(title) {
    return String(title || '').match(/[\u4e00-\u9fff\uf900-\ufaffA-Za-z0-9]+/g)?.join('').toLowerCase() || '';
  }

  function mirrorGroupId(platform) {
    for (let i = 0; i < MIRROR_GROUPS.length; i += 1) {
      if (MIRROR_GROUPS[i].has(platform)) return i;
    }
    return null;
  }

  function uniquePostsForPlaceCounts(posts) {
    const seen = new Set();
    const out = [];
    (posts || []).forEach(p => {
      const nt = normalizedTitle(p.title);
      const gid = mirrorGroupId(p.platform);
      let key = null;
      if (gid !== null && nt) key = `mirror:${gid}:${nt}`;
      else if (SELF_DEDUP_PLATFORMS.has(p.platform) && nt) key = `self:${p.platform}:${nt}`;
      if (!key) {
        out.push(p);
        return;
      }
      if (seen.has(key)) return;
      seen.add(key);
      out.push(p);
    });
    return out;
  }

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
    const cityUrl = window.DASHBOARD_CITY_URL ||
      (dataUrl.endsWith('posts.json') ? dataUrl.replace('posts.json', 'cities.json') : './data/cities.json');
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
      const r = await fetch(cityUrl, { cache: 'no-store' });
      if (r.ok) state.cityCatalog = await r.json();
    } catch (_) { /* cities.json is optional; fallback to static map points */ }
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

    // Footer data line
    const footerEl = document.getElementById('footerData');
    if (footerEl) {
      footerEl.textContent = t('footerData', {
        from: d.meta.date_from,
        to: d.meta.date_to,
        total: d.meta.total_posts,
        unique: d.meta.unique_posts != null ? d.meta.unique_posts : d.meta.total_posts,
      });
    }
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

  // Time-based rolling-window helpers. The user-facing trend signal
  // compares the last 7 calendar days of posts against the prior 7,
  // independent of how many scrape runs happened in that period.
  function _sumWindow(days, dateKeys, sliceStart, sliceEnd) {
    const slice = dateKeys.slice(sliceStart, sliceEnd);
    let total = 0;
    const byPlatform = {};
    slice.forEach(k => {
      const info = days[k] || {};
      total += info.total || 0;
      for (const [p, n] of Object.entries(info.by_platform || {})) {
        byPlatform[p] = (byPlatform[p] || 0) + n;
      }
    });
    return { total, byPlatform, days: slice.length };
  }

  // Return { last7, prev7 } — both objects with .total + .byPlatform.
  // If daily.json doesn't cover 14 days, returns null windows.
  function rollingWindows() {
    const days = state.daily && state.daily.days;
    if (!days) return null;
    const dateKeys = Object.keys(days).sort();
    if (dateKeys.length < 14) {
      // Not enough history yet — only return the most recent window if any
      return {
        last7: _sumWindow(days, dateKeys, -7, undefined),
        prev7: null,
      };
    }
    return {
      last7: _sumWindow(days, dateKeys, -7, undefined),
      prev7: _sumWindow(days, dateKeys, -14, -7),
    };
  }

  function totalDeltaText() {
    const w = rollingWindows();
    if (!w || !w.prev7 || w.prev7.total === 0) return t('kpiTotalSubFirst');
    const pct = ((w.last7.total - w.prev7.total) / w.prev7.total) * 100;
    const arrow = pct >= 0 ? '▲' : '▼';
    return `${arrow} ${Math.abs(pct).toFixed(1)}%`;
  }

  // Count days within `dateKeys[sliceStart:sliceEnd]` that had >=1 post
  // for the given platform. Used by computeAlerts to suppress alerts
  // when the prior window has poor coverage (e.g., platform was newly
  // added so its "prior 7 days" includes days with no recording).
  // Platforms that have current-window data but incomplete prior-window
  // coverage — these are "newly tracked" and we can't compute a trend
  // for them yet. The dashboard surfaces this so users don't wonder why
  // the rising/cooling list looks short during a coverage ramp.
  function _platformsRamping() {
    const days = state.daily && state.daily.days;
    if (!days) return [];
    const keys = Object.keys(days).sort();
    if (keys.length < 7) return [];
    const out = [];
    for (const p of PLATFORMS) {
      const cur = _platformCoverageDays(days, keys, p.id, -7, undefined);
      const prev = _platformCoverageDays(days, keys, p.id, -14, -7);
      if (cur >= 4 && prev < 7) out.push(platformName(p.id));
    }
    return out;
  }

  // Returns { cur: [from, to], prev: [from, to] } — the ISO date ranges
  // of the two 7-day windows used by computeAlerts. Used to label the
  // alert banner with explicit time anchors.
  function _alertWindowDates() {
    const days = state.daily && state.daily.days;
    const keys = days ? Object.keys(days).sort() : [];
    const cur = keys.slice(-7);
    const prev = keys.slice(-14, -7);
    return {
      cur:  [cur[0] || '', cur[cur.length - 1] || ''],
      prev: [prev[0] || '', prev[prev.length - 1] || ''],
    };
  }

  function _platformCoverageDays(days, dateKeys, platform, sliceStart, sliceEnd) {
    return dateKeys.slice(sliceStart, sliceEnd)
      .filter(k => ((days[k] || {}).by_platform || {})[platform] > 0).length;
  }

  function computeAlerts() {
    // Time-based: compare each platform's last-7-days total against
    // its prior 7-day total. Suppress alerts when the prior window has
    // <4 days of coverage for that platform (i.e. the platform was
    // newly tracked, so a "+X%" comparison would be biased toward ↑).
    const days = state.daily && state.daily.days;
    if (!days) return { rising: [], falling: [] };
    const dateKeys = Object.keys(days).sort();
    if (dateKeys.length < 14) return { rising: [], falling: [] };

    const w = rollingWindows();
    if (!w || !w.prev7) return { rising: [], falling: [] };

    const rising = [], falling = [];
    for (const p of PLATFORMS) {
      const cur = w.last7.byPlatform[p.id] || 0;
      const prev = w.prev7.byPlatform[p.id] || 0;
      // Noise floor on absolute counts
      if (prev < 10) continue;
      // Coverage gate: require FULL 7/7 days of data in BOTH windows
      // before a comparison is allowed. Anything less mixes "real
      // change" with "we didn't have a scraper recording on day X" and
      // produces spurious +50%-style alerts during ramp-up.
      const prevCoverage = _platformCoverageDays(days, dateKeys, p.id, -14, -7);
      const curCoverage = _platformCoverageDays(days, dateKeys, p.id, -7, undefined);
      if (prevCoverage < 7 || curCoverage < 7) continue;
      const delta = (cur - prev) / prev;
      if (delta >= 0.20) rising.push({ platform: p, current: cur, prev: prev, pct: delta * 100 });
      else if (delta <= -0.20) falling.push({ platform: p, current: cur, prev: prev, pct: delta * 100 });
    }
    return { rising, falling };
  }

  function isStale() {
    // Daily scrape cadence: anything older than 36 hours means at
    // least one scheduled run was missed.
    const lu = state.data && state.data.meta && state.data.meta.last_updated;
    if (!lu) return false;
    const ageMs = Date.now() - new Date(lu).getTime();
    return ageMs > 36 * 3600 * 1000;
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
    const latestIso = dateKeys[dateKeys.length - 1];
    const latestTotal = (days[latestIso] || {}).total || 0;
    // Compare the latest complete day against the average of the 7 days
    // before it. The scraper intentionally publishes yesterday's complete
    // data, so browser-local "today" would be a partial empty bucket.
    const latestIdx = dateKeys.indexOf(latestIso);
    const priorEnd = latestIdx >= 0 ? latestIdx : dateKeys.length;
    const priorStart = Math.max(0, priorEnd - 7);
    const prior7 = dateKeys.slice(priorStart, priorEnd).map(k => days[k].total || 0);
    const avg = prior7.length ? (prior7.reduce((s, n) => s + n, 0) / prior7.length) : 0;
    const avgRounded = avg.toFixed(1);
    let deltaTxt = '—';
    if (avg > 0) {
      const pct = ((latestTotal - avg) / avg) * 100;
      const arrow = pct >= 0 ? '▲' : '▼';
      deltaTxt = `${arrow} ${Math.abs(pct).toFixed(0)}%`;
    }
    valEl.textContent = latestTotal;
    valEl.style.color = avg > 0
      ? (latestTotal >= avg ? 'var(--accent2)' : 'var(--warn)')
      : 'var(--text)';
    subEl.textContent = t('kpiTodaySub', { date: latestIso, avg: avgRounded, delta: deltaTxt });
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
    // Coverage-ramp advisory: surface when some platforms are too new
    // for the prior-7d comparison. Shown alongside fired alerts so the
    // user knows there's MORE going on that we're refusing to compare.
    const rampingPlatforms = _platformsRamping();
    if (rampingPlatforms.length > 0) {
      messages.push('ℹ ' + t('coverageRamping', { names: rampingPlatforms.join(', ') }));
    }
    warnings.forEach(w => messages.push(`⚠ ${w}`));
    // Build the explicit date-range labels for the two 7-day windows
    // so the comparison is unambiguous in the banner.
    const winRange = _alertWindowDates();
    rising.forEach(a => messages.push(
      `▲ ${platformName(a.platform.id)} ${t('rising')} +${a.pct.toFixed(0)}% · ${t('alertWindowFmt', { prevFrom: winRange.prev[0], prevTo: winRange.prev[1], prev: a.prev, curFrom: winRange.cur[0], curTo: winRange.cur[1], cur: a.current })}`
    ));
    falling.forEach(a => messages.push(
      `▼ ${platformName(a.platform.id)} ${t('cooling')} ${a.pct.toFixed(0)}% · ${t('alertWindowFmt', { prevFrom: winRange.prev[0], prevTo: winRange.prev[1], prev: a.prev, curFrom: winRange.cur[0], curTo: winRange.cur[1], cur: a.current })}`
    ));

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

    // Per-platform deltas: last 7 days vs prior 7 days (time-based,
    // independent of how many scrape batches the data was collected in).
    const w = rollingWindows();
    const last7Plat = w && w.last7 ? w.last7.byPlatform : {};
    const prev7Plat = w && w.prev7 ? w.prev7.byPlatform : null;

    // Platform list
    const list = document.getElementById('platformList');
    list.innerHTML = '';
    totals.sort((a, b) => b.total - a.total).forEach(p => {
      const curWindow = last7Plat[p.id] || 0;
      const prevWindow = prev7Plat ? (prev7Plat[p.id] || 0) : null;
      let trendTxt = '—';
      let trendCls = 'neu';
      if (prevWindow != null && prevWindow > 0) {
        const pct = ((curWindow - prevWindow) / prevWindow) * 100;
        trendTxt = (pct >= 0 ? '+' : '') + pct.toFixed(0) + '%';
        trendCls = pct > 0 ? 'up' : (pct < 0 ? 'down' : 'neu');
      } else if (prevWindow === 0 && curWindow > 0) {
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
      // The selector now expresses days directly (14, 30, -1 for all).
      const dateKeys = Object.keys(days).sort();
      let sliced;
      if (rangeRaw > 0) sliced = dateKeys.slice(-rangeRaw);
      else sliced = dateKeys;

      labels = sliced;
      // Update the window-hint subtitle so the user can see which
      // date range this chart actually covers (distinct from the top
      // schedule bar's current-7d window).
      const hintEl = document.getElementById('trendWindowHint');
      if (hintEl && sliced.length > 0) {
        hintEl.textContent = t('trendWindowHint', {
          n: sliced.length,
          from: sliced[0],
          to: sliced[sliced.length - 1],
        });
      } else if (hintEl) {
        hintEl.textContent = '';
      }
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

      // Per-day TOTAL (sum across all platforms for that day). Plotted as
      // a thicker solid white line so the user can compare any single
      // platform's spike against the day's actual total — without this,
      // a spike day shows the platform's value visually exceeding the
      // 7-day MA, which looks like "platform > total" but is just the
      // MA dampening the spike.
      const totals = sliced.map(k => (days[k] || {}).total || 0);
      datasets.push({
        label: t('trendTotal'),
        data: totals,
        borderColor: '#e8ecf4',
        backgroundColor: '#e8ecf433',
        borderWidth: 3,
        pointRadius: 2,
        pointHoverRadius: 5,
        tension: 0.25,
        fill: false,
      });

      // 7-day moving average overlay on the per-day totals — keeps the
      // smoothed-trend signal alongside the raw totals.
      const ma7 = totals.map((_, i) => {
        const start = Math.max(0, i - 6);
        const window = totals.slice(start, i + 1);
        return window.reduce((s, n) => s + n, 0) / window.length;
      });
      datasets.push({
        label: t('trendOverlay'),
        data: ma7,
        borderColor: '#9aa2b8',
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
  const CITY_POINTS = {
    '纽约': [-74.0060, 40.7128],
    '洛杉矶': [-118.2437, 34.0522],
    '布鲁克林': [-73.9442, 40.6782],
    '旧金山-奥克兰-圣何塞': [-122.1500, 37.6000],
    '休斯顿': [-95.3698, 29.7604],
    '芝加哥': [-87.6298, 41.8781],
    '费城': [-75.1652, 39.9526],
    '拉斯维加斯': [-115.1398, 36.1699],
    '奥兰多-代托纳海滩-墨尔本': [-81.3792, 28.5383],
    '西雅图-塔科马': [-122.3321, 47.6062],
    '迈阿密-劳德代尔堡': [-80.1918, 25.7617],
    '波特兰': [-122.6784, 45.5152],
    '圣地亚哥': [-117.1611, 32.7157],
    '布朗克斯': [-73.8648, 40.8448],
    '奥斯汀': [-97.7431, 30.2672],
    '亚特兰大': [-84.3880, 33.7490],
    '圣安东尼奥': [-98.4936, 29.4241],
    '凤凰城': [-112.0740, 33.4484],
    '达拉斯-沃思堡': [-96.7970, 32.7767],
    '杰克逊维尔': [-81.6557, 30.3322],
    '夏洛特': [-80.8431, 35.2271],
    '萨克拉门托-斯托克顿-莫德斯托': [-121.4944, 38.5816],
    '法拉盛': [-73.8331, 40.7675],
    '圣何塞': [-121.8863, 37.3382],
    '坦帕-圣彼得堡（萨拉索塔）': [-82.4572, 27.9506],
    '华盛顿特区（黑格斯敦）': [-77.0369, 38.9072],
    '印第安纳波利斯': [-86.1581, 39.7684],
    '丹佛': [-104.9903, 39.7392],
    '巴尔的摩': [-76.6122, 39.2904],
    '圣路易斯': [-90.1994, 38.6270],
    '弗吉尼亚海滩': [-75.9780, 36.8529],
    '奥克兰': [-122.2711, 37.8044],
    '埃尔帕索': [-106.4850, 31.7619],
    '哥伦布': [-82.9988, 39.9612],
    '路易斯维尔': [-85.7585, 38.2527],
    '俄克拉何马城': [-97.5164, 35.4676],
    '弗雷斯诺-维萨利亚': [-119.7871, 36.7378],
    '图森（塞拉维斯塔）': [-110.9747, 32.2226],
    '波士顿-曼彻斯特': [-71.0589, 42.3601],
    '斯塔滕岛': [-74.1502, 40.5795],
    '阿尔伯克基-圣菲': [-106.6504, 35.0844],
    '曼哈顿': [-73.9712, 40.7831],
    '皇后区': [-73.7949, 40.7282],
    '长岛': [-73.4129, 40.7891],
    '泽西市': [-74.0431, 40.7178],
    '纽瓦克': [-74.1724, 40.7357],
    '爱迪生': [-74.4121, 40.5187],
    '昆西': [-71.0023, 42.2529],
    '罗克维尔': [-77.1528, 39.0840],
    '匹兹堡': [-79.9959, 40.4406],
    '尔湾': [-117.8265, 33.6846],
    '圣盖博': [-118.1080, 34.0961],
    '蒙特利公园': [-118.1270, 34.0625],
    '阿罕布拉': [-118.1270, 34.0953],
    '罗兰岗': [-117.9053, 33.9761],
    '钻石吧': [-117.8103, 34.0286],
    '核桃': [-117.8653, 34.0203],
    '哈仙达岗': [-117.9687, 33.9931],
    '阿凯迪亚': [-118.0353, 34.1397],
    '罗斯密': [-118.0728, 34.0806],
    '加迪纳': [-118.3089, 33.8883],
    '弗里蒙特': [-121.9886, 37.5485],
    '库比蒂诺': [-122.0322, 37.3229],
    '森尼韦尔': [-122.0363, 37.3688],
    '圣塔克拉拉': [-121.9552, 37.3541],
    '圣马刁': [-122.3255, 37.5630],
    '米尔皮塔斯': [-121.8996, 37.4323],
    '都柏林': [-121.9358, 37.7022],
    '伯克利': [-122.2730, 37.8715],
    '圣拉蒙': [-121.9780, 37.7799],
    '橙县': [-117.8311, 33.7175],
    '安纳海姆': [-117.9145, 33.8366],
    '圣塔安娜': [-117.8677, 33.7455],
    '河滨': [-117.3961, 33.9533],
    '安大略': [-117.6509, 34.0633],
    '贝尔维尤': [-122.2007, 47.6101],
    '比弗顿': [-122.8037, 45.4871],
    '普莱诺': [-96.6989, 33.0198],
    '凯蒂': [-95.8244, 29.7858],
    '糖城': [-95.6349, 29.6197],
    '罗利': [-78.6382, 35.7796],
    '纳什维尔': [-86.7816, 36.1627],
    '孟菲斯': [-90.0490, 35.1495],
    '新奥尔良': [-90.0715, 29.9511],
    '底特律': [-83.0458, 42.3314],
    '克利夫兰': [-81.6944, 41.4993],
    '辛辛那提': [-84.5120, 39.1031],
    '密尔沃基': [-87.9065, 43.0389],
    '明尼阿波利斯': [-93.2650, 44.9778],
    '堪萨斯城': [-94.5786, 39.0997],
    '盐湖城': [-111.8910, 40.7608],
    '檀香山': [-157.8583, 21.3069],
  };

  function cityPoints() {
    const points = { ...CITY_POINTS };
    const cities = state.cityCatalog && state.cityCatalog.cities;
    if (cities) {
      Object.entries(cities).forEach(([name, info]) => {
        const lon = Number(info && info.lon);
        const lat = Number(info && info.lat);
        if (Number.isFinite(lon) && Number.isFinite(lat)) {
          points[name] = [lon, lat];
        }
      });
    }
    return points;
  }

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
    const points = cityPoints();
    const counts = {};
    const cityCounts = {};
    posts.forEach(p => {
      if (!p.state) return;
      const usps = window.I18N && window.I18N.uspsFor(p.state);
      if (!usps) return;
      counts[usps] = (counts[usps] || 0) + 1;
    });
    uniquePostsForPlaceCounts(posts).forEach(p => {
      if (p.city && points[p.city]) {
        cityCounts[p.city] = (cityCounts[p.city] || 0) + 1;
      }
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
    const showCityTip = (event, city, count) => {
      tooltip.innerHTML = `
        <div class="tt-name">${escapeHtml(cityName(city))}</div>
        <div class="tt-count">${count} ${escapeHtml(t('cityPosts'))}</div>
      `;
      tooltip.classList.add('shown');
      tooltip.style.left = (event.clientX + 12) + 'px';
      tooltip.style.top = (event.clientY + 12) + 'px';
    };

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

    const cityEntries = Object.entries(cityCounts)
      .map(([city, count]) => ({ city, count, coord: points[city] }))
      .filter(d => d.coord && projection(d.coord))
      .sort((a, b) => b.count - a.count);
    const maxCity = Math.max(1, ...cityEntries.map(d => d.count));
    const radius = d3.scaleSqrt().domain([1, maxCity]).range([5, 18]);
    const cityLayer = svg.append('g').attr('class', 'city-layer');
    cityLayer.selectAll('circle')
      .data(cityEntries)
      .join('circle')
      .attr('class', 'city-dot')
      .attr('cx', d => projection(d.coord)[0])
      .attr('cy', d => projection(d.coord)[1])
      .attr('r', d => radius(d.count))
      .on('mousemove', (e, d) => showCityTip(e, d.city, d.count))
      .on('mouseleave', hideTip);
    cityLayer.selectAll('text')
      .data(cityEntries.filter(d => d.count >= Math.max(2, maxCity * 0.12)).slice(0, 18))
      .join('text')
      .attr('class', 'city-count')
      .attr('x', d => projection(d.coord)[0])
      .attr('y', d => projection(d.coord)[1] + 3)
      .text(d => d.count);

    // Legend
    const legend = document.createElement('div');
    legend.className = 'legend';
    legend.innerHTML = `<span>0</span><span class="legend-bar"></span><span>${max}</span><span class="city-legend-dot"></span><span>${escapeHtml(t('cityPosts'))}</span>`;
    container.appendChild(legend);
  }

  // ────────────────────────────────────────────────────────
  // REGION TAB
  // ────────────────────────────────────────────────────────
  function renderRegion() {
    // Window hint — Region tab uses posts.json's current 7-day window
    // (same scope as the KPI cards), NOT the longer daily.json history.
    const hintEl = document.getElementById('regionWindowHint');
    if (hintEl && state.data && state.data.meta) {
      hintEl.textContent = t('regionWindowHint', {
        from: state.data.meta.date_from,
        to:   state.data.meta.date_to,
      });
    }
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
        const placePosts = uniquePostsForPlaceCounts(rp);
        const sCounts = {};
        const cCounts = {};
        rp.forEach(p => { if (p.state) sCounts[p.state] = (sCounts[p.state] || 0) + 1; });
        placePosts.forEach(p => { if (p.city) cCounts[p.city] = (cCounts[p.city] || 0) + 1; });
        const top = Object.entries(sCounts).sort((a, b) => b[1] - a[1]).slice(0, 5);
        const topCities = Object.entries(cCounts).sort((a, b) => b[1] - a[1]).slice(0, 8);
        byRegion[r] = { total: rp.length, top_states: Object.fromEntries(top), top_cities: Object.fromEntries(topCities) };
      });
    }

    const grid = document.getElementById('regionGrid');
    grid.innerHTML = '';
    REGIONS.forEach(r => {
      const info = byRegion[r] || { total: 0, top_states: {} };
      const places = Object.entries(info.top_cities || {}).length
        ? Object.entries(info.top_cities || {})
        : Object.entries(info.top_states || {});
      const usingCities = Boolean(Object.entries(info.top_cities || {}).length);
      const maxState = Math.max(1, ...places.map(([, c]) => c));
      const block = document.createElement('div');
      block.className = 'region-block';
      const stateRows = places.length
        ? places.map(([n, c], i) => `
            <div class="state-row">
              <span class="state-name">${escapeHtml(usingCities ? cityName(n) : stateName(n))}</span>
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
    // Build date filter cutoffs from LOCAL date components (toISOString
    // would shift to UTC and break the filter overnight in negative-
    // offset timezones).
    const fmtLocalIso = (d) => {
      const y = d.getFullYear();
      const m = String(d.getMonth() + 1).padStart(2, '0');
      const day = String(d.getDate()).padStart(2, '0');
      return `${y}-${m}-${day}`;
    };
    const now = new Date(); now.setHours(0, 0, 0, 0);
    const yesterday = new Date(now); yesterday.setDate(yesterday.getDate() - 1);
    const isoYesterday = fmtLocalIso(yesterday);
    const last7Cutoff = new Date(now); last7Cutoff.setDate(last7Cutoff.getDate() - 6);
    const isoLast7 = fmtLocalIso(last7Cutoff);
    const latestCompleteIso = (d.meta && d.meta.date_to) || (state.daily && state.daily.meta && state.daily.meta.latest) || isoYesterday;

    const filtered = posts.filter(p => {
      if (f.search && !p.title.toLowerCase().includes(f.search.toLowerCase())) return false;
      if (f.platform && p.platform !== f.platform) return false;
      if (f.region && p.region !== f.region) return false;
      if (f.keyword && !(p.keywords_matched || []).includes(f.keyword)) return false;
      if (f.date) {
        const pd = p.date || '';
        if (f.date === 'today' && pd !== latestCompleteIso) return false;
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
      const placeText = p.city
        ? `${regionName(p.region) || t('unknownRegion')} · ${cityName(p.city)} · ${stateName(p.state) || '—'}`
        : `${regionName(p.region) || t('unknownRegion')} · ${stateName(p.state) || '—'}`;
      el.innerHTML = `
        <div class="post-meta">
          <span class="post-platform" style="background:${platMeta.color}33; color:${platMeta.color}">${escapeHtml(platformName(p.platform))}</span>
          <span class="post-time">${escapeHtml(p.date || '—')}</span>
        </div>
        <div class="post-title">${titleEl}</div>
        <div class="post-region">${escapeHtml(placeText)} ${(p.keywords_matched || []).map(k => `<span class="kw-tag">${escapeHtml(k)}</span>`).join('')}</div>
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
