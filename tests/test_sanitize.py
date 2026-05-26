"""Unit tests for scraper.sanitize.

Phone-number redaction is the project's defense against republishing PII
to a public dashboard.
"""

from __future__ import annotations

from scraper import sanitize


# ─────────────────────────────────────────────────────────────
# Phone formats observed in the wild
# ─────────────────────────────────────────────────────────────

def test_run_on_10_digits():
    assert "[电话]" in sanitize.redact_phones("call me at 7187082268")


def test_hyphen_separated():
    assert sanitize.redact_phones("973-767-8887") == "[电话]"


def test_paren_area_code():
    assert sanitize.redact_phones("(917) 250-9767") == "[电话]"


def test_dotted():
    assert sanitize.redact_phones("917.250.9767") == "[电话]"


def test_with_country_code():
    assert sanitize.redact_phones("1-917-250-9767") == "[电话]"


def test_with_plus_one():
    assert "[电话]" in sanitize.redact_phones("+1 (917) 250-9767")


def test_mixed_with_chinese():
    out = sanitize.redact_phones("法拉盛日餐7187082268请师傅")
    assert "7187082268" not in out
    assert "[电话]" in out


def test_multiple_phones_in_title():
    out = sanitize.redact_phones("call 7187082268 or 973-767-8887")
    assert out.count("[电话]") == 2


# ─────────────────────────────────────────────────────────────
# Non-matches (numeric strings that aren't phones)
# ─────────────────────────────────────────────────────────────

def test_short_number_not_redacted():
    assert sanitize.redact_phones("salary 5000") == "salary 5000"


def test_year_not_redacted():
    assert sanitize.redact_phones("posted 2026") == "posted 2026"


def test_seven_digit_number_not_redacted():
    assert sanitize.redact_phones("invoice 1234567") == "invoice 1234567"


# ─────────────────────────────────────────────────────────────
# Empty / None
# ─────────────────────────────────────────────────────────────

def test_empty_passthrough():
    assert sanitize.redact_phones("") == ""


def test_none_passthrough():
    assert sanitize.redact_phones(None) is None


# ─────────────────────────────────────────────────────────────
# sanitize_title is the public wrapper
# ─────────────────────────────────────────────────────────────

def test_sanitize_title_runs_redact():
    out = sanitize.sanitize_title("call 7187082268")
    assert "[电话]" in out
