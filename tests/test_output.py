"""Unit tests for scraper.output.

Covers: atomic write, corrupt-file preservation, history merge (same-day),
daily merge (window-bounded refresh), mirror-group dedup, and warning
emission.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from scraper import output
from scraper.platforms.base import Post


def _mk(post_id, platform, title, date_iso="2026-05-25", region=None, state=None):
    return Post(
        id=post_id,
        platform=platform,
        title=title,
        date=date_iso,
        region=region,
        state=state,
        keywords_matched=[],
        url=f"https://example.com/{post_id}",
    )


# ─────────────────────────────────────────────────────────────
# _normalize_title
# ─────────────────────────────────────────────────────────────

def test_normalize_strips_emoji():
    assert output._normalize_title("📜请熟手炒锅") == "请熟手炒锅"


def test_normalize_collapses_whitespace():
    assert output._normalize_title("请  熟手 炒锅") == "请熟手炒锅"


def test_normalize_strips_punctuation():
    assert output._normalize_title("急聘！炒锅师傅。") == "急聘炒锅师傅"


def test_normalize_lowercases():
    assert output._normalize_title("Boston Restaurant") == "bostonrestaurant"


def test_normalize_empty_string():
    assert output._normalize_title("") == ""


def test_normalize_none_safe():
    assert output._normalize_title(None) == ""


# ─────────────────────────────────────────────────────────────
# _unique_post_count (mirror-group dedup)
# ─────────────────────────────────────────────────────────────

def test_unique_count_no_duplicates():
    posts = [
        _mk("a", "168worker", "请炒锅一"),
        _mk("b", "500work", "请师傅二"),
        _mk("c", "niuyuegongzuo", "请打杂三"),
    ]
    assert output._unique_post_count(posts) == 3


def test_mirror_dedup_collapses_cross_platform_dup():
    """168worker + 500work with identical normalized title → 1 unique."""
    posts = [
        _mk("a", "168worker", "请炒锅师傅"),
        _mk("b", "500work", "请炒锅师傅"),
    ]
    assert output._unique_post_count(posts) == 1


def test_independent_platforms_keep_duplicates():
    """Same title on independent platforms (not in MIRROR_GROUPS) stays as 2."""
    posts = [
        _mk("a", "niuyuegongzuo", "熟手炒锅"),
        _mk("b", "uscanyin", "熟手炒锅"),
    ]
    assert output._unique_post_count(posts) == 2


def test_same_platform_duplicates_kept():
    """Multiple posts with the same generic title on a single mirror-group
    platform are still distinct restaurants — only ONE collapses out."""
    posts = [
        _mk("a1", "168worker", "请师傅"),
        _mk("a2", "168worker", "请师傅"),  # different restaurant, same title
    ]
    # Within mirror-group: same-title posts dedup to 1 (we can't tell them apart)
    assert output._unique_post_count(posts) == 1


def test_mixed_real_scenario():
    posts = [
        _mk("a", "168worker", "请炒锅"),       # → 168/500 mirror collapse
        _mk("b", "500work", "请炒锅"),         # → same
        _mk("c", "168worker", "请师傅"),       # → separate mirror entry
        _mk("d", "500work", "请师傅"),         # → same
        _mk("e", "uscanyin", "熟手炒锅"),     # → kept (independent)
        _mk("f", "uscanyin", "熟手炒锅"),     # → kept (within-platform repeats)
        _mk("g", "uscanyin", "熟手炒锅"),     # → kept
    ]
    # 2 (mirror) + 3 (uscanyin within-platform) = 5
    assert output._unique_post_count(posts) == 5


def test_unique_count_handles_blank_title():
    posts = [_mk("a", "168worker", "")]
    # Untitled — still counts as 1 (no normalization key collision)
    assert output._unique_post_count(posts) == 1


# ─────────────────────────────────────────────────────────────
# _merge_history (same-day handling)
# ─────────────────────────────────────────────────────────────

def test_merge_history_new_day_appends():
    existing = {"history": [{"run_date": "2026-05-24", "total": 100}]}
    new_entry = {"run_date": "2026-05-25", "total": 50}
    merged = output._merge_history(existing, new_entry)
    assert len(merged) == 2
    assert merged[-1] == new_entry


def test_merge_history_same_day_higher_wins():
    existing = {"history": [{"run_date": "2026-05-25", "total": 50}]}
    new_entry = {"run_date": "2026-05-25", "total": 100}
    merged = output._merge_history(existing, new_entry)
    assert len(merged) == 1
    assert merged[0]["total"] == 100


def test_merge_history_same_day_lower_rejected():
    """Protects against a partial re-run overwriting a healthy entry."""
    existing = {"history": [{"run_date": "2026-05-25", "total": 100}]}
    new_entry = {"run_date": "2026-05-25", "total": 50}
    merged = output._merge_history(existing, new_entry)
    assert len(merged) == 1
    assert merged[0]["total"] == 100  # old kept


def test_merge_history_first_run():
    existing = {}
    new_entry = {"run_date": "2026-05-25", "total": 100}
    merged = output._merge_history(existing, new_entry)
    assert merged == [new_entry]


# ─────────────────────────────────────────────────────────────
# _merge_daily (window-bounded refresh)
# ─────────────────────────────────────────────────────────────

def test_merge_daily_freezes_older_days():
    existing = {"days": {
        "2026-05-15": {"total": 5, "by_platform": {}, "by_region": {}},  # before window
        "2026-05-20": {"total": 10, "by_platform": {}, "by_region": {}},  # in window
    }}
    new_days = {
        "2026-05-20": {"total": 12, "by_platform": {}, "by_region": {}},  # refreshed
        "2026-05-25": {"total": 8, "by_platform": {}, "by_region": {}},   # new
    }
    merged = output._merge_daily(existing, new_days, window_start="2026-05-19")
    assert merged["2026-05-15"]["total"] == 5    # frozen (before window)
    assert merged["2026-05-20"]["total"] == 12   # refreshed (was 10)
    assert merged["2026-05-25"]["total"] == 8    # new


def test_merge_daily_drops_stale_in_window_days():
    """If a prior in-window day disappears from new_days, drop it (don't
    overstate activity by keeping stale data)."""
    existing = {"days": {
        "2026-05-20": {"total": 10, "by_platform": {}, "by_region": {}},
        "2026-05-21": {"total": 8, "by_platform": {}, "by_region": {}},
    }}
    new_days = {
        "2026-05-21": {"total": 0, "by_platform": {}, "by_region": {}},
        # 2026-05-20 NOT in new_days — should be dropped
    }
    merged = output._merge_daily(existing, new_days, window_start="2026-05-19")
    assert "2026-05-20" not in merged
    assert merged["2026-05-21"]["total"] == 0


def test_merge_daily_empty_new():
    existing = {"days": {"2026-05-10": {"total": 5, "by_platform": {}, "by_region": {}}}}
    merged = output._merge_daily(existing, {}, window_start="2026-05-19")
    # Only the old frozen day
    assert merged == {"2026-05-10": {"total": 5, "by_platform": {}, "by_region": {}}}


def test_merge_daily_empty_existing():
    new_days = {"2026-05-25": {"total": 7, "by_platform": {}, "by_region": {}}}
    merged = output._merge_daily({}, new_days, window_start="2026-05-19")
    assert merged == new_days


# ─────────────────────────────────────────────────────────────
# _compute_warnings (schema-drift detection)
# ─────────────────────────────────────────────────────────────

def test_warning_on_platform_drop_to_zero():
    history = [
        {"run_date": "2026-05-22", "by_platform": {"168worker": 30}},
        {"run_date": "2026-05-25", "by_platform": {"168worker": 0}},
    ]
    warnings = output._compute_warnings(history, diagnostics=None)
    assert any("168worker" in w and "0" in w for w in warnings)


def test_warning_on_70pct_drop():
    history = [
        {"run_date": "2026-05-22", "by_platform": {"niuyuegongzuo": 100}},
        {"run_date": "2026-05-25", "by_platform": {"niuyuegongzuo": 25}},
    ]
    warnings = output._compute_warnings(history, diagnostics=None)
    assert any("niuyuegongzuo" in w for w in warnings)


def test_no_warning_for_normal_variation():
    history = [
        {"run_date": "2026-05-22", "by_platform": {"168worker": 50}},
        {"run_date": "2026-05-25", "by_platform": {"168worker": 45}},
    ]
    warnings = output._compute_warnings(history, diagnostics=None)
    assert warnings == []


def test_warning_on_high_unparsed_date_rate():
    diagnostics = {"168worker": {"status": "ok", "rows_parsed": 100, "dropped_unparseable_date": 15}}
    history = [{"run_date": "2026-05-25", "by_platform": {"168worker": 85}}]
    warnings = output._compute_warnings(history, diagnostics=diagnostics)
    assert any("date format" in w for w in warnings)


def test_warning_on_scraper_exception():
    diagnostics = {"168worker": {"status": "error", "exception": "TimeoutError"}}
    history = [{"run_date": "2026-05-25", "by_platform": {"168worker": 0}}]
    warnings = output._compute_warnings(history, diagnostics=diagnostics)
    assert any("TimeoutError" in w or "168worker" in w for w in warnings)


# ─────────────────────────────────────────────────────────────
# Atomic write
# ─────────────────────────────────────────────────────────────

def test_atomic_write_creates_file(tmp_path: Path):
    p = tmp_path / "x.json"
    output._atomic_write(p, '{"hello":"world"}')
    assert p.read_text() == '{"hello":"world"}'


def test_atomic_write_overwrites_existing(tmp_path: Path):
    p = tmp_path / "x.json"
    p.write_text("old")
    output._atomic_write(p, "new")
    assert p.read_text() == "new"


def test_atomic_write_no_tmp_left_behind(tmp_path: Path):
    p = tmp_path / "x.json"
    output._atomic_write(p, "data")
    # No stray .tmp files
    tmps = list(tmp_path.glob("*.tmp"))
    assert tmps == []


def test_load_existing_returns_empty_for_missing_file(tmp_path: Path):
    p = tmp_path / "missing.json"
    assert output._load_existing(p) == {}


def test_load_existing_preserves_corrupt_file(tmp_path: Path):
    p = tmp_path / "corrupt.json"
    p.write_text("this is not valid json{")
    result = output._load_existing(p)
    assert result == {}
    # Corrupt file renamed aside
    corrupts = list(tmp_path.glob("corrupt.json.corrupt-*"))
    assert len(corrupts) == 1
