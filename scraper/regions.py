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


# City/metro markets requested for post-level granularity. `name` is the
# dashboard key (Chinese display form); `state` is any token that already maps
# to a USPS code in i18n.js so the existing state choropleth keeps working.
CITY_MARKETS = [
    {
        "name": "纽约", "en": "New York, NY", "region": "东部", "state": "纽约",
        "tokens": ["New York, NY", "New York City", "NYC", "纽约"],
    },
    {
        "name": "洛杉矶", "en": "Los Angeles, CA", "region": "西部", "state": "洛杉矶",
        "tokens": ["Los Angeles", "LA", "L.A.", "洛杉矶", "洛杉磯"],
    },
    {
        "name": "布鲁克林", "en": "Brooklyn, New York", "region": "东部", "state": "布鲁克林",
        "tokens": ["Brooklyn", "布鲁克林", "布鲁伦"],
    },
    {
        "name": "旧金山-奥克兰-圣何塞", "en": "San Francisco-Oakland-San Jose, CA", "region": "西部", "state": "旧金山",
        "tokens": ["San Francisco-Oakland-San Jose", "San Francisco Bay Area", "Bay Area", "旧金山-奥克兰-圣何塞", "旧金山湾区", "湾区", "旧金山"],
    },
    {
        "name": "休斯顿", "en": "Houston, TX", "region": "南部", "state": "休斯顿",
        "tokens": ["Houston", "休斯顿"],
    },
    {
        "name": "芝加哥", "en": "Chicago, IL", "region": "中部", "state": "芝加哥",
        "tokens": ["Chicago", "芝加哥"],
    },
    {
        "name": "费城", "en": "Philadelphia, PA", "region": "东部", "state": "费城",
        "tokens": ["Philadelphia", "Philly", "费城"],
    },
    {
        "name": "拉斯维加斯", "en": "Las Vegas, NV", "region": "西部", "state": "拉斯维加斯",
        "tokens": ["Las Vegas", "Vegas", "拉斯维加斯"],
    },
    {
        "name": "奥兰多-代托纳海滩-墨尔本", "en": "Orlando-Daytona Beach-Melbourne, FL", "region": "南部", "state": "奥兰多",
        "tokens": ["Orlando-Daytona Beach-Melbourne", "Orlando", "Daytona Beach", "Melbourne", "奥兰多-代托纳海滩-墨尔本", "奥兰多", "代托纳", "墨尔本"],
    },
    {
        "name": "西雅图-塔科马", "en": "Seattle-Tacoma, WA", "region": "西部", "state": "西雅图",
        "tokens": ["Seattle-Tacoma", "Seattle", "Tacoma", "西雅图-塔科马", "西雅图", "塔科马"],
    },
    {
        "name": "迈阿密-劳德代尔堡", "en": "Miami-Ft. Lauderdale, FL", "region": "南部", "state": "迈阿密",
        "tokens": ["Miami-Ft. Lauderdale", "Miami", "Fort Lauderdale", "Ft. Lauderdale", "迈阿密-劳德代尔堡", "迈阿密", "劳德代尔堡"],
    },
    {
        "name": "波特兰", "en": "Portland, OR", "region": "西部", "state": "波特兰",
        "tokens": ["Portland", "波特兰"],
    },
    {
        "name": "圣地亚哥", "en": "San Diego, CA", "region": "西部", "state": "圣地亚哥",
        "tokens": ["San Diego", "圣地亚哥"],
    },
    {
        "name": "布朗克斯", "en": "The Bronx, New York", "region": "东部", "state": "纽约",
        "tokens": ["The Bronx", "Bronx", "布朗克斯"],
    },
    {
        "name": "奥斯汀", "en": "Austin, TX", "region": "南部", "state": "德州",
        "tokens": ["Austin", "奥斯汀"],
    },
    {
        "name": "亚特兰大", "en": "Atlanta, GA", "region": "南部", "state": "亚特兰大",
        "tokens": ["Atlanta", "亚特兰大"],
    },
    {
        "name": "圣安东尼奥", "en": "San Antonio, TX", "region": "南部", "state": "德州",
        "tokens": ["San Antonio", "圣安东尼奥"],
    },
    {
        "name": "凤凰城", "en": "Phoenix, AZ", "region": "西部", "state": "凤凰城",
        "tokens": ["Phoenix", "凤凰城"],
    },
    {
        "name": "达拉斯-沃思堡", "en": "Dallas-Ft. Worth, TX", "region": "南部", "state": "达拉斯",
        "tokens": ["Dallas-Ft. Worth", "Dallas-Fort Worth", "Dallas", "Fort Worth", "Ft. Worth", "达拉斯-沃思堡", "达拉斯", "沃思堡"],
    },
    {
        "name": "杰克逊维尔", "en": "Jacksonville, FL", "region": "南部", "state": "杰克逊维尔",
        "tokens": ["Jacksonville", "杰克逊维尔"],
    },
    {
        "name": "夏洛特", "en": "Charlotte, NC", "region": "南部", "state": "夏洛特",
        "tokens": ["Charlotte", "夏洛特"],
    },
    {
        "name": "萨克拉门托-斯托克顿-莫德斯托", "en": "Sacramento-Stockton-Modesto, CA", "region": "西部", "state": "加州",
        "tokens": ["Sacramento-Stockton-Modesto", "Sacramento", "Stockton", "Modesto", "萨克拉门托-斯托克顿-莫德斯托", "萨克拉门托", "斯托克顿", "莫德斯托"],
    },
    {
        "name": "法拉盛", "en": "Flushing, New York", "region": "东部", "state": "法拉盛",
        "tokens": ["Flushing", "法拉盛"],
    },
    {
        "name": "圣何塞", "en": "San Jose, CA", "region": "西部", "state": "圣何塞",
        "tokens": ["San Jose", "圣何塞"],
    },
    {
        "name": "坦帕-圣彼得堡（萨拉索塔）", "en": "Tampa-St. Petersburg (Sarasota), FL", "region": "南部", "state": "坦帕",
        "tokens": ["Tampa-St. Petersburg", "Tampa", "St. Petersburg", "Sarasota", "坦帕-圣彼得堡", "坦帕", "圣彼得堡", "萨拉索塔"],
    },
    {
        "name": "华盛顿特区（黑格斯敦）", "en": "Washington DC (Hagerstown MD)", "region": "东部", "state": "华盛顿DC",
        "tokens": ["Washington DC", "Washington, DC", "Hagerstown", "华盛顿特区", "华盛顿DC", "黑格斯敦"],
    },
    {
        "name": "印第安纳波利斯", "en": "Indianapolis, IN", "region": "中部", "state": "印第安纳波利斯",
        "tokens": ["Indianapolis", "印第安纳波利斯"],
    },
    {
        "name": "丹佛", "en": "Denver, CO", "region": "西部", "state": "丹佛",
        "tokens": ["Denver", "丹佛"],
    },
    {
        "name": "巴尔的摩", "en": "Baltimore, MD", "region": "南部", "state": "马里兰",
        "tokens": ["Baltimore", "巴尔的摩"],
    },
    {
        "name": "圣路易斯", "en": "St. Louis, MO", "region": "中部", "state": "圣路易斯",
        "tokens": ["St. Louis", "Saint Louis", "圣路易斯"],
    },
    {
        "name": "弗吉尼亚海滩", "en": "Virginia Beach, VA", "region": "南部", "state": "维吉尼亚",
        "tokens": ["Virginia Beach", "弗吉尼亚海滩"],
    },
    {
        "name": "奥克兰", "en": "Oakland, CA", "region": "西部", "state": "奥克兰",
        "tokens": ["Oakland", "奥克兰"],
    },
    {
        "name": "埃尔帕索", "en": "El Paso, TX", "region": "南部", "state": "德州",
        "tokens": ["El Paso", "埃尔帕索"],
    },
    {
        "name": "哥伦布", "en": "Columbus, OH", "region": "中部", "state": "哥伦布",
        "tokens": ["Columbus", "哥伦布"],
    },
    {
        "name": "路易斯维尔", "en": "Louisville, KY", "region": "南部", "state": "肯塔基",
        "tokens": ["Louisville", "路易斯维尔"],
    },
    {
        "name": "俄克拉何马城", "en": "Oklahoma City, OK", "region": "南部", "state": "俄克拉荷马",
        "tokens": ["Oklahoma City", "OKC", "俄克拉何马城", "俄克拉荷马城"],
    },
    {
        "name": "弗雷斯诺-维萨利亚", "en": "Fresno-Visalia, CA", "region": "西部", "state": "加州",
        "tokens": ["Fresno-Visalia", "Fresno", "Visalia", "弗雷斯诺-维萨利亚", "弗雷斯诺", "维萨利亚"],
    },
    {
        "name": "图森（塞拉维斯塔）", "en": "Tucson (Sierra Vista), AZ", "region": "西部", "state": "亚利桑那",
        "tokens": ["Tucson", "Sierra Vista", "图森", "塞拉维斯塔"],
    },
    {
        "name": "波士顿-曼彻斯特", "en": "Boston MA-Manchester NH", "region": "东部", "state": "波士顿",
        "tokens": ["Boston-Manchester", "Boston", "Manchester NH", "波士顿-曼彻斯特", "波士顿", "曼彻斯特"],
    },
    {
        "name": "斯塔滕岛", "en": "Staten Island, New York", "region": "东部", "state": "纽约",
        "tokens": ["Staten Island", "斯塔滕岛"],
    },
    {
        "name": "阿尔伯克基-圣菲", "en": "Albuquerque-Santa Fe, NM", "region": "西部", "state": "新墨西哥",
        "tokens": ["Albuquerque-Santa Fe", "Albuquerque", "Santa Fe", "阿尔伯克基-圣菲", "阿尔伯克基", "圣菲"],
    },
]


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

