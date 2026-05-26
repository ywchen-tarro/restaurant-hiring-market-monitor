# Restaurant Hiring Market Monitor

> Is the US restaurant market expanding or cooling right now?

Twice a week, this project counts how many restaurant-job posts appear on the five largest Chinese-language US job boards. More posts → restaurants are growing → more demand in the market. Fewer posts → cooling. The number is a fast, free, weekly read on a market segment that no public dataset tracks at this resolution.

**Live dashboard:** https://ywchen-tarro.github.io/restaurant-hiring-market-monitor/

---

## How to read it

Top of page is a row of five KPI cards (English / 中文 labels swap with the language toggle):

| Card | What it tells you |
|---|---|
| **Posts this period / 本期总帖数** | Total restaurant-job posts in the trailing 7 days (unique, after 168↔500work mirror dedup). Sub-line shows the % delta vs. the previous run. |
| **Today's posts / 今日帖数** | Posts dated today (per their source listing date), compared to the 7-day average. Green when at/above average; orange when below. |
| **Most active platform / 最活跃平台** | Which board carried the most posts this period. Useful when a platform's audience shifts. |
| **Most active region / 招聘最活跃地区** | Region (East / South / Midwest / West) with the highest volume, and its top state/city. Where outbound efforts will land warmest right now. |
| **Market signal / 市场信号** | Count of platforms with ≥20% week-over-week change. Green when more are rising than cooling; orange when more are cooling. |

And four tabs below the KPI row:

| Tab | What's there |
|---|---|
| **Overview / 概览** | GitHub-style 35-day heatmap of post dates; platform list with per-platform deltas; platform-share donut. |
| **Trend / 趋势** | Daily post-volume chart (one line per platform) with a 7-day moving-average overlay on the total. Drives off `daily.json`. |
| **Regions / 地区分布** | US choropleth map (D3 + us-atlas) colored by per-state post count, plus per-region cards with top-5 state breakdowns. |
| **Posts / 帖子详情** | Filterable post list — search by title, filter by platform, region, keyword, and date (Today / Yesterday / Last 7 days). Each row links to the source listing. |

### What it is NOT

- Not a full labor-market index (no JOLTS/BLS data).
- Not seasonally adjusted.
- Not a comprehensive census — five boards skew **Chinese-American restaurant operators**. The signal generalizes to that segment well, but isn't representative of all US restaurants.
- A drop on **168worker.com** alone reflects platform attrition (their audience is migrating elsewhere), not necessarily a market change. Cross-check against the other boards.

### Who this is for

A Growth team uses this to:
1. **Time outbound pushes** into regions that are heating up.
2. **Spot cooling early** — when the signal drops two runs in a row, the segment is softening.
3. **Skip slow weeks** — no point launching campaigns when volume is at a local minimum.

---

## What it tracks

| Platform | URL | Transport |
|---|---|---|
| 168worker | https://www.168worker.com/list/1_0 | `curl_cffi` (chrome120 TLS) |
| 华人街生活网 | https://www.usahuarenjie.com/category-catid-251.html | `requests` |
| 500work | https://www.500work.com/ | `curl_cffi` (chrome120 TLS) |
| 北美餐饮通 | https://uscanyin.com/en/jobs | `requests` (30s timeout) |
| 纽约工作网 | https://niuyuegongzuo.com/ | `requests` |

All five platforms are active. **168worker and 500work share the same CMS / post database** — identical post IDs cross-listed on both. The aggregate `total_posts` overcounts because of this; see [ROADMAP.md](./ROADMAP.md) for the cross-platform deduplication follow-up. Per-platform breakdowns on the dashboard are accurate.

For the anti-bot strategy (TLS fingerprinting via `curl_cffi`, why it was needed, and what to try next) and how to add new platforms — see [ROADMAP.md](./ROADMAP.md).

A post is counted as a restaurant job when its title matches at least one **strong** keyword — a clear venue (`餐馆`, `火锅`, `日料`, `奶茶`) or a restaurant-specific role (`炒锅`, `油锅`, `厨师`, `企台`, `打杂`, `服务员`). Ambiguous terms (`招聘`, `招人`, `请人`, `前台`, `收银`) appear in many other industries and don't qualify a post on their own.

Each post is classified into one of four US regions: 东部 / 南部 / 中部 / 西部, by state-token match against ~150 city/state names (Simplified + Traditional Chinese + English).

### Data files

