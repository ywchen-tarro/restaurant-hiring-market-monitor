"""Unit tests for scraper.output.

Covers: atomic write, corrupt-file preservation, history merge (same-day),
daily merge (window-bounded refresh), mirror-group dedup, and warning
emission.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

import pytest

from scraper import output
from scraper.platforms.base import Post


def _mk(post_id, platform, title, date_iso="2026-05-25", region=None, state=None, city=None):
    return Post(
        id=post_id,
        platform=platform,
        title=title,
        date=date_iso,
        region=region,
        state=state,
        keywords_matched=[],
        url=f"https://example.com/{post_id}",
        city=city,
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


def test_meiguogongzuo_self_dedup():
    """meiguogongzuo reposts the same job under a new ID — those should
    collapse to one in the unique count."""
    posts = [
        _mk("a", "meiguogongzuo", "中日餐 炒锅"),
        _mk("b", "meiguogongzuo", "中日餐 炒锅"),       # same normalized title
        _mk("c", "meiguogongzuo", "长岛寿司助手"),
        _mk("d", "meiguogongzuo", "长岛寿司助手"),       # repost
    ]
    # 2 distinct titles after self-dedup
    assert output._unique_post_count(posts) == 2


def test_meiguogongzuo_self_dedup_normalized_through_punctuation():
    """Self-dedup should ignore punctuation/whitespace/emoji like mirror dedup."""
    posts = [
        _mk("a", "meiguogongzuo", "中日餐 炒锅"),
        _mk("b", "meiguogongzuo", "📜中日餐  炒锅！"),  # decorations only
    ]
    assert output._unique_post_count(posts) == 1


def test_self_dedup_does_not_affect_other_platforms():
    """A platform NOT in SELF_DEDUP_PLATFORMS keeps within-platform repeats."""
    posts = [
        _mk("a", "niuyuegongzuo", "熟手炒锅"),
        _mk("b", "niuyuegongzuo", "熟手炒锅"),
        _mk("c", "niuyuegongzuo", "熟手炒锅"),
    ]
    assert output._unique_post_count(posts) == 3


def test_mirror_dedup_still_intact():
    """The mirror-group dedup must not be broken by the new self-dedup path."""
    posts = [
        _mk("a", "168worker", "请熟手炒锅"),
        _mk("b", "500work",   "请熟手炒锅"),
    ]
    assert output._unique_post_count(posts) == 1


def test_mirror_and_self_dedup_combined():
    """Mirror group + self-dedup platform in the same dataset both apply."""
    posts = [
        _mk("a", "168worker",     "炒锅师傅"),
        _mk("b", "500work",       "炒锅师傅"),       # mirror dup
        _mk("c", "meiguogongzuo", "炒锅师傅"),       # NOT a mirror; counts as 1
        _mk("d", "meiguogongzuo", "炒锅师傅"),       # self-dedup with (c)
        _mk("e", "niuyuegongzuo", "炒锅师傅"),       # independent → kept
    ]
    # 1 (mirror) + 1 (mgg) + 1 (nyge) = 3
    assert output._unique_post_count(posts) == 3


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
    overstate activity by keeping stale data for normal platforms)."""
    existing = {"days": {
        "2026-05-20": {"total": 10, "by_platform": {"168worker": 10}, "by_region": {}},
        "2026-05-21": {"total": 8, "by_platform": {"168worker": 8}, "by_region": {}},
    }}
    new_days = {
        "2026-05-21": {"total": 0, "by_platform": {}, "by_region": {}},
        # 2026-05-20 NOT in new_days — should be dropped
    }
    merged = output._merge_daily(existing, new_days, window_start="2026-05-19")
    assert "2026-05-20" not in merged
    assert "2026-05-21" not in merged


def test_merge_daily_preserves_relative_date_platforms_in_window():
    """uscanyin exposes relative timestamps, so tomorrow's scrape cannot
    reconstruct yesterday's bucket. Preserve that platform's prior count
    while still refreshing normal platforms from the new scrape."""
    existing = {"days": {
        "2026-05-25": {
            "total": 150,
            "by_platform": {"uscanyin": 120, "168worker": 30},
            "by_region": {"东部": 150},
        },
    }}
    new_days = {
        "2026-05-25": {
            "total": 25,
            "by_platform": {"168worker": 25},
            "by_region": {"东部": 25},
        },
        "2026-05-26": {
            "total": 130,
            "by_platform": {"uscanyin": 110, "168worker": 20},
            "by_region": {"东部": 130},
        },
    }
    merged = output._merge_daily(existing, new_days, window_start="2026-05-20")
    assert merged["2026-05-25"]["by_platform"] == {
        "168worker": 25,
        "uscanyin": 120,
    }
    assert merged["2026-05-25"]["total"] == 145
    assert merged["2026-05-26"]["by_platform"]["uscanyin"] == 110


