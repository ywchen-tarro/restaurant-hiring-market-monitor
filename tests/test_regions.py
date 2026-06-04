"""Unit tests for scraper.regions.

Covers the critical correctness paths: Chinese substring matching, English
word-boundary matching (the `SUNNYVALE → NY` class of bug), longest-token-
first precedence, and the region_for inverse lookup.
"""

from __future__ import annotations

from scraper import regions


# ─────────────────────────────────────────────────────────────
# Chinese substring matching
# ─────────────────────────────────────────────────────────────

def test_zh_state_in_title():
    region, state = regions.classify("法拉盛餐厅请熟手炒锅")
    assert region == "东部"
    assert state == "法拉盛"


def test_zh_california_city():
    region, state = regions.classify("Rosemead 海鲜餐馆请打杂")
    assert region == "西部"
    assert state == "Rosemead"


def test_zh_upstate_ny():
    region, state = regions.classify("上州日餐请师傅")
    assert region == "东部"
    assert state == "上州"


def test_zh_arcadia():
    region, state = regions.classify("阿凯迪亚mall烫吧招聘")
    assert region == "西部"
    assert state == "阿凯迪亚"


def test_zh_atlanta():
    region, state = regions.classify("亚特兰大日餐请熟手炒锅")
    assert region == "南部"
    assert state == "亚特兰大"


# ─────────────────────────────────────────────────────────────
# Virginia must be South (US Census), NOT East
# ─────────────────────────────────────────────────────────────

def test_va_is_south():
    region, state = regions.classify("维吉尼亚中餐招聘")
    assert region == "南部"


# ─────────────────────────────────────────────────────────────
# ASCII tokens: word-boundary matching (the SUNNYVALE → NY bug)
# ─────────────────────────────────────────────────────────────

def test_sunnyvale_does_not_match_ny():
    """Substring matching would match 'NY' inside 'SUNNYVALE' → East.
    With word boundaries, Sunnyvale resolves to its CA-named entry → West.
    """
    region, _ = regions.classify("SUNNYVALE restaurant hiring")
    assert region == "西部"


def test_continental_does_not_match_ct():
    region, _ = regions.classify("CONTINENTAL kitchen招聘")
    assert region is None  # No CA state token matches


def test_ny_with_boundary():
    region, state = regions.classify("restaurant in NY hiring")
    assert region == "东部"
    assert state == "NY"


def test_california_full_name_matches():
    region, state = regions.classify("California 日餐招聘")
    assert region == "西部"


def test_arkansas_lowercase_matches_case_insensitive():
    """ASCII tokens are word-boundary regex AND case-insensitive."""
    region, _ = regions.classify("arkansas restaurant 招聘")
    assert region == "南部"


# ─────────────────────────────────────────────────────────────
# Longest-token-first precedence
# ─────────────────────────────────────────────────────────────

def test_washington_dc_beats_washington_state():
    """'华盛顿DC' must match before 'washington' (state)."""
    region, state = regions.classify("华盛顿DC的餐厅")
    assert region == "东部"
    assert state == "华盛顿DC"


def test_san_francisco_beats_bare_san():
    region, state = regions.classify("San Francisco 日餐")
    assert region == "西部"
    assert state == "San Francisco"


def test_classify_city_requested_market():
    city = regions.classify_city("法拉盛餐馆请busboys")
    assert city["name"] == "法拉盛"
    assert city["region"] == "东部"


def test_classify_city_ascii_boundary():
    assert regions.classify_city("SUNNYVALERESTAURANT hiring") is None
    assert regions.classify_city("SUNNYVALE restaurant hiring")["name"] == "森尼韦尔"
    city = regions.classify_city("San Jose sushi chef")
    assert city["name"] == "圣何塞"


def test_classify_city_upstate_not_new_york_city():
    assert regions.classify_city("纽约上州日餐请师傅") is None


def test_classify_city_chinese_community_aliases():
    assert regions.classify_city("尔湾轻食餐厅招后厨")["name"] == "尔湾"
    assert regions.classify_city("蒙市中餐馆请炒锅")["name"] == "蒙特利公园"
    assert regions.classify_city("Great Neck餐厅请企台")["name"] == "长岛"


def test_classify_city_major_market_expansion():
    assert regions.classify_city("Plano sushi restaurant hiring")["name"] == "普莱诺"
    assert regions.classify_city("Rockville 马里兰诚请熟手男企台")["name"] == "罗克维尔"
    assert regions.classify_city("Milpitas中餐馆诚招炒锅")["name"] == "米尔皮塔斯"


def test_city_catalog_has_coordinates_for_all_markets():
    missing = [c["name"] for c in regions.city_catalog() if c.get("lon") is None or c.get("lat") is None]
    assert missing == []


# ─────────────────────────────────────────────────────────────
# region_for inverse lookup
# ─────────────────────────────────────────────────────────────

def test_region_for_known_state():
    assert regions.region_for("法拉盛") == "东部"
    assert regions.region_for("加州") == "西部"
    assert regions.region_for("亚特兰大") == "南部"
    assert regions.region_for("芝加哥") == "中部"


def test_region_for_unknown_state():
    assert regions.region_for("Pluto City") is None


def test_region_for_empty():
    assert regions.region_for("") is None
    assert regions.region_for(None) is None


# ─────────────────────────────────────────────────────────────
# Empty / None inputs
# ─────────────────────────────────────────────────────────────

def test_classify_empty_string():
    assert regions.classify("") == (None, None)


def test_classify_no_match():
    region, state = regions.classify("just a plain English sentence")
    assert region is None
    assert state is None
