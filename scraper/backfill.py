"""One-off backfill scraper.

Runs a regular scrape but with a custom (longer) lookback window. The
resulting per-day aggregation is merged into `docs/data/daily.json`
without overwriting days that already have data — so backfilling never
erases your current series.

Usage:
    python3 -m scraper.backfill --days 14
    python3 -m scraper.backfill --days 30 --max-pages 30
    python3 -m scraper.backfill --days 14 --only 168worker,500work
    python3 -m scraper.backfill --days 14 --preserve-existing  (default)
    python3 -m scraper.backfill --days 14 --overwrite-existing

Caveats:
  - uscanyin lists dates as "1 hour ago" / "yesterday" — anything older
    than 2 days collapses to today/yesterday in our parser. Backfilling
    uscanyin past 2 days does NOT recover earlier-dated posts. Use
    --only to skip it for backfills > 2 days.
  - 168worker and 500work share an upstream database; they'll backfill
    identical post sets. Either one is enough.

The original `daily.json` series is preserved: pre-existing day entries
are only overwritten with `--overwrite-existing`. By default, backfill
only ADDS missing days.
"""

from __future__ import annotations

import argparse
import importlib
import json
import logging
import sys
from datetime import date, timedelta
from typing import Dict, List

from . import config
from .output import (
    _atomic_write, _compute_daily, _load_existing,
    write_posts_json,
)
from .platforms.base import Post
from .scrape import PLATFORM_MODULE, _load_scraper

log = logging.getLogger("backfill")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Backfill historical days into daily.json")
    parser.add_argument("--days", type=int, default=14,
                        help="Lookback window in days (default: 14)")
    parser.add_argument("--max-pages", type=int, default=None,
                        help="Override per-platform max_pages (default: keep platform default, "
                             "or use config.MAX_PAGES_PER_PLATFORM)")
    parser.add_argument("--only", type=str, default="",
                        help="Comma-separated platform IDs to include (default: all enabled)")
    parser.add_argument("--skip", type=str, default="",
                        help="Comma-separated platform IDs to skip")
    parser.add_argument("--overwrite-existing", action="store_true",
                        help="Overwrite already-recorded days in daily.json (default: only add missing)")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    only_set = {s.strip() for s in args.only.split(",") if s.strip()}
    skip_set = {s.strip() for s in args.skip.split(",") if s.strip()}

    enabled = [p for p in config.PLATFORMS if p.get("enabled", False)]
    if only_set:
        enabled = [p for p in enabled if p["id"] in only_set]
    enabled = [p for p in enabled if p["id"] not in skip_set]

    log.info("Backfill: days=%d, platforms=%s", args.days, [p["id"] for p in enabled])

    all_posts: List[Post] = []
    for plat in enabled:
        pid = plat["id"]
        ScraperCls = _load_scraper(pid)
        if not ScraperCls:
            log.warning("Skipping %s (no scraper class)", pid)
            continue
        try:
            scraper = ScraperCls()
            if args.max_pages is not None:
                scraper.max_pages = args.max_pages
            posts = scraper.run(days_back=args.days)
            log.info("[%s] backfilled %d posts", pid, len(posts))
            all_posts.extend(posts)
        except Exception as exc:  # noqa: BLE001
            log.exception("[%s] backfill failed: %s", pid, exc)

    # Merge into daily.json
    daily_path = config.DAILY_JSON
    existing = _load_existing(daily_path) if daily_path.exists() else {}
    existing_days = existing.get("days", {})

    new_days = _compute_daily(all_posts)

    if args.overwrite_existing:
        merged = {**existing_days, **new_days}
    else:
        # Only add days that aren't already recorded
        merged = dict(existing_days)
        added = 0
        for d, info in new_days.items():
            if d not in merged:
                merged[d] = info
                added += 1
        log.info("Added %d new days; %d already present (preserved)",
                 added, len(new_days) - added)

    from datetime import datetime as _dt
    output = {
        "meta": {
            "schema_version": 1,
            "last_updated": _dt.now().astimezone().isoformat(timespec="seconds"),
            "day_count": len(merged),
            "earliest": min(merged) if merged else None,
            "latest": max(merged) if merged else None,
            "backfilled_at": _dt.now().astimezone().isoformat(timespec="seconds"),
        },
        "days": dict(sorted(merged.items())),
    }
    _atomic_write(daily_path, json.dumps(output, ensure_ascii=False, indent=2))

    print()
    print("=" * 60)
    print(f"Backfill complete. Days in daily.json: {len(merged)}")
    print(f"  earliest: {output['meta']['earliest']}")
    print(f"  latest:   {output['meta']['latest']}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
