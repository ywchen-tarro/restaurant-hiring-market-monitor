"""Unit tests for BasePlatformScraper.run() — the scrape driver.

Covers cutoff date math, dedup, the keyword filter, region classification,
pagination-stop semantics, and per-page exception isolation. Tests use a
stub Scraper subclass that injects synthetic posts, so no network.
"""

from __future__ import annotations

from datetime import date, timedelta
from unittest import mock

import pytest

from scraper import config
from scraper.platforms.base import BasePlatformScraper, Post, post_id


def _mk(native_id: str, title: str, day_offset: int, today: date) -> Post:
    """Build a raw Post (pre-filter) dated `day_offset` days before today."""
    d = today + timedelta(days=day_offset)
    return Post(
        id=post_id("stub", native_id),
        platform="stub",
        title=title,
        date=d.isoformat(),
        region=None,
        state=None,
        keywords_matched=[],
        url=f"https://example.com/{native_id}",
    )


class _StubScraper(BasePlatformScraper):
    """Test double that returns canned page results without HTTP."""

    id = "stub"
    name = "Stub"
    # Big cap so MAX_PAGES_PER_PLATFORM doesn't interfere with tests
    max_pages = 50

    def __init__(self, pages, today=None):
        super().__init__()
        # pages: list of [Post, ...] OR None (None simulates fetch failure)
        self._pages = pages
        self._today = today or date.today()

    def page_url(self, page_num):
        return f"https://example.com/list/{page_num}"

    # Bypass actual fetching — return canned HTML markers
    def fetch_page(self, page_num):
        idx = page_num - 1
        if idx >= len(self._pages):
            return None
        if self._pages[idx] is None:
            return None
        # Anything truthy works — parse_page below ignores it
        return f"page-{page_num}"

    def parse_page(self, html, page_num):
        idx = page_num - 1
        if idx >= len(self._pages):
            return []
        result = self._pages[idx]
        if result is None:
            return []
        return list(result)


# ─────────────────────────────────────────────────────────────
# Cutoff date math (off-by-one regression guard)
# ─────────────────────────────────────────────────────────────

def test_post_at_cutoff_edge_kept():
    """A post dated exactly today - (days_back-1) should be KEPT
    (the lookback window is inclusive of that boundary day)."""
    today = date(2026, 5, 25)
    posts = [_mk("a", "中日餐请炒锅", -6, today)]   # 2026-05-19, the edge
    s = _StubScraper([posts])
    with mock.patch("scraper.platforms.base.date") as fake_date:
        fake_date.today.return_value = today
        fake_date.fromisoformat = date.fromisoformat
        result = s.run(days_back=7)
    assert len(result) == 1
    assert result[0].date == "2026-05-19"


def test_post_outside_window_dropped():
    today = date(2026, 5, 25)
    posts = [_mk("a", "中日餐请炒锅", -7, today)]   # 2026-05-18, one day past
    s = _StubScraper([posts])
    with mock.patch("scraper.platforms.base.date") as fake_date:
        fake_date.today.return_value = today
        fake_date.fromisoformat = date.fromisoformat
        result = s.run(days_back=7)
    assert result == []
    assert s.last_diagnostics["dropped_out_of_window"] == 1


def test_future_dated_post_dropped():
    """A post dated AFTER local-today should be dropped — happens when
    the source site runs in a timezone east of us (e.g. ET vs PT) and
    serves posts dated tomorrow late at night."""
    today = date(2026, 5, 25)
    # Post dated tomorrow (5/26), simulating an ET-dated listing
    # appearing in our 22:30 PT scrape
    posts = [_mk("a", "中日餐请炒锅", +1, today)]   # 2026-05-26
    s = _StubScraper([posts])
    with mock.patch("scraper.platforms.base.date") as fake_date:
        fake_date.today.return_value = today
        fake_date.fromisoformat = date.fromisoformat
        result = s.run(days_back=7)
    assert result == []
    assert s.last_diagnostics["dropped_future_date"] == 1


def test_post_dated_exactly_today_kept():
    today = date(2026, 5, 25)
    posts = [_mk("a", "中日餐请炒锅", 0, today)]   # 2026-05-25 == today
    s = _StubScraper([posts])
    with mock.patch("scraper.platforms.base.date") as fake_date:
        fake_date.today.return_value = today
        fake_date.fromisoformat = date.fromisoformat
        result = s.run(days_back=7)
    assert len(result) == 1
    assert result[0].date == today.isoformat()


def test_stop_paginating_after_window_boundary():
    """Once any post on a page falls outside the window, the scraper
    should NOT fetch the next page."""
    today = date(2026, 5, 25)
    page1 = [_mk(f"p{i}", "请炒锅师傅", -i, today) for i in range(0, 8)]  # today..7d ago
    page2 = [_mk("never", "请炒锅师傅", -1, today)]
    s = _StubScraper([page1, page2])
    with mock.patch("scraper.platforms.base.date") as fake_date:
        fake_date.today.return_value = today
        fake_date.fromisoformat = date.fromisoformat
        result = s.run(days_back=7)
    # Should have stopped after page 1 (which contained an out-of-window post)
    assert s.last_diagnostics["pages_fetched"] == 1
    # Page 2's post never got included
    assert all(p.id != "stub_never" for p in result)


# ─────────────────────────────────────────────────────────────
# Restaurant keyword filter integration
# ─────────────────────────────────────────────────────────────

