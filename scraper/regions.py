"""Region/state classification for US restaurant job posts.

Match the longest substring first so '纽约上州' resolves to '上州' (东部)
rather than '纽约' (also 东部 here, but disambiguation matters for some pairs).
"""

from __future__ import annotations

from typing import List, Optional, Tuple

REGION_MAP = {
    "东部": [
        "纽约", "上州", "宾州", "康州", "麻州", "新泽西", "缅因", "罗得岛",
        "维吉尼亚", "佛蒙特", "特拉华", "新罕布什尔", "曼哈顿", "布鲁伦",
        "布鲁克林", "法拉盛", "皇后区", "长岛", "波士顿", "费城", "华盛顿DC",
        "NY", "NJ", "MA", "CT", "PA", "VA", "VT", "DE", "NH", "RI", "ME",
        "New York", "New Jersey", "Massachusetts", "Connecticut",
        "Pennsylvania", "Virginia", "Vermont", "Delaware",
    ],
    "南部": [
        "佛州", "德州", "南卡", "北卡", "马里兰", "乔治亚", "田纳西",
        "路易斯安娜", "肯塔基", "密西西比", "俄克拉荷马", "阿拉巴马",
        "西维吉尼亚", "阿肯色", "迈阿密", "亚特兰大", "达拉斯", "休斯顿",
        "奥兰多", "坦帕", "夏洛特", "罗利",
        "FL", "TX", "GA", "NC", "SC", "TN", "MD", "KY", "AL", "MS",
        "LA", "AR", "OK", "WV",
        "Florida", "Texas", "Georgia", "Maryland",
    ],
    "中部": [
        "伊州", "俄亥俄", "密苏里", "堪萨斯", "爱荷华", "密歇根",
        "明尼苏达", "南达科他", "北达科他", "印第安纳", "威斯康星",
        "内布拉斯加", "芝加哥", "底特律", "印第安纳波利斯", "明尼阿波利斯",
        "圣路易斯", "克利夫兰", "哥伦布", "辛辛那提",
        "IL", "MI", "MN", "OH", "IN", "WI", "MO", "IA", "KS", "NE",
        "SD", "ND",
        "Illinois", "Michigan", "Minnesota", "Ohio", "Indiana",
    ],
    "西部": [
        "加州", "犹他", "夏威夷", "内华达", "蒙大拿", "俄勒冈", "爱达荷",
        "怀俄明", "华盛顿州", "亚利桑那", "科罗拉多", "阿拉斯加", "新墨西哥",
        "洛杉矶", "旧金山", "湾区", "西雅图", "圣地亚哥", "尔湾",
        "圣何塞", "奥克兰", "波特兰", "凤凰城", "丹佛", "拉斯维加斯",
        "盐湖城",
        "CA", "WA", "NV", "AZ", "CO", "OR", "UT", "ID", "MT", "WY", "AK", "HI", "NM",
        "California", "Washington", "Nevada", "Arizona", "Colorado", "Oregon",
    ],
}


# Pre-build a flat list of (token, state, region), sorted by token length desc
# so we match longer/more-specific tokens first.
_TOKENS = []  # list of (token, state, region)
for _region, _tokens in REGION_MAP.items():
    for _t in _tokens:
        _TOKENS.append((_t, _t, _region))
_TOKENS.sort(key=lambda x: len(x[0]), reverse=True)


def classify(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Return (region, state) for the first matching token in `text`.

    State is the matched token verbatim (Chinese name preferred). Region is
    one of: '东部' / '南部' / '中部' / '西部'. Returns (None, None) if nothing matches.
    """
    if not text:
        return None, None
    for token, state, region in _TOKENS:
        if token in text:
            return region, state
    return None, None


def region_for(state: str) -> Optional[str]:
    """Look up the region for an already-known state token."""
    if not state:
        return None
    for token, _, region in _TOKENS:
        if token == state:
            return region
    return None
