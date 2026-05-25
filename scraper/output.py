"""Aggregate Post objects into the dashboard JSON file.

History is APPENDED on every run (never overwritten) — the dashboard's
trend chart depends on this accumulation.
"""

from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, List, Optional

from . import config
from .platforms.base import Post

log = logging.getLogger(__name__)

REGIONS_ORDER = ["东部", "南部", "中部", "西部"]


def _load_existing(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("Could not parse existing %s (%s); starting fresh", path, exc)
        return {}


def _aggregate(posts: List[Post], days_back: int) -> dict:
    today = date.today()
    date_from = (today - timedelta(days=days_back)).isoformat()
    date_to = today.isoformat()

    # by_platform
    by_platform = {}
    plats_counter = Counter(p.platform for p in posts)
    for plat in config.PLATFORMS:
        pid = plat["id"]
        total = plats_counter.get(pid, 0)
        by_platform[pid] = {
            "total": total,
            "daily_avg": round(total / max(days_back, 1), 2),
        }

    # by_region
    by_region = {}
    for region in REGIONS_ORDER:
        region_posts = [p for p in posts if p.region == region]
        states = Counter(p.state for p in region_posts if p.state)
        by_region[region] = {
            "total": len(region_posts),
            "top_states": dict(states.most_common(5)),
        }

    # by_keyword
    kw_counter = Counter()
    for p in posts:
        for kw in p.keywords_matched:
            kw_counter[kw] += 1
    by_keyword = dict(kw_counter.most_common(20))

    # meta
    meta = {
        "last_updated": datetime.now().isoformat(timespec="seconds"),
        "scrape_days_back": days_back,
        "date_from": date_from,
        "date_to": date_to,
        "total_posts": len(posts),
    }

    return {
        "meta": meta,
        "by_platform": by_platform,
        "by_region": by_region,
        "by_keyword": by_keyword,
    }


def _new_history_entry(posts: List[Post], days_back: int) -> dict:
    today = date.today()
    date_from = (today - timedelta(days=days_back)).isoformat()
    plats_counter = Counter(p.platform for p in posts)
    return {
        "run_date": today.isoformat(),
        "period": f"{date_from} ~ {today.isoformat()}",
        "by_platform": {
            plat["id"]: plats_counter.get(plat["id"], 0)
            for plat in config.PLATFORMS
        },
        "total": len(posts),
    }


def _merge_history(existing: dict, new_entry: dict) -> List[dict]:
    history = list(existing.get("history", []))
    # If the most-recent entry is the same calendar day, replace it (avoid
    # double-counting on a same-day re-run); otherwise append.
    if history and history[-1].get("run_date") == new_entry["run_date"]:
        history[-1] = new_entry
    else:
        history.append(new_entry)
    return history


def write_posts_json(
    posts: List[Post],
    days_back: int,
    out_path: Optional[Path] = None,
) -> Path:
    out_path = out_path or config.OUTPUT_JSON
    out_path.parent.mkdir(parents=True, exist_ok=True)

    existing = _load_existing(out_path)
    aggregated = _aggregate(posts, days_back)
    new_history = _merge_history(existing, _new_history_entry(posts, days_back))

    output = {
        **aggregated,
        "history": new_history,
        "posts": [p.to_dict() for p in posts],
    }

    out_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log.info(
        "Wrote %d posts to %s (history: %d entries)",
        len(posts), out_path, len(new_history),
    )
    return out_path