def test_merge_daily_drops_relative_platform_when_explicitly_replaced_by_zero():
    """If the new scrape explicitly contains the relative platform with 0
    for a day, trust the new data."""
    existing = {"days": {
        "2026-05-25": {
            "total": 120,
            "by_platform": {"uscanyin": 120},
            "by_region": {},
        },
    }}
    new_days = {
        "2026-05-25": {
            "total": 0,
            "by_platform": {"uscanyin": 0},
            "by_region": {},
        },
    }
    merged = output._merge_daily(existing, new_days, window_start="2026-05-20")
    assert "2026-05-25" not in merged


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


def test_warning_on_all_platforms_zero():
    """Global signal: total dropped to 0 while prior run had real data → warn."""
    history = [
        {"run_date": "2026-05-22", "by_platform": {"168worker": 30, "uscanyin": 50}},
        {"run_date": "2026-05-25", "by_platform": {"168worker": 0, "uscanyin": 0}},
    ]
    warnings = output._compute_warnings(history, diagnostics=None)
    # Should include the global "all zero" warning (more informative than
    # the per-platform messages alone — both small-volume platforms can
    # fail at once without crossing the per-platform 5-floor)
    assert any("all platforms" in w.lower() for w in warnings)


def test_no_global_zero_warning_on_first_run():
    """No prior data → no spurious 'all platforms zero' warning on day 1."""
    history = [{"run_date": "2026-05-25", "by_platform": {"168worker": 0}}]
    warnings = output._compute_warnings(history, diagnostics=None)
    assert not any("all platforms" in w.lower() for w in warnings)


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


def test_warning_on_page_cap_before_window_boundary():
    diagnostics = {
        "us168": {
            "status": "ok",
            "pages_fetched": 30,
            "hit_page_cap": True,
            "dropped_out_of_window": 0,
            "fetch_failures": 0,
            "rows_parsed": 600,
            "dropped_unparseable_date": 0,
        }
    }
    history = [{"run_date": "2026-05-25", "by_platform": {"us168": 200}}]
    warnings = output._compute_warnings(history, diagnostics=diagnostics)
    assert any("us168" in w and "page cap" in w for w in warnings)


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


# ─────────────────────────────────────────────────────────────
# write_posts_json end-to-end (full output shape, history append,
# daily.json side effect)
# ─────────────────────────────────────────────────────────────

def test_write_posts_json_end_to_end(tmp_path: Path):
    """Full happy path: write posts.json with a real Post; ensure all
    documented top-level keys exist, history starts fresh, daily.json
    co-exists alongside (atomic). """
    import json
    posts_path = tmp_path / "posts.json"
    daily_path = tmp_path / "daily.json"
    city_path = tmp_path / "cities.json"
    posts = [
        _mk("a", "niuyuegongzuo", "中日餐请炒锅",  region="东部", state="法拉盛", city="法拉盛"),
        _mk("b", "168worker",     "请师傅",         region="东部", state="纽约"),
    ]
    # Patch the config defaults to point at tmp paths
    with mock.patch.object(output.config, "OUTPUT_JSON", posts_path), \
         mock.patch.object(output.config, "DAILY_JSON", daily_path), \
         mock.patch.object(output.config, "CITY_JSON", city_path):
        output.write_posts_json(posts, days_back=7, diagnostics={"168worker": {"status": "ok"}})

    assert posts_path.exists()
    d = json.loads(posts_path.read_text(encoding="utf-8"))
    # Documented schema
    for key in ("meta", "by_platform", "by_region", "by_city", "by_keyword", "history", "posts"):
        assert key in d, f"missing top-level key: {key}"
    assert d["by_city"]["法拉盛"]["total"] == 1
    assert d["by_city"]["法拉盛"]["lon"] is not None
    assert d["by_city"]["法拉盛"]["lat"] is not None
    assert d["by_region"]["东部"]["top_cities"]["法拉盛"] == 1
    assert d["posts"][0]["city"] == "法拉盛"
    assert d["meta"]["total_posts"] == 2
    assert d["meta"]["unique_posts"] >= 1
    assert d["meta"]["scrape_days_back"] == 7
    # History was appended (single new entry)
    assert len(d["history"]) == 1
    assert d["history"][0]["total"] == 2
    assert d["history"][0]["total_unique"] >= 1

    # daily.json side-effect file also written
    assert daily_path.exists()
    daily = json.loads(daily_path.read_text(encoding="utf-8"))
    assert "days" in daily
    assert "meta" in daily and "schema_version" in daily["meta"]

    assert city_path.exists()
    cities = json.loads(city_path.read_text(encoding="utf-8"))
    assert cities["cities"]["法拉盛"]["total"] == 1
    assert cities["cities"]["法拉盛"]["lon"] is not None


