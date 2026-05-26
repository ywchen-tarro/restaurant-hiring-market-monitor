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


# ─────────────────────────────────────────────────────────────
# 师傅 / 打包 are no longer strong (must combine with venue/role)
# ─────────────────────────────────────────────────────────────

def test_bare_师傅_does_not_qualify():
    """A title that matches only `师傅` (no venue, no other role) is
    rejected — too many non-restaurant trades use 师傅 (装修师傅,
    安装师傅, 裁缝师傅)."""
    assert keywords.is_restaurant("一流师傅拉面") is False
    assert keywords.is_restaurant("曼哈顿招聘兼职烫粉师傅") is False
    assert keywords.is_restaurant("纽约长岛Great Neck(大颈）招包馄饨/水饺 师傅") is False


def test_bare_打包_does_not_qualify():
    """`打包` alone often means warehouse packing, not restaurant takeout."""
    assert keywords.is_restaurant("自营仓大量聘请打包员拣货员") is False


def test_师傅_with_strong_venue_kept():
    assert keywords.is_restaurant("寿司师傅") is True
    assert keywords.is_restaurant("中餐师傅") is True
    assert keywords.is_restaurant("法拉盛日餐请熟手师傅") is True


def test_打包_with_strong_venue_kept():
    assert keywords.is_restaurant("中餐外卖店请打包") is True


def test_师傅_with_strong_role_kept():
    """A role + 师傅 should still match via the role half (师傅 itself
    is no longer strong, but 炒锅 is)."""
    assert keywords.is_restaurant("炒锅师傅") is True
    assert keywords.is_restaurant("熟手油锅师傅") is True


# ─────────────────────────────────────────────────────────────
# Negative-keyword filter — non-restaurant trade jobs
# ─────────────────────────────────────────────────────────────

def test_negative_keyword_drops_non_restaurant_trade():
    """Posts with negative keywords AND no venue keyword are dropped
    even if they match a role keyword."""
    # User-listed examples:
    assert keywords.is_restaurant("电工维修/技工/师傅") is False
    assert keywords.is_restaurant("安装门窗公司招聘安装师傅") is False
    assert keywords.is_restaurant("布鲁克林干洗改衣店急聘熟手改衣裁缝师傅") is False
    assert keywords.is_restaurant("纽约皇后区汽车内饰改装招聘安装师傅") is False
    assert keywords.is_restaurant("大理石台面安装师傅") is False


def test_negative_keyword_with_venue_still_kept():
    """If a strong VENUE keyword is present, the post passes even if a
    negative keyword co-occurs (e.g. 餐馆水电维修工 — restaurant
    electrician is still a restaurant supply-chain job)."""
    assert keywords.is_restaurant("法拉盛招聘 餐馆水电维修工 木工 电工 杂工") is True
    assert keywords.is_restaurant("奶茶批发请仓库兼送货") is True


def test_negative_keyword_traditional_chinese_variants():
    """The negative list includes both Simp and Trad forms."""
    assert keywords.is_restaurant("急聘師傅 裝修工程") is False  # 裝修 = 装修
    assert keywords.is_restaurant("門窗安裝師傅") is False        # 門窗 = 门窗


def test_matched_negatives_helper():
    """matched_negatives reports which negative tokens hit (diagnostic)."""
    hits = keywords.matched_negatives("布鲁克林干洗改衣店急聘师傅")
    assert "干洗" in hits
    assert "改衣" in hits


def test_match_excludes_negative_from_display():
    """match() should NOT include negative keywords in keywords_matched —
    we don't want a restaurant post tagged "电工" on the dashboard just
    because of a co-occurrence."""
    hits = keywords.match("餐馆水电维修工")
    assert "电工" not in hits
    assert "维修" not in hits
