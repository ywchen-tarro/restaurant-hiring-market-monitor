"""Unit tests for scraper.date_parser.

Pins behavior for every parsing branch the date strings on the active
platforms exercise. Frozen "today" makes the relative-date paths
deterministic.
"""

from __future__ import annotations

from datetime import date, timedelta
from unittest import mock

from scraper import date_parser


TODAY = date(2026, 5, 25)


def _parse(text):
    """parse() with TODAY pinned, so 'yesterday' is always 2026-05-24."""
    with mock.patch.object(date_parser, "date") as fake:
        fake.today.return_value = TODAY
        # date.fromisoformat etc. still need to work — pass through:
        fake.side_effect = lambda *a, **k: date(*a, **k)
        # Actually simpler: just pass `today` arg directly.
        pass
    # parse() accepts today= override — use that instead of mocking.
    return date_parser.parse(text, today=TODAY)


# ─────────────────────────────────────────────────────────────
# Absolute dates
# ─────────────────────────────────────────────────────────────

def test_iso_yyyy_mm_dd():
    assert _parse("2026-05-22") == date(2026, 5, 22)


def test_iso_yyyy_slash_mm_slash_dd():
    assert _parse("2026/05/22") == date(2026, 5, 22)


def test_mm_dd_yy_us_format():
    # MM/DD/YY (niuyuegongzuo style)
    assert _parse("05/22/26") == date(2026, 5, 22)


def test_mm_dd_yyyy():
    assert _parse("05/22/2026") == date(2026, 5, 22)


def test_invalid_month_returns_none():
    assert _parse("2026-13-01") is None


def test_invalid_day_returns_none():
    assert _parse("2026-02-30") is None


# ─────────────────────────────────────────────────────────────
# Chinese relative dates
# ─────────────────────────────────────────────────────────────

def test_zh_just_now():
    assert _parse("刚刚") == TODAY


def test_zh_just_now_traditional():
    assert _parse("剛剛") == TODAY


def test_zh_today():
    assert _parse("今天") == TODAY


def test_zh_yesterday():
    assert _parse("昨天") == TODAY - timedelta(days=1)


def test_zh_two_days_ago():
    assert _parse("前天") == TODAY - timedelta(days=2)


def test_zh_minutes_ago_collapses_to_today():
    # Sub-day units all collapse to today
    assert _parse("5分钟前") == TODAY
    assert _parse("30分鐘前") == TODAY


def test_zh_hours_ago_collapses_to_today():
    assert _parse("7小时前") == TODAY
    assert _parse("23小時前") == TODAY


def test_zh_n_days_ago():
    assert _parse("3天前") == TODAY - timedelta(days=3)
    assert _parse("5日前") == TODAY - timedelta(days=5)


def test_zh_one_week_ago():
    assert _parse("1周前") == TODAY - timedelta(days=7)
    assert _parse("2週前") == TODAY - timedelta(days=14)


def test_zh_one_month_ago_approx():
    assert _parse("1月前") == TODAY - timedelta(days=30)


# ─────────────────────────────────────────────────────────────
# English relative dates (uscanyin)
# ─────────────────────────────────────────────────────────────

def test_en_just_now():
    assert _parse("just now") == TODAY


def test_en_today():
    assert _parse("today") == TODAY


def test_en_yesterday():
    assert _parse("yesterday") == TODAY - timedelta(days=1)
    assert _parse("YESTERDAY") == TODAY - timedelta(days=1)


def test_en_minutes_hours_ago():
    assert _parse("1 minute ago") == TODAY
    assert _parse("5 minutes ago") == TODAY
    assert _parse("1 hour ago") == TODAY
    assert _parse("23 hours ago") == TODAY


def test_en_n_days_ago():
    assert _parse("1 day ago") == TODAY - timedelta(days=1)
    assert _parse("5 days ago") == TODAY - timedelta(days=5)


def test_en_weeks_ago():
    assert _parse("1 week ago") == TODAY - timedelta(days=7)
    assert _parse("2 weeks ago") == TODAY - timedelta(days=14)


def test_en_months_years_approx():
    assert _parse("1 month ago") == TODAY - timedelta(days=30)
    assert _parse("1 year ago") == TODAY - timedelta(days=365)


# ─────────────────────────────────────────────────────────────
# Boundary & error cases
# ─────────────────────────────────────────────────────────────

def test_empty_string_returns_none():
    assert _parse("") is None


def test_none_returns_none():
    assert _parse(None) is None


def test_garbage_string_returns_none():
    assert _parse("not a date at all") is None


def test_whitespace_only_returns_none():
    assert _parse("   \n\t") is None
