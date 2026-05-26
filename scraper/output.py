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
import re
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from . import config
from .platforms.base import Post

# 168worker.com and 500work.com share a CMS and republish identical job
# posts. We dedupe ONLY within such "mirror groups" — distinct restaurants
# on an independent platform that happen to share a generic title
# ("熟手炒锅") are different jobs and stay counted as 2.
_KEEP_RE = re.compile(r"[一-鿿豈-﫿A-Za-z0-9]+")

# Each set is a group of platforms that share an upstream database.
# Posts whose normalized title is the same across platforms IN THE SAME
# GROUP are collapsed; everything else stays counted as separate posts.
MIRROR_GROUPS = [
    frozenset({"168worker", "500work"}),
]


def _normalize_title(t: str) -> str:
    if not t:
        return ""
    # Keep CJK Unified Ideographs (U+4E00–U+9FFF) + CJK Compatibility
    # Ideographs (U+F900–U+FAFF) + ASCII alphanumerics. Drops emoji,
    # punctuation, symbols, the redaction placeholder, and whitespace.
    return "".join(_KEEP_RE.findall(t)).lower()


def _mirror_group_id(platform: str):
    for i, group in enumerate(MIRROR_GROUPS):
        if platform in group:
            return i
    return None


def _unique_post_count(posts: List[Post]) -> int:
    """Count distinct posts, collapsing only mirror-group duplicates."""
    counted = 0
    seen_in_group = set()  # (group_id, normalized_title)
    for p in posts:
        nt = _normalize_title(p.title) if p.title else ""
        gid = _mirror_group_id(p.platform)
        if gid is None or not nt:
            # Independent platform OR untitled: count every instance.
            counted += 1
            continue
        key = (gid, nt)
        if key in seen_in_group:
            continue
        seen_in_group.add(key)
        counted += 1
    return counted

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
    # days_back includes today (see base.py for the same convention) so
    # the window spans `today - (days_back-1)` … `today`, i.e. days_back
    # calendar days inclusive.
    date_from = (today - timedelta(days=days_back - 1)).isoformat()
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

    # Cross-platform deduplication for mirror groups (168 ↔ 500work).
    unique_count = _unique_post_count(posts)

    meta = {
        "last_updated": datetime.now().astimezone().isoformat(timespec="seconds"),
        "scrape_days_back": days_back,
        "date_from": date_from,
        "date_to": date_to,
        "total_posts": len(posts),
        "unique_posts": unique_count,
        "duplicate_count": max(0, len(posts) - unique_count),
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
    date_from = (today - timedelta(days=days_back - 1)).isoformat()
    plats_counter = Counter(p.platform for p in posts)
    return {
        "run_date": today.isoformat(),
        "period": f"{date_from} ~ {today.isoformat()}",
        "by_platform": {
            plat["id"]: plats_counter.get(plat["id"], 0)
            for plat in config.PLATFORMS
        },
        "total": len(posts),
        "total_unique": _unique_post_count(posts),
    }


def _merge_history(existing: dict, new_entry: dict) -> List[dict]:
    """Append the new entry, OR replace the same-day entry only when the
    new run is at least as healthy. "Healthy" = higher total.

    Why: a partially-failed re-run could otherwise overwrite a good entry
    with a smaller number, silently corrupting the trend. Conversely, if
    the morning run failed (small total) and a re-run succeeded (big total),
    we want the bigger number. Single-direction replacement keeps each
    history point a real, internally-consistent snapshot — unlike the
    earlier per-platform max-merge which could synthesize a total that
    no single run produced.
    """
    history = list(existing.get("history", []))
    if not history or history[-1].get("run_date") != new_entry["run_date"]:
        history.append(new_entry)
        return history

    prev = history[-1]
    # Compare on raw `total` (always present on both entries). Higher total
    # implies a healthier scrape (more pages parsed). total_unique is just
    # informational; comparing mixed scales would yield false rejections.
    if new_entry.get("total", 0) >= prev.get("total", 0):
        history[-1] = new_entry
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

    # Global signal: if total dropped to 0 while prior run had real data,
    # the most likely cause is a network/auth/config failure across the
    # whole run — not a real "market went to zero". Per-platform checks
    # below catch single-platform failures but only when the prior was
    # large enough to clear the noise floor; this catches the case where
    # several small-volume platforms simultaneously went silent.
    cur_total = sum(cur.values()) if cur else 0
    prev_total = sum(prev.values()) if prev else 0
    if cur_total == 0 and prev_total > 0:
        warnings.append(
            f"all platforms returned 0 posts (prior run: {prev_total}) — "
            f"likely a network, auth, or config failure"
        )

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
                # Lowered from 10% to 5% — even a small fraction of
                # unparseable dates usually indicates a real format change.
                if rows >= 20 and unparsed / rows > 0.05:
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


def _compute_daily(posts: List[Post]) -> Dict[str, dict]:
    """Aggregate posts by ISO date string → per-platform / per-region counts.

    Note: platforms whose source dates are relative (e.g. uscanyin's
    "1 hour ago") all collapse to today, so the daily breakdown for those
    platforms is approximate. The aggregate per-day total is still useful
    as a smoothed signal across platforms with absolute dates.
    """
    days: Dict[str, dict] = {}
    for p in posts:
        if not p.date:
            continue
        bucket = days.setdefault(p.date, {
            "by_platform": {},
            "by_region": {},
            "total": 0,
        })
        bucket["by_platform"][p.platform] = bucket["by_platform"].get(p.platform, 0) + 1
        if p.region:
            bucket["by_region"][p.region] = bucket["by_region"].get(p.region, 0) + 1
        bucket["total"] += 1
    return days


def _merge_daily(
    existing: dict,
    new_days: Dict[str, dict],
    window_start: str,
) -> dict:
    """Refresh days inside the current window; preserve older frozen days.

    `existing` is the prior daily.json contents (or {} on first run).
    `new_days` is what this run computed.
    `window_start` is the ISO date of the first day in the current
    lookback window (inclusive).

    - Days < window_start are kept verbatim (frozen — we've moved past
      their scrape window so we can't refresh them anyway).
    - Days >= window_start come EXCLUSIVELY from the new scrape. If a
      prior in-window day disappeared from new_days, that means the
      current scrape legitimately found zero matching posts for that
      day — preserving the old count would overstate activity (e.g.
      after a keyword-filter correction). The schema-drift warning
      system catches the genuine-failure case where the whole platform
      dropped to 0.
    """
    prior_days = (existing or {}).get("days", {})
    merged_days: Dict[str, dict] = {}

    for d, info in prior_days.items():
        if d < window_start:
            merged_days[d] = info

    for d, info in new_days.items():
        merged_days[d] = info

    return merged_days


def write_daily_json(
    posts: List[Post],
    days_back: int,
    out_path: Optional[Path] = None,
) -> Path:
    """Write/refresh the per-day time series."""
    out_path = out_path or config.DAILY_JSON
    today = date.today()
    window_start = (today - timedelta(days=days_back - 1)).isoformat()

    existing = _load_existing(out_path) if out_path.exists() else {}
    new_days = _compute_daily(posts)
    merged = _merge_daily(existing, new_days, window_start)

    output = {
        "meta": {
            "schema_version": 1,
            "last_updated": datetime.now().astimezone().isoformat(timespec="seconds"),
            "day_count": len(merged),
            "earliest": min(merged) if merged else None,
            "latest": max(merged) if merged else None,
        },
        "days": dict(sorted(merged.items())),
    }
    _atomic_write(out_path, json.dumps(output, ensure_ascii=False, indent=2))
    log.info("Wrote daily aggregation to %s (%d days)", out_path, len(merged))
    return out_path


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

    # Also update the per-day time series alongside posts.json. This is
    # the file that grows linearly over time — analytics-friendly.
    write_daily_json(posts, days_back)
    return out_path
