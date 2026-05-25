# Restaurant Hiring Market Monitor

> Is the US restaurant market expanding or cooling right now?

Twice a week, this project counts how many restaurant-job posts appear on the five largest Chinese-language US job boards. More posts → restaurants are growing → more demand in the market. Fewer posts → cooling. The number is a fast, free, weekly read on a market segment that no public dataset tracks at this resolution.

**Live dashboard:** https://ywchen-tarro.github.io/restaurant-hiring-market-monitor/

---

## How to read it

| Card | What it tells you |
|---|---|
| **本期总帖数** | Total restaurant-job posts in the trailing 7 days, plus the % delta vs. the previous run. |
| **招聘最活跃地区** | Region (East/South/Midwest/West) with the highest volume, and its top state/city. Where outbound efforts will land warmest right now. |
| **最活跃平台** | Which board carried the most posts this period. Useful when a platform's audience shifts. |
| **市场信号** | Count of platforms with ≥20% week-over-week change. Green = rising, orange = cooling. |
| **趋势 tab** | Multi-line chart of each platform's weekly count. The story is in the slopes. |
| **地区分布 tab** | Per-region cards with top-5 state breakdowns. |
| **帖子详情 tab** | Filterable list of the individual posts the count comes from. |

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

| Platform | URL | Status |
|---|---|---|
| 168worker | https://www.168worker.com/list/1_0 | Disabled — anti-bot block (see [ROADMAP.md](./ROADMAP.md)) |
| 华人街生活网 | https://www.usahuarenjie.com/category-catid-251.html | ✅ Active |
| 500work | https://www.500work.com/ | Disabled — anti-bot block |
| 北美餐饮通 | https://uscanyin.com/en/jobs | Disabled — pagination scale (~4,500 pages) needs custom handling |
| 纽约工作网 | https://niuyuegongzuo.com/ | ✅ Active |

The plan to unblock the disabled platforms — including which anti-bot tools to try in what order, and how to add new ones — lives in [ROADMAP.md](./ROADMAP.md).

A post is counted as a restaurant job when its title matches at least one **strong** keyword — a clear venue (`餐馆`, `火锅`, `日料`, `奶茶`) or a restaurant-specific role (`炒锅`, `油锅`, `厨师`, `企台`, `打杂`, `服务员`). Ambiguous terms (`招聘`, `招人`, `请人`, `前台`, `收银`) appear in many other industries and don't qualify a post on their own.

Each post is classified into one of four US regions: 东部 / 南部 / 中部 / 西部, by state-token match against ~150 city/state names (Simplified + Traditional Chinese + English).

### Sample output (`docs/data/posts.json`)

```json
{
  "meta": {
    "last_updated": "2026-05-25T15:23:14-07:00",
    "date_from": "2026-05-18",
    "date_to": "2026-05-25",
    "total_posts": 150,
    "warnings": []
  },
  "by_platform": {
    "usahuarenjie":  { "total": 32,  "daily_avg": 4.57 },
    "niuyuegongzuo": { "total": 118, "daily_avg": 16.86 }
  },
  "by_region": {
    "东部": { "total": 131, "top_states": { "法拉盛": 38, "长岛": 26, "上州": 19 } },
    "西部": { "total":  14, "top_states": { "洛杉矶": 4, "旧金山": 4, "圣何塞": 2 } }
  },
  "history": [
    { "run_date": "2026-05-25", "total": 150, "by_platform": { "usahuarenjie": 32, "niuyuegongzuo": 118 } }
  ],
  "posts": [ /* … one entry per matched post … */ ]
}
```

The dashboard reads this file at load time. The trend chart uses the `history` array, which **accumulates over runs** (it isn't overwritten).

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
