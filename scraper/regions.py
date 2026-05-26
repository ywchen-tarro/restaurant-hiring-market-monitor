"""Region/state classification for US restaurant job posts.

Match the longest substring first so '纽约上州' resolves to '上州' (东部)
rather than '纽约' (also 东部 here, but disambiguation matters for some pairs).
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

REGION_MAP = {
    "东部": [
        # state-level
        "纽约", "上州", "宾州", "康州", "麻州", "新泽西", "缅因", "罗得岛",
        "佛蒙特", "特拉华", "新罕布什尔",
        # NY/NJ/MA cities
        "曼哈顿", "布鲁伦", "布鲁克林", "法拉盛", "皇后区", "长岛", "波士顿",
        "费城", "华盛顿DC", "Washington DC", "新泽西", "纽瓦克", "泽西市",
        "Boston", "Philadelphia", "New York", "Manhattan", "Brooklyn",
        "Flushing", "Queens", "Long Island",
        # English state abbreviations / names
        "NY", "NJ", "MA", "CT", "PA", "VT", "DE", "NH", "RI", "ME",
        "New Jersey", "Massachusetts", "Connecticut",
        "Pennsylvania", "Vermont", "Delaware",
    ],
    "南部": [
        # states (note: VA / Virginia is South per US Census)
        "佛州", "德州", "南卡", "北卡", "马里兰", "乔治亚", "田纳西",
        "路易斯安娜", "肯塔基", "密西西比", "俄克拉荷马", "阿拉巴马",
        "西维吉尼亚", "阿肯色", "维吉尼亚",
        # cities
        "迈阿密", "亚特兰大", "达拉斯", "休斯顿", "奥兰多", "坦帕",
        "夏洛特", "罗利", "纳什维尔", "新奥尔良", "孟菲斯", "杰克逊维尔",
        "Miami", "Atlanta", "Dallas", "Houston", "Orlando", "Tampa",
        "Charlotte", "Raleigh", "Nashville", "New Orleans", "Memphis",
        # codes / English
        "FL", "TX", "GA", "NC", "SC", "TN", "MD", "KY", "AL", "MS",
        "LA", "AR", "OK", "WV", "VA",
        "Florida", "Texas", "Georgia", "Maryland", "Virginia",
        "Tennessee", "Louisiana", "Arkansas", "Alabama", "Mississippi",
        "Kentucky", "Oklahoma", "West Virginia",
        "North Carolina", "South Carolina",
    ],
    "中部": [
        # states
        "伊州", "俄亥俄", "密苏里", "堪萨斯", "爱荷华", "密歇根",
        "明尼苏达", "南达科他", "北达科他", "印第安纳", "威斯康星",
        "内布拉斯加",
        # cities
        "芝加哥", "底特律", "印第安纳波利斯", "明尼阿波利斯",
        "圣路易斯", "克利夫兰", "哥伦布", "辛辛那提", "密尔沃基",
        "堪萨斯城",
        "Chicago", "Detroit", "Minneapolis", "Cleveland",
        "Indianapolis", "Milwaukee", "Columbus", "Cincinnati",
        "St. Louis", "Kansas City",
        # codes
        "IL", "MI", "MN", "OH", "IN", "WI", "MO", "IA", "KS", "NE",
        "SD", "ND",
        "Illinois", "Michigan", "Minnesota", "Ohio", "Indiana",
        "Wisconsin", "Missouri", "Iowa", "Kansas", "Nebraska",
        "South Dakota", "North Dakota",
    ],
    "西部": [
        # states (NOTE: bare "Washington" is ambiguous with DC; we use
        # "Washington州" / "WA" / "华盛顿州" only)
        "加州", "犹他", "夏威夷", "内华达", "蒙大拿", "俄勒冈", "爱达荷",
        "怀俄明", "华盛顿州", "Washington州", "亚利桑那", "科罗拉多",
        "阿拉斯加", "新墨西哥",
        # CA cities — broad coverage since the SoCal/Bay-Area Chinese
        # community uses many specific city names in posts
        "洛杉矶", "旧金山", "湾区", "圣地亚哥", "尔湾", "圣何塞", "奥克兰",
        "圣盖博", "蒙特利公园", "蒙市", "阿罕布拉", "阿罕布拉市",
        "罗兰岗", "罗兰岡", "钻石吧", "钻石吧市", "核桃", "核桃市",
        "哈仙达", "哈仙达岗", "阿凯迪亚", "阿凯迪亚市",
        "罗斯密", "Rosemead", "Arcadia", "Gardena", "加迪纳",
        "圣马利诺", "天普市", "都柏林", "Dublin",
        "弗里蒙特", "库柏蒂诺", "圣塔克拉拉", "圣马刁",
        "Sunnyvale", "Cupertino", "Fremont", "Oakland", "San Jose",
        "Los Angeles", "San Francisco", "San Diego",
        # OR/WA cities
        "波特兰", "西雅图", "Portland", "Seattle", "Beaverton", "Bellevue",
        # AZ / NV / CO / UT / HI cities
        "凤凰城", "丹佛", "拉斯维加斯", "盐湖城", "檀香山",
        "Phoenix", "Denver", "Las Vegas", "Salt Lake City",
        # codes
        "CA", "WA", "NV", "AZ", "CO", "OR", "UT", "ID", "MT", "WY", "AK", "HI", "NM",
        "California", "Nevada", "Arizona", "Colorado", "Oregon", "Hawaii",
        "Utah", "New Mexico", "Wyoming", "Montana", "Idaho", "Alaska",
    ],
}


def _is_ascii_token(t: str) -> bool:
    """ASCII-only tokens (state codes like 'NY', names like 'California') need
    word-boundary matching. Chinese tokens use substring matching since CJK
    has no spaces. Mixed-script tokens (e.g. '华盛顿DC') treat as Chinese."""
    return all(ord(c) < 128 for c in t)


# Pre-build a flat list of (token, state, region), sorted by token length desc
# so we match longer/more-specific tokens first. ASCII tokens get a compiled
# word-boundary regex; Chinese tokens use plain substring containment.
_TOKENS = []  # list of (token, state, region, ascii_pattern_or_None)
for _region, _tokens in REGION_MAP.items():
    for _t in _tokens:
        pattern = None
        if _is_ascii_token(_t):
            pattern = re.compile(r'\b' + re.escape(_t) + r'\b', re.IGNORECASE)
        _TOKENS.append((_t, _t, _region, pattern))
_TOKENS.sort(key=lambda x: len(x[0]), reverse=True)


def _matches(text: str, token: str, pattern) -> bool:
    if pattern is not None:
        return bool(pattern.search(text))
    return token in text


def classify(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Return (region, state) for the first matching token in `text`.

    State is the matched token verbatim (Chinese name preferred). Region is
    one of: '东部' / '南部' / '中部' / '西部'. Returns (None, None) if nothing matches.

    ASCII tokens are matched with word boundaries to avoid e.g. `SUNNYVALE`
    matching `NY` or `SAN JOSE` matching `OR`.
    """
    if not text:
        return None, None
    for token, state, region, pattern in _TOKENS:
        if _matches(text, token, pattern):
            return region, state
    return None, None


def region_for(state: str) -> Optional[str]:
    """Look up the region for an already-known state token."""
    if not state:
        return None
    for token, _, region, _pat in _TOKENS:
        if token == state:
            return region
    return None
