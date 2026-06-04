# Data files

Three files live here. All are committed to git and refreshed on every scrape.

## `posts.json`

The dashboard's source of truth. Holds the **current** scrape window
(the trailing 7 days from the last run) plus a per-run history log.

```jsonc
{
  "meta": {
    "last_updated": "2026-05-25T16:56:04-07:00",
    "scrape_days_back": 7,
    "date_from": "2026-05-18",
    "date_to":   "2026-05-25",
    "total_posts":   369,    // raw count, with mirror-group duplicates
    "unique_posts":  310,    // collapses 168↔500work duplicates
    "duplicate_count": 59,
    "unclassified_region": 15,
    "warnings":     [],      // schema-drift alerts
    "diagnostics":  { /* per-platform: rows_parsed, dropped_*, … */ }
  },

  "by_platform": {
    "168worker":     { "total": 59,  "daily_avg": 8.43 },
    "usahuarenjie":  { "total": 33,  "daily_avg": 4.71 },
    "500work":       { "total": 59,  "daily_avg": 8.43 },
    "uscanyin":      { "total": 99,  "daily_avg": 14.14 },
    "us168":         { "total": 119, "daily_avg": 17.00 }
  },

  "by_region": {
    "东部": { "total": 221, "top_states": { "法拉盛": 51, ... } },
    "南部": { "total": 25,  "top_states": { ... } },
    "中部": { "total": 12,  "top_states": { ... } },
    "西部": { "total": 30,  "top_states": { ... } }
  },

  "by_keyword": {
    "炒锅": 64,
    "招聘": 56,
    /* … top 20 keyword hits … */
  },

  "history": [
    {
      "run_date": "2026-05-25",
      "period":   "2026-05-18 ~ 2026-05-25",
      "by_platform": { /* raw counts per platform */ },
      "total":        369,
      "total_unique": 310
    }
    /* one entry per run; append-only across days, max-merged within a day */
  ],

  "posts": [
    {
      "id":       "168worker_307421",
      "platform": "168worker",
      "title":    "请熟手包小笼包",
      "date":     "2026-05-25",
      "region":   "东部",
      "state":    "曼哈顿",
      "keywords_matched": ["师傅", "炒锅"],
      "url":      "https://www.168worker.com/page/307421"
    }
    /* … current window only … */
  ]
}
```

Notes:
- `total_posts` includes mirror-group duplicates (168 ↔ 500work). Use `unique_posts` for the headline market signal.
- `posts[]` is **replaced** on every run — only the current 7-day window. For longer history, use `daily.json` below.
- `history[]` is **appended** per run. Same-day re-runs keep whichever had the higher raw total (prevents partial-failure overwrites).

## `daily.json`

Per-calendar-day aggregation that grows over time. Each scrape refreshes
only the days inside the current 7-day window; days older than the
window are frozen as recorded. After 12 months you'll have ~365 day
records, ~50 bytes each — small enough to commit + load in the browser.

```jsonc
{
  "meta": {
    "schema_version": 1,
    "last_updated":   "2026-05-25T20:54:45-07:00",
    "day_count":      8,
    "earliest":       "2026-05-18",
    "latest":         "2026-05-25"
  },
  "days": {
    "2026-05-18": {
      "by_platform": { "168worker": 7, "usahuarenjie": 2, "500work": 7, "us168": 13 },
      "by_region":   { "东部": 22, "西部": 5, "南部": 2 },
      "total":       29
    },
    "2026-05-19": { /* same shape */ },
    /* … one entry per day, sorted ascending … */
  }
}
```

## `cities.json`

City metadata for the regional map. It is regenerated on every scrape from
the scraper's city catalog and the current `posts[]` window, so the front-end
map can use newly recognized cities without hardcoding every point in JS.

```jsonc
{
  "meta": {
    "schema_version": 1,
    "last_updated": "2026-06-04T11:07:34-07:00",
    "city_count": 92,
    "observed_city_count": 18
  },
  "cities": {
    "法拉盛": {
      "en": "Flushing, New York",
      "region": "东部",
      "state": "法拉盛",
      "lon": -73.8331,
      "lat": 40.7675,
      "total": 25
    }
  }
}
```

Notes:
- `city_count` is the number of geocoded city/metro markets available to the scraper.
- `observed_city_count` is how many of those had posts in the current scrape window.
- `total` is the current-window count for that city. Zero-count cities stay in the catalog so future posts can render immediately on the map.

### Caveats for analytics

- **uscanyin's daily distribution is approximate.** uscanyin lists dates as "1 hour ago" / "5 hours ago" / "yesterday"; anything ≤24h resolves to today. The aggregate per-day total for uscanyin is therefore right at the day boundary but flat within a day.
- **168worker ↔ 500work daily counts mirror each other** (same upstream DB). For unique signal, subtract one of them or compute `max(168, 500work)` per day.
- **Weekday seasonality.** Restaurant posting volume is 30–50% lower on Sat/Sun. Apply weekday adjustment before computing trend slopes.

### Loading from Python

```python
import json, pandas as pd
daily = json.load(open("docs/data/daily.json"))
rows = []
for day, info in daily["days"].items():
    for platform, n in info["by_platform"].items():
        rows.append({"date": day, "platform": platform, "posts": n})
df = pd.DataFrame(rows)
df["date"] = pd.to_datetime(df["date"])
df.set_index("date", inplace=True)
```

### Loading from JS (dashboard, notebooks)

```js
const daily = await fetch("./data/daily.json").then(r => r.json());
const series = Object.entries(daily.days).map(([d, info]) => ({
  date: d, total: info.total, ...info.by_platform,
}));
```

## File hygiene

- All generated files are written atomically (`tmp + os.replace`) — a crash during write can't leave a corrupt file.
- If `posts.json` is found unparseable on the next run, it's preserved as `posts.json.corrupt-<timestamp>` rather than silently overwritten.
- The files are committed to git. The current size is small enough for GitHub Pages; estimated daily-series growth is ~1 KB per scrape.
