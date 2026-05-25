# Restaurant Hiring Market Monitor

A lightweight monitoring system that tracks restaurant-job posting volume across major Chinese-language job boards in the US. Restaurant hiring activity is a leading signal for restaurant business health — when restaurants post more jobs, they're growing; when posting volume drops, the market is cooling.

The system runs locally on a schedule, scrapes posting counts across five platforms, and publishes a dashboard via GitHub Pages.

## What it tracks

Five Chinese-language job platforms with significant restaurant-job coverage:

| Platform | URL | Notes |
|---|---|---|
| 168worker | https://www.168worker.com/list/1_0 | Historical baseline; declining volume |
| 华人街生活网 | https://www.usahuarenjie.com/category-catid-251.html | National coverage |
| 500work | https://www.500work.com/ | All 50 states |
| 北美餐饮通 | https://uscanyin.com/en/jobs | Restaurant-only |
| 纽约工作网 | https://niuyuegongzuo.com/ | NY-focused |

Restaurant posts are identified by keyword matching against titles (`餐馆`, `炒锅`, `服务员`, `打杂`, etc., in both simplified and traditional Chinese). Each post is classified into a US region (East / South / Midwest / West) by state.

## Architecture

```
Mac (local)
├── launchd timer (Mon + Thu 09:00)
│     ↓
├── scraper/scrape.py (Python)
│     ↓
├── docs/data/posts.json  ← scraper output
│     ↓ git push
└── GitHub (public repo)
      ↓
      GitHub Pages → static dashboard
```

No backend, no database, no GitHub Actions. Just a Python scraper that updates a JSON file on a cron-like schedule, commits it, and pushes. The dashboard is static HTML/CSS/JS that reads the JSON at page load.

## Setup

**Requirements:** macOS, Python 3.9+, git, [`gh` CLI](https://cli.github.com/) authenticated.

```bash
# Clone
git clone https://github.com/<your-username>/restaurant-hiring-market-monitor.git
cd restaurant-hiring-market-monitor

# Install Python dependencies
python3 -m pip install -r scraper/requirements.txt

# First run — manual
bash run.sh
```

**Install the schedule** (Mon + Thu 09:00 local time):

```bash
bash install_schedule.sh
```

**Trigger a test run** anytime:

```bash
launchctl start local.restaurant-hiring-monitor
```

Logs land in `logs/scraper.log` and `logs/scraper_error.log`.

## View the dashboard locally

```bash
cd docs && python3 -m http.server 8080
# open http://localhost:8080
```

(Opening `index.html` via `file://` is blocked by CORS — the dashboard fetches `data/posts.json` and needs a real HTTP server.)

## Tuning

All knobs live in **`scraper/config.py`**:

- `SCRAPE_DAYS_BACK` — how far back each run looks (default 7)
- `DELAY_MIN` / `DELAY_MAX` — polite delay between requests
- `MAX_RETRIES` — per-request retry count
- `PLATFORMS` — list of platforms (id, name, color, base URL, pagination style)
- `USER_AGENTS` — UA pool to rotate through

## Project layout

```
scraper/
├── scrape.py              Entry point — drives all platforms
├── config.py              All tunables
├── http_client.py         polite_get(), UA rotation, retries
├── regions.py             Region/state mapping (East/South/Midwest/West)
├── keywords.py            Restaurant keyword list + matcher
├── output.py              Writes docs/data/posts.json, appends history
└── platforms/
    ├── base.py            BasePlatformScraper
    ├── niuyuegongzuo.py
    ├── usahuarenjie.py
    ├── _168worker.py
    ├── _500work.py
    └── uscanyin.py

docs/                      GitHub Pages source
├── index.html
├── assets/
│   ├── styles.css
│   └── dashboard.js
└── data/posts.json        Scraper output

run.sh                     Scrape → commit → push
install_schedule.sh        Installs the launchd timer
local.restaurant-hiring-monitor.plist
```

## How a run works

1. For each platform in `config.PLATFORMS`, paginate from page 1 until either the post dates fall outside the lookback window or the page yields nothing new.
2. For each post: extract title, date, location, URL; classify region/state; check keywords. Drop non-restaurant posts.
3. Aggregate by platform, region, and keyword.
4. Append a new entry to `history[]` in `posts.json` (the trend chart uses the history).
5. `git commit` + `git push`. GitHub Pages auto-rebuilds within ~1 minute.

## License

MIT