def test_write_posts_json_empty_posts_still_produces_valid_file(tmp_path: Path):
    """All platforms returned 0 today: writer should still produce a
    valid posts.json (and daily.json) rather than crash."""
    import json
    posts_path = tmp_path / "posts.json"
    daily_path = tmp_path / "daily.json"
    city_path = tmp_path / "cities.json"
    with mock.patch.object(output.config, "OUTPUT_JSON", posts_path), \
         mock.patch.object(output.config, "DAILY_JSON", daily_path), \
         mock.patch.object(output.config, "CITY_JSON", city_path):
        output.write_posts_json([], days_back=7)
    d = json.loads(posts_path.read_text(encoding="utf-8"))
    assert d["meta"]["total_posts"] == 0
    assert d["meta"]["unique_posts"] == 0
    assert d["posts"] == []
    assert len(d["history"]) == 1
    assert d["history"][0]["total"] == 0


def test_write_posts_json_history_accumulates_across_days(tmp_path: Path):
    """Two runs on different days produce 2 history entries (frozen
    older days preserved)."""
    import json
    posts_path = tmp_path / "posts.json"
    daily_path = tmp_path / "daily.json"
    city_path = tmp_path / "cities.json"
    with mock.patch.object(output.config, "OUTPUT_JSON", posts_path), \
         mock.patch.object(output.config, "DAILY_JSON", daily_path), \
         mock.patch.object(output.config, "CITY_JSON", city_path):
        output.write_posts_json([_mk("a", "niuyuegongzuo", "中日餐请炒锅")], days_back=7)
        d1 = json.loads(posts_path.read_text(encoding="utf-8"))
        # Patch the run_date of the first entry to look like yesterday so
        # the next run treats it as a different day
        d1["history"][0]["run_date"] = "2026-05-24"
        posts_path.write_text(json.dumps(d1, ensure_ascii=False), encoding="utf-8")
        output.write_posts_json([_mk("b", "168worker", "请师傅")], days_back=7)
        d2 = json.loads(posts_path.read_text(encoding="utf-8"))
    assert len(d2["history"]) == 2


def test_write_posts_json_atomic_write_no_tmp_left(tmp_path: Path):
    posts_path = tmp_path / "posts.json"
    daily_path = tmp_path / "daily.json"
    city_path = tmp_path / "cities.json"
    with mock.patch.object(output.config, "OUTPUT_JSON", posts_path), \
         mock.patch.object(output.config, "DAILY_JSON", daily_path), \
         mock.patch.object(output.config, "CITY_JSON", city_path):
        output.write_posts_json([_mk("a", "niuyuegongzuo", "中日餐请炒锅")], days_back=7)
    tmps = list(tmp_path.glob("*.tmp"))
    assert tmps == [], f"left-over tmp files: {tmps}"


def test_write_posts_json_meiguogongzuo_listed_in_by_platform_even_when_empty(tmp_path: Path):
    """All platforms in config.PLATFORMS should appear in by_platform —
    a 0 total for a configured platform is meaningful (vs missing key)."""
    import json
    posts_path = tmp_path / "posts.json"
    daily_path = tmp_path / "daily.json"
    city_path = tmp_path / "cities.json"
    with mock.patch.object(output.config, "OUTPUT_JSON", posts_path), \
         mock.patch.object(output.config, "DAILY_JSON", daily_path), \
         mock.patch.object(output.config, "CITY_JSON", city_path):
        output.write_posts_json([_mk("a", "niuyuegongzuo", "中日餐请炒锅")], days_back=7)
    d = json.loads(posts_path.read_text(encoding="utf-8"))
    for plat in output.config.PLATFORMS:
        if plat.get("enabled"):
            assert plat["id"] in d["by_platform"], \
                f"enabled platform {plat['id']} missing from by_platform"