_CITY_TOKENS = []  # list of (token, city_info, ascii_pattern_or_None)
for _city in CITY_MARKETS:
    for _t in _city["tokens"]:
        pattern = None
        if _is_ascii_token(_t):
            pattern = re.compile(r'\b' + re.escape(_t) + r'\b', re.IGNORECASE)
        _CITY_TOKENS.append((_t, _city, pattern))
_CITY_TOKENS.sort(key=lambda x: len(x[0]), reverse=True)


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


def classify_city(text: str) -> Optional[dict]:
    """Return canonical city/metro info when text mentions a tracked market.

    The result is one entry from CITY_MARKETS. It is safe to serialize; callers
    should usually store only `name` on the post and aggregate with this helper.
    """
    if not text:
        return None
    lower_text = text.lower()
    # "纽约上州" is a common way to mean upstate NY rather than NYC.
    if "上州" in text or "upstate" in lower_text:
        ny_names = {"纽约", "New York, NY"}
    else:
        ny_names = set()
    for token, city, pattern in _CITY_TOKENS:
        if city["name"] in ny_names:
            continue
        if _matches(text, token, pattern):
            return city
    return None


def city_info(name: str) -> Optional[dict]:
    """Look up a canonical city/metro entry by its Chinese `name`."""
    if not name:
        return None
    for city in CITY_MARKETS:
        if city["name"] == name:
            return city
    return None


def region_for(state: str) -> Optional[str]:
    """Look up the region for an already-known state token."""
    if not state:
        return None
    for token, _, region, _pat in _TOKENS:
        if token == state:
            return region
    return None