| File | Purpose |
|---|---|
| [`docs/data/posts.json`](./docs/data/posts.json) | Current 7-day window: aggregate counts, per-run history log, full list of posts. The dashboard reads this. |
| [`docs/data/daily.json`](./docs/data/daily.json) | Per-day time series that grows across runs. Analytics-friendly (load into pandas / a notebook for moving averages, regressions, etc.). |

Full schemas and loading examples: see [`docs/data/README.md`](./docs/data/README.md).

### Sample output (`docs/data/posts.json`)

```json
{
  "meta": {
    "last_updated": "2026-05-25T21:27:00-07:00",
    "scrape_days_back": 7,
    "date_from": "2026-05-19",
    "date_to":   "2026-05-25",
    "total_posts":  340,
    "unique_posts": 285,
    "duplicate_count": 55,
    "warnings": []
  },
  "by_platform": {
    "168worker":     { "total": 59, "daily_avg": 8.43 },
    "usahuarenjie":  { "total": 33, "daily_avg": 4.71 },
    "500work":       { "total": 59, "daily_avg": 8.43 },
    "uscanyin":      { "total": 70, "daily_avg": 10.00 },
    "niuyuegongzuo": { "total": 119, "daily_avg": 17.00 }
  },
  "by_region": {
    "东部": { "total": 213, "top_states": { "法拉盛": 51, ... } },
    "南部": { "total":  22, "top_states": { "亚特兰大": 5, ... } },
    "中部": { "total":  10, "top_states": { "芝加哥": 3 } },
    "西部": { "total":  29, "top_states": { "洛杉矶": 8, ... } }
  },
  "history": [
    {
      "run_date":  "2026-05-25",
      "by_platform": { "168worker": 59, "usahuarenjie": 33, "500work": 59, "uscanyin": 70, "niuyuegongzuo": 119 },
      "total":        340,
      "total_unique": 285
    }
  ],
  "posts": [ /* … one entry per matched post in the current 7-day window … */ ]
}
```

The dashboard reads `posts.json` for the current window + per-run history, and `daily.json` (which **accumulates over runs**) for the per-day Trend chart and the 35-day heatmap.

---

## Setup