def test_weak_only_keyword_dropped():
    today = date(2026, 5, 25)
    posts = [
        _mk("a", "Brooklyn 脊椎诊所招聘 2 名", 0, today),  # only 招聘 — weak
        _mk("b", "法拉盛日餐请师傅", 0, today),            # strong
    ]
    s = _StubScraper([posts])
    with mock.patch("scraper.platforms.base.date") as fake_date:
        fake_date.today.return_value = today
        fake_date.fromisoformat = date.fromisoformat
        result = s.run(days_back=7)
    assert len(result) == 1
    assert result[0].id == "stub_b"
    assert s.last_diagnostics["dropped_not_restaurant"] == 1


def test_unparseable_date_dropped():
    today = date(2026, 5, 25)
    # Force an unparseable date by overriding directly
    p = _mk("a", "中日餐请炒锅", 0, today)
    p.date = "not-a-date"
    s = _StubScraper([[p]])
    with mock.patch("scraper.platforms.base.date") as fake_date:
        fake_date.today.return_value = today
        fake_date.fromisoformat = date.fromisoformat
        result = s.run(days_back=7)
    assert result == []
    assert s.last_diagnostics["dropped_unparseable_date"] == 1


# ─────────────────────────────────────────────────────────────
# Per-page dedup
# ─────────────────────────────────────────────────────────────

def test_duplicate_id_across_pages_dedup():
    today = date(2026, 5, 25)
    p = _mk("a", "中日餐请炒锅", 0, today)
    page1 = [p]
    page2 = [Post(**{**p.__dict__})]  # same id
    s = _StubScraper([page1, page2])
    with mock.patch("scraper.platforms.base.date") as fake_date:
        fake_date.today.return_value = today
        fake_date.fromisoformat = date.fromisoformat
        result = s.run(days_back=7)
    assert len(result) == 1
    assert s.last_diagnostics["dropped_duplicate"] == 1


# ─────────────────────────────────────────────────────────────
# Pagination stop on consecutive empty pages
# ─────────────────────────────────────────────────────────────

def test_two_consecutive_empty_pages_stops():
    today = date(2026, 5, 25)
    page1 = [_mk("a", "中日餐请炒锅", 0, today)]
    s = _StubScraper([page1, [], [], page1])  # 2 empty pages should stop us
    with mock.patch("scraper.platforms.base.date") as fake_date:
        fake_date.today.return_value = today
        fake_date.fromisoformat = date.fromisoformat
        result = s.run(days_back=7)
    assert s.last_diagnostics["pages_fetched"] == 3   # tried page 1, 2, 3, stopped before 4
    assert len(result) == 1


def test_fetch_failure_stops_pagination():
    today = date(2026, 5, 25)
    page1 = [_mk("a", "中日餐请炒锅", 0, today)]
    s = _StubScraper([page1, None])   # second page fetch returns None
    with mock.patch("scraper.platforms.base.date") as fake_date:
        fake_date.today.return_value = today
        fake_date.fromisoformat = date.fromisoformat
        result = s.run(days_back=7)
    assert s.last_diagnostics["fetch_failures"] == 1
    assert s.last_diagnostics["pages_fetched"] == 1   # only page 1 counted
    assert len(result) == 1


# ─────────────────────────────────────────────────────────────
# Per-page exception isolation
# ─────────────────────────────────────────────────────────────

class _BadScraper(_StubScraper):
    def parse_page(self, html, page_num):
        if page_num == 2:
            raise RuntimeError("simulated DOM-change crash")
        return super().parse_page(html, page_num)


def test_parse_page_exception_does_not_kill_run():
    today = date(2026, 5, 25)
    page1 = [_mk("a", "中日餐请炒锅", 0, today)]
    # "中餐请师傅" still passes (师傅 alone wouldn't, but 中餐 is venue)
    page3 = [_mk("c", "中餐请师傅", 0, today)]
    s = _BadScraper([page1, [], page3])
    with mock.patch("scraper.platforms.base.date") as fake_date:
        fake_date.today.return_value = today
        fake_date.fromisoformat = date.fromisoformat
        result = s.run(days_back=7)
    # Page 2 raised; pages 1 + 3 still produced posts
    ids = {p.id for p in result}
    assert "stub_a" in ids
    # Page 3 not reached because page 2's empty + page 3 counts as 1 empty,
    # but didn't trigger 2-consecutive-empty stop yet. Actually:
    # page 1: 1 parsed, 1 kept (consecutive_empty resets to 0)
    # page 2: raises → page_posts=[] → consecutive_empty=1
    # page 3: 1 parsed, 1 kept → consecutive_empty resets
    # So page 3 IS reached. Verify:
    assert "stub_c" in ids


# ─────────────────────────────────────────────────────────────
# Diagnostics shape
# ─────────────────────────────────────────────────────────────

def test_diagnostics_keys_present():
    today = date(2026, 5, 25)
    page1 = [_mk("a", "中日餐请炒锅", 0, today)]
    s = _StubScraper([page1])
    with mock.patch("scraper.platforms.base.date") as fake_date:
        fake_date.today.return_value = today
        fake_date.fromisoformat = date.fromisoformat
        s.run(days_back=7)
    d = s.last_diagnostics
    # Keys consumed by output._compute_warnings
    for key in ["pages_fetched", "rows_parsed", "dropped_unparseable_date",
                "dropped_out_of_window", "dropped_not_restaurant",
                "dropped_duplicate", "fetch_failures"]:
        assert key in d, f"missing diagnostics key: {key}"


def test_phone_number_redacted_in_kept_post():
    today = date(2026, 5, 25)
    p = _mk("a", "中日餐请炒锅 联系 7187082268", 0, today)
    s = _StubScraper([[p]])
    with mock.patch("scraper.platforms.base.date") as fake_date:
        fake_date.today.return_value = today
        fake_date.fromisoformat = date.fromisoformat
        result = s.run(days_back=7)
    assert "7187082268" not in result[0].title
    assert "[电话]" in result[0].title
