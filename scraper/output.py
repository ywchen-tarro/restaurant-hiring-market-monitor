"""Aggregate Post objects into the dashboard JSON file.

History is APPENDED on every run (never overwritten) — the dashboard's
trend chart depends on this accumulation.

Writes are atomic (tmp + os.replace) so a crash mid-write can't corrupt
the existing file. If an existing file fails to parse, it's renamed aside
as <name>.json.corrupt-<ts> rather than silently overwritten — this
preserves history we'd otherwise destroy on the next run.
"""

from __future__ import annotations

import json
import logging
import os
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from . import config
from .platforms.base import Post

log = logging.getLogger(__name__)

REGIONS_ORDER = ["东部", "南部", "中部", "西部"]

# Schema-drift thresholds: warn if a previously-active platform drops sharply.
_DROP_RATIO_WARN = 0.30          # current < 30% of prior
_PRIOR_MIN_FOR_DROP_WARN = 20    # only when prior was meaningful
_PRIOR_MIN_FOR_ZERO_WARN = 5     # warn on 0 only if prior had ≥ this


def _load_existing(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        # Preserve the broken file so history isn't lost forever
        try:
            stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
            corrupt = path.with_suffix(f".json.corrupt-{stamp}")
            path.rename(corrupt)
            log.warning(
                "Existing %s did not parse (%s); preserved as %s",
                path, exc, corrupt.name,
            )
        except OSError as rename_exc:
            log.warning(
                "Existing %s did not parse (%s) and could not be preserved (%s)",
                path, exc, rename_exc,
            )
        return {}


def _aggregate(posts: List[Post], days_back: int) -> dict:
    today = date.today()
    date_from = (today - timedelta(days=days_back)).isoformat()
    date_to = today.isoformat()

    plats_counter = Counter(p.platform for p in posts)
    by_platform = {}
    for plat in config.PLATFORMS:
        pid = plat["id"]
        total = plats_counter.get(pid, 0)
        # daily_avg divides by the lookback window; this is the *intended*
        # post rate, not the partial-day-adjusted rate. Document and revisit
        # if/when we move to a per-day time series.
        by_platform[pid] = {
            "total": total,
            "daily_avg": round(total / max(days_back, 1), 2),
        }

    by_region = {}
    for region in REGIONS_ORDER:
        region_posts = [p for p in posts if p.region == region]
        states = Counter(p.state for p in region_posts if p.state)
        by_region[region] = {
            "total": len(region_posts),
            "top_states": dict(states.most_common(5)),
        }
    # surface posts that didn't classify
    unclassified = sum(1 for p in posts if not p.region)

    kw_counter = Counter()
    for p in posts:
        for kw in p.keywords_matched:
            kw_counter[kw] += 1
    by_keyword = dict(kw_counter.most_common(20))

    meta = {
        "last_updated": datetime.now().astimezone().isoformat(timespec="seconds"),
        "scrape_days_back": days_back,
        "date_from": date_from,
        "date_to": date_to,
        "total_posts": len(posts),
        "unclassified_region": unclassified,
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
    """Append the new entry, OR merge with the same-day entry by taking the
    per-platform max. This protects against a partially-failed re-run
    silently replacing a healthier earlier run."""
    history = list(existing.get("history", []))
    if not history or history[-1].get("run_date") != new_entry["run_date"]:
        history.append(new_entry)
        return history

    prev = history[-1]
    merged_by_platform = {}
    pids = set(prev.get("by_platform", {})) | set(new_entry["by_platform"])
    for pid in pids:
        merged_by_platform[pid] = max(
            prev.get("by_platform", {}).get(pid, 0),
            new_entry["by_platform"].get(pid, 0),
        )
    merged = {
        "run_date": new_entry["run_date"],
        "period": new_entry["period"],
        "by_platform": merged_by_platform,
        "total": sum(merged_by_platform.values()),
    }
    history[-1] = merged
    return history


def _compute_warnings(
    new_history: List[dict],
    diagnostics: Optional[Dict[str, dict]],
) -> List[str]:
    """Detect signs of scrape failure / schema drift."""
    warnings: List[str] = []
    if not new_history:
        return warnings

    cur = new_history[-1]["by_platform"]
    prev = new_history[-2]["by_platform"] if len(new_history) >= 2 else {}

    for pid, count in cur.items():
        prev_count = prev.get(pid, 0)
        if count == 0 and prev_count >= _PRIOR_MIN_FOR_ZERO_WARN:
            warnings.append(
                f"{pid}: dropped to 0 (prior: {prev_count}) — possible scrape failure or schema drift"
            )
        elif (
            prev_count >= _PRIOR_MIN_FOR_DROP_WARN
            and count < prev_count * _DROP_RATIO_WARN
        ):
            warnings.append(
                f"{pid}: dropped >70% ({prev_count} → {count}) — investigate"
            )

    if diagnostics:
        for pid, diag in diagnostics.items():
            status = diag.get("status")
            if status == "error":
                warnings.append(f"{pid}: scraper raised {diag.get('exception', 'Exception')}")
            elif status == "not_implemented":
                continue
            else:
                unparsed = diag.get("dropped_unparseable_date", 0)
                rows = diag.get("rows_parsed", 0)
                if rows > 0 and unparsed / rows > 0.10:
                    warnings.append(
                        f"{pid}: {unparsed}/{rows} posts had unparseable dates — date format may have changed"
                    )

    return warnings


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def write_posts_json(
    posts: List[Post],
    days_back: int,
    out_path: Optional[Path] = None,
    diagnostics: Optional[Dict[str, dict]] = None,
) -> Path:
    out_path = out_path or config.OUTPUT_JSON

    existing = _load_existing(out_path)
    aggregated = _aggregate(posts, days_back)
    new_history = _merge_history(existing, _new_history_entry(posts, days_back))

    aggregated["meta"]["warnings"] = _compute_warnings(new_history, diagnostics)
    if diagnostics:
        aggregated["meta"]["diagnostics"] = diagnostics

    output = {
        **aggregated,
        "history": new_history,
        "posts": [p.to_dict() for p in posts],
    }

    _atomic_write(
        out_path,
        json.dumps(output, ensure_ascii=False, indent=2),
    )
    log.info(
        "Wrote %d posts to %s (history: %d entries, warnings: %d)",
        len(posts), out_path, len(new_history), len(aggregated["meta"]["warnings"]),
    )
    return out_path