**Requirements:** macOS, Python 3.9+, git, [`gh` CLI](https://cli.github.com/) authenticated to a GitHub account.

```bash
git clone https://github.com/<your-username>/restaurant-hiring-market-monitor.git
cd restaurant-hiring-market-monitor

# Install pinned Python dependencies
python3 -m pip install -r scraper/requirements.txt

# Configure git to use gh's stored token (needed so the scheduled run can push)
gh auth setup-git

# First run — manual
bash run.sh
```

### Install the schedule (Mon + Thu 09:00 local time)

```bash
bash install_schedule.sh
```

The installer writes two launchd plists to `~/Library/LaunchAgents/`:
- **scraper** — Mon + Thu 09:00 → runs the scrape and pushes the JSON
- **watchdog** — daily 10:00 → checks the heartbeat and pops a macOS notification if no successful run in 4+ days

> **One manual step the first time:** if the project lives in iCloud Drive, macOS blocks launchd-spawned processes from reading it. After `install_schedule.sh`, grant **Full Disk Access** to `/bin/bash`:
> System Settings → Privacy & Security → Full Disk Access → `+` → Cmd+Shift+G → type `/bin/bash` → toggle on. The installer prints these instructions when it runs.

Trigger a test run anytime:

```bash
launchctl start local.restaurant-hiring-monitor
tail -f logs/scraper.log
```

### Languages

The dashboard ships in **English by default** with a one-click toggle to **Chinese (Simplified)**. The toggle sits in the top-right of the header (`EN` ↔ `中文`); your preference is saved in localStorage and persists across visits. Post titles always stay in their source language (they're scraped from Chinese-language boards); region/state/platform labels are translated.

### Mobile

The dashboard is responsive down to phone widths (≥320px). Breakpoints:
- **≥960px**: full desktop — 5 KPI cards in a row, side-by-side panels
- **640-960px**: tablet — 2-column KPIs, stacked panels
- **<640px**: phone — 1-column KPIs, horizontally-scrollable tabs, stacked filters, compact charts
- **<380px**: super-narrow — drops the logo badge and "last run" status text to save space

### Monitoring — is it still running?

Three layers, in increasing effort:

1. **macOS Notification Center** — every scrape (Mon + Thu) fires a banner: `Hiring Monitor: OK · 150 posts · pushed` on success, `Hiring Monitor: FAIL` on failure. The daily watchdog fires `Hiring Monitor: STALE` if no successful run in 4+ days (catches the case where the Mac was asleep through the scheduled window).
2. **Status command** — `bash check-health.sh` prints last successful run, time since, warnings, per-platform diagnostics, launchd job status, recent log tails, and git state on one screen.
3. **Dashboard banner** — if `meta.last_updated` is >4 days old when someone opens the dashboard, an orange banner reads `数据已 N 天未更新 — 请检查 launchd 调度`.

Per-platform health (rows parsed, posts dropped, dropped-by-reason) is written to `meta.diagnostics` in `posts.json` on every run, so a silent schema-drift on one platform shows up immediately.

### View locally during development

The dashboard fetches `data/posts.json` over HTTP, so `file://` won't work:

```bash
cd docs && python3 -m http.server 8080
# open http://localhost:8080
```

---

## Tuning

All knobs live in **`scraper/config.py`**:

- `SCRAPE_DAYS_BACK` — lookback window (default 7).
- `DELAY_MIN` / `DELAY_MAX` — polite seconds between HTTP requests.
- `MAX_RETRIES` — per-URL retry count.
- `MAX_PAGES_PER_PLATFORM` — pagination cap.
- `PLATFORMS` — list of platforms; `"enabled": false` toggles one off.
- `USER_AGENTS` — desktop-only UA rotation pool.

---

## Adding a platform

1. Add an entry to `PLATFORMS` in `scraper/config.py` with `"enabled": true`.
2. Create `scraper/platforms/<id>.py` exporting a `Scraper` class that subclasses `BasePlatformScraper`. You only need to implement two methods:
   - `page_url(page_num: int) -> str` — build the listing-page URL.
   - `parse_page(html: str, page_num: int) -> List[Post]` — extract posts. Wrap per-row parsing in a try/except so one broken row doesn't kill the page.
3. Optionally override `fetch_page` if the platform needs special HTTP handling (e.g., a different client, cookies, JS rendering).
4. Add the new platform's `id` to `scrape.py`'s `PLATFORM_MODULE` map.
5. Add the platform's display metadata (color, name) to `docs/assets/dashboard.js`'s `PLATFORMS` array.

The base class handles pagination, the 7-day cutoff, the keyword filter, region classification, deduplication, and diagnostics.

---

## Project layout

```
scraper/
├── scrape.py              Entry point — drives all enabled platforms
├── config.py              Tunables (single source of truth)
├── http_client.py         polite_get() — UA rotation, delays, retries
├── regions.py             4-region classifier (state/city → 东部/南部/中部/西部)
├── keywords.py            Strong (venue/role) + weak (ambiguous) keyword sets
├── sanitize.py            PII redaction (phone numbers)
├── date_parser.py         Chinese relative + absolute date formats
├── output.py              Atomic write of posts.json, history append, schema-drift warnings
└── platforms/
    ├── base.py            BasePlatformScraper, Post dataclass
    ├── niuyuegongzuo.py
    └── usahuarenjie.py

docs/                      GitHub Pages source
├── index.html
├── assets/
│   ├── styles.css
│   └── dashboard.js
└── data/posts.json        Scraper output (committed)

run.sh                     Scrape → commit → push
install_schedule.sh        Installs the launchd timer
local.restaurant-hiring-monitor.plist  ← the launchd job
```

---

## How a run works

1. `launchd` fires `run.sh` at 09:00 on Mon/Thu.
2. `scraper.scrape` iterates enabled platforms. Each `Scraper.run()` paginates from page 1 until either (a) a post date falls outside `SCRAPE_DAYS_BACK`, (b) two consecutive empty pages, or (c) `MAX_PAGES_PER_PLATFORM`.
3. For each parsed post: drop if date doesn't parse, drop if outside the window, drop if no strong keyword. Otherwise sanitize the title, classify the region, and add to the output set.
4. `output.write_posts_json` aggregates by platform/region/keyword, **atomically** replaces `docs/data/posts.json`, and **appends** a new entry to `history[]`.
5. `run.sh` commits and pushes the JSON. GitHub Pages auto-rebuilds within ~1 minute.

If a platform raises an exception, the other platforms still produce their portion of the JSON. Per-platform health, error states, and drop diagnostics are written to `meta.diagnostics`. Schema drift (e.g., 0 posts when previous run had ≥5) emits an entry in `meta.warnings`, which the dashboard surfaces as a banner.

---

## License

MIT.
