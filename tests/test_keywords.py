"""Unit tests for scraper.keywords.

The strong/weak split is the project's primary defense against
false-positive restaurant matches (medical-supply, swim school, spa, etc.
that hire `前台` or `招聘 收银`).
"""

from __future__ import annotations

from scraper import keywords


def test_strong_venue_match():
    assert keywords.is_restaurant("法拉盛日餐请熟手厨师") is True


def test_strong_role_match():
    assert keywords.is_restaurant("急聘炒锅师傅") is True


def test_traditional_chinese_match():
    assert keywords.is_restaurant("廚房學徒") is True


def test_weak_only_招聘_drops():
    """`招聘` alone is too generic — would match medical, swim school,
    spa, retail. Should NOT qualify as restaurant."""
    assert keywords.is_restaurant("Brooklyn 脊椎诊所招聘 2名") is False


def test_weak_only_前台_drops():
    assert keywords.is_restaurant("医疗器材请全职前台") is False


def test_weak_only_收银_drops():
    assert keywords.is_restaurant("超市急聘收银") is False


def test_weak_plus_strong_keeps():
    # If 招聘 co-occurs with a strong term, restaurant is kept.
    assert keywords.is_restaurant("法拉盛日餐招聘前台") is True


def test_match_returns_all_hits():
    hits = keywords.match("急聘炒锅师傅，前台招聘")
    assert "炒锅" in hits
    assert "师傅" in hits
    assert "前台" in hits
    assert "招聘" in hits


def test_match_empty_title():
    assert keywords.match("") == []
    assert keywords.match(None) == []


def test_match_no_keywords_in_title():
    assert keywords.match("hello world") == []


def test_split_matches():
    strong, weak = keywords.split_matches("中日餐请熟手炒锅，招聘前台")
    # Strong matches: 中日餐 covers venue (matches '日餐' / '餐'), '炒锅' covers role
    assert any(s in strong for s in ("日餐", "餐", "炒锅"))
    # Weak matches: 招聘 + 前台
    assert "招聘" in weak
    assert "前台" in weak


def test_is_restaurant_with_none():
    assert keywords.is_restaurant(None) is False
    assert keywords.is_restaurant("") is False
