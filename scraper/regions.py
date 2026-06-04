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
    # Additional high-signal city markets and common Chinese community aliases.
    {
        "name": "曼哈顿", "en": "Manhattan, New York", "region": "东部", "state": "曼哈顿",
        "tokens": ["Manhattan", "曼哈顿"],
    },
    {
        "name": "皇后区", "en": "Queens, New York", "region": "东部", "state": "皇后区",
        "tokens": ["Queens", "Queen's", "皇后区", "皇后"],
    },
    {
        "name": "长岛", "en": "Long Island, New York", "region": "东部", "state": "长岛",
        "tokens": ["Long Island", "Great Neck", "大颈", "长岛"],
    },
    {
        "name": "泽西市", "en": "Jersey City, NJ", "region": "东部", "state": "泽西市",
        "tokens": ["Jersey City", "泽西市"],
    },
    {
        "name": "纽瓦克", "en": "Newark, NJ", "region": "东部", "state": "纽瓦克",
        "tokens": ["Newark NJ", "Newark, NJ", "纽瓦克"],
    },
    {
        "name": "爱迪生", "en": "Edison, NJ", "region": "东部", "state": "新泽西",
        "tokens": ["Edison NJ", "Edison, NJ", "爱迪生"],
    },
    {
        "name": "昆西", "en": "Quincy, MA", "region": "东部", "state": "麻州",
        "tokens": ["Quincy MA", "Quincy, MA", "昆西"],
    },
    {
        "name": "罗克维尔", "en": "Rockville, MD", "region": "南部", "state": "马里兰",
        "tokens": ["Rockville", "罗克维尔"],
    },
    {
        "name": "匹兹堡", "en": "Pittsburgh, PA", "region": "东部", "state": "宾州",
        "tokens": ["Pittsburgh", "匹兹堡"],
    },
    {
        "name": "尔湾", "en": "Irvine, CA", "region": "西部", "state": "尔湾",
        "tokens": ["Irvine", "尔湾", "爾灣"],
    },
    {
        "name": "圣盖博", "en": "San Gabriel, CA", "region": "西部", "state": "圣盖博",
        "tokens": ["San Gabriel", "圣盖博", "聖蓋博"],
    },
    {
        "name": "蒙特利公园", "en": "Monterey Park, CA", "region": "西部", "state": "蒙特利公园",
        "tokens": ["Monterey Park", "蒙特利公园", "蒙特利公園", "蒙市"],
    },
    {
        "name": "阿罕布拉", "en": "Alhambra, CA", "region": "西部", "state": "阿罕布拉",
        "tokens": ["Alhambra", "阿罕布拉", "阿市"],
    },
    {
        "name": "罗兰岗", "en": "Rowland Heights, CA", "region": "西部", "state": "罗兰岗",
        "tokens": ["Rowland Heights", "罗兰岗", "罗兰岡"],
    },
    {
        "name": "钻石吧", "en": "Diamond Bar, CA", "region": "西部", "state": "钻石吧",
        "tokens": ["Diamond Bar", "钻石吧"],
    },
    {
        "name": "核桃", "en": "Walnut, CA", "region": "西部", "state": "核桃",
        "tokens": ["Walnut CA", "Walnut, CA", "核桃市", "核桃"],
    },
    {
        "name": "哈仙达岗", "en": "Hacienda Heights, CA", "region": "西部", "state": "哈仙达岗",
        "tokens": ["Hacienda Heights", "哈仙达岗", "哈仙达"],
    },
    {
        "name": "阿凯迪亚", "en": "Arcadia, CA", "region": "西部", "state": "阿凯迪亚",
        "tokens": ["Arcadia", "阿凯迪亚"],
    },
    {
        "name": "罗斯密", "en": "Rosemead, CA", "region": "西部", "state": "罗斯密",
        "tokens": ["Rosemead", "罗斯密"],
    },
    {
        "name": "加迪纳", "en": "Gardena, CA", "region": "西部", "state": "加迪纳",
        "tokens": ["Gardena", "加迪纳"],
    },
    {
        "name": "弗里蒙特", "en": "Fremont, CA", "region": "西部", "state": "弗里蒙特",
        "tokens": ["Fremont", "弗里蒙特"],
    },
    {
        "name": "库比蒂诺", "en": "Cupertino, CA", "region": "西部", "state": "库柏蒂诺",
        "tokens": ["Cupertino", "库比蒂诺", "库柏蒂诺"],
    },
    {
        "name": "森尼韦尔", "en": "Sunnyvale, CA", "region": "西部", "state": "圣塔克拉拉",
        "tokens": ["Sunnyvale", "森尼韦尔", "森尼维尔"],
    },
    {
        "name": "圣塔克拉拉", "en": "Santa Clara, CA", "region": "西部", "state": "圣塔克拉拉",
        "tokens": ["Santa Clara", "圣塔克拉拉"],
    },
    {
        "name": "圣马刁", "en": "San Mateo, CA", "region": "西部", "state": "圣马刁",
        "tokens": ["San Mateo", "圣马刁"],
    },
    {
        "name": "米尔皮塔斯", "en": "Milpitas, CA", "region": "西部", "state": "加州",
        "tokens": ["Milpitas", "米尔皮塔斯"],
    },
    {
        "name": "都柏林", "en": "Dublin, CA", "region": "西部", "state": "都柏林",
        "tokens": ["Dublin CA", "Dublin, CA", "都柏林"],
    },
    {
        "name": "伯克利", "en": "Berkeley, CA", "region": "西部", "state": "加州",
        "tokens": ["Berkeley", "伯克利"],
    },
    {
        "name": "圣拉蒙", "en": "San Ramon, CA", "region": "西部", "state": "加州",
        "tokens": ["San Ramon", "Sanramon", "圣拉蒙"],
    },
    {
        "name": "橙县", "en": "Orange County, CA", "region": "西部", "state": "加州",
        "tokens": ["Orange County CA", "Orange County, CA", "OC CA", "橙县", "橙縣"],
    },
    {
        "name": "安纳海姆", "en": "Anaheim, CA", "region": "西部", "state": "加州",
        "tokens": ["Anaheim", "安纳海姆"],
    },
    {
        "name": "圣塔安娜", "en": "Santa Ana, CA", "region": "西部", "state": "加州",
        "tokens": ["Santa Ana", "圣塔安娜"],
    },
    {
        "name": "河滨", "en": "Riverside, CA", "region": "西部", "state": "加州",
        "tokens": ["Riverside CA", "Riverside, CA", "河滨"],
    },
    {
        "name": "安大略", "en": "Ontario, CA", "region": "西部", "state": "加州",
        "tokens": ["Ontario CA", "Ontario, CA", "安大略"],
    },
    {
        "name": "贝尔维尤", "en": "Bellevue, WA", "region": "西部", "state": "华盛顿州",
        "tokens": ["Bellevue", "贝尔维尤"],
    },
    {
        "name": "比弗顿", "en": "Beaverton, OR", "region": "西部", "state": "波特兰",
        "tokens": ["Beaverton", "比弗顿"],
    },
    {
        "name": "普莱诺", "en": "Plano, TX", "region": "南部", "state": "德州",
        "tokens": ["Plano", "普莱诺"],
    },
    {
        "name": "凯蒂", "en": "Katy, TX", "region": "南部", "state": "德州",
        "tokens": ["Katy TX", "Katy, TX", "凯蒂"],
    },
    {
        "name": "糖城", "en": "Sugar Land, TX", "region": "南部", "state": "德州",
        "tokens": ["Sugar Land", "糖城"],
    },
    {
        "name": "罗利", "en": "Raleigh, NC", "region": "南部", "state": "罗利",
        "tokens": ["Raleigh", "罗利"],
    },
    {
        "name": "纳什维尔", "en": "Nashville, TN", "region": "南部", "state": "纳什维尔",
        "tokens": ["Nashville", "纳什维尔"],
    },
    {
        "name": "孟菲斯", "en": "Memphis, TN", "region": "南部", "state": "孟菲斯",
        "tokens": ["Memphis", "孟菲斯"],
    },
    {
        "name": "新奥尔良", "en": "New Orleans, LA", "region": "南部", "state": "新奥尔良",
        "tokens": ["New Orleans", "新奥尔良"],
    },
    {
        "name": "底特律", "en": "Detroit, MI", "region": "中部", "state": "底特律",
        "tokens": ["Detroit", "底特律"],
    },
    {
        "name": "克利夫兰", "en": "Cleveland, OH", "region": "中部", "state": "克利夫兰",
        "tokens": ["Cleveland", "克利夫兰"],
    },
    {
        "name": "辛辛那提", "en": "Cincinnati, OH", "region": "中部", "state": "辛辛那提",
        "tokens": ["Cincinnati", "辛辛那提"],
    },
    {
        "name": "密尔沃基", "en": "Milwaukee, WI", "region": "中部", "state": "密尔沃基",
        "tokens": ["Milwaukee", "密尔沃基"],
    },
    {
        "name": "明尼阿波利斯", "en": "Minneapolis, MN", "region": "中部", "state": "明尼阿波利斯",
        "tokens": ["Minneapolis", "明尼阿波利斯"],
    },
    {
        "name": "堪萨斯城", "en": "Kansas City, MO", "region": "中部", "state": "堪萨斯城",
        "tokens": ["Kansas City", "堪萨斯城"],
    },
    {
        "name": "盐湖城", "en": "Salt Lake City, UT", "region": "西部", "state": "盐湖城",
        "tokens": ["Salt Lake City", "盐湖城"],
    },
    {
        "name": "檀香山", "en": "Honolulu, HI", "region": "西部", "state": "檀香山",
        "tokens": ["Honolulu", "檀香山"],
    },
]

CITY_COORDS = {
    '纽约': (-74.0060, 40.7128),
    '洛杉矶': (-118.2437, 34.0522),
    '布鲁克林': (-73.9442, 40.6782),
    '旧金山-奥克兰-圣何塞': (-122.1500, 37.6000),
    '休斯顿': (-95.3698, 29.7604),
    '芝加哥': (-87.6298, 41.8781),
    '费城': (-75.1652, 39.9526),
    '拉斯维加斯': (-115.1398, 36.1699),
    '奥兰多-代托纳海滩-墨尔本': (-81.3792, 28.5383),
    '西雅图-塔科马': (-122.3321, 47.6062),
    '迈阿密-劳德代尔堡': (-80.1918, 25.7617),
    '波特兰': (-122.6784, 45.5152),
    '圣地亚哥': (-117.1611, 32.7157),
    '布朗克斯': (-73.8648, 40.8448),
    '奥斯汀': (-97.7431, 30.2672),
    '亚特兰大': (-84.3880, 33.7490),
    '圣安东尼奥': (-98.4936, 29.4241),
    '凤凰城': (-112.0740, 33.4484),
    '达拉斯-沃思堡': (-96.7970, 32.7767),
    '杰克逊维尔': (-81.6557, 30.3322),
    '夏洛特': (-80.8431, 35.2271),
    '萨克拉门托-斯托克顿-莫德斯托': (-121.4944, 38.5816),
    '法拉盛': (-73.8331, 40.7675),
    '圣何塞': (-121.8863, 37.3382),
    '坦帕-圣彼得堡（萨拉索塔）': (-82.4572, 27.9506),
    '华盛顿特区（黑格斯敦）': (-77.0369, 38.9072),
    '印第安纳波利斯': (-86.1581, 39.7684),
    '丹佛': (-104.9903, 39.7392),
    '巴尔的摩': (-76.6122, 39.2904),
    '圣路易斯': (-90.1994, 38.6270),
    '弗吉尼亚海滩': (-75.9780, 36.8529),
    '奥克兰': (-122.2711, 37.8044),
    '埃尔帕索': (-106.4850, 31.7619),
    '哥伦布': (-82.9988, 39.9612),
    '路易斯维尔': (-85.7585, 38.2527),
    '俄克拉何马城': (-97.5164, 35.4676),
    '弗雷斯诺-维萨利亚': (-119.7871, 36.7378),
    '图森（塞拉维斯塔）': (-110.9747, 32.2226),
    '波士顿-曼彻斯特': (-71.0589, 42.3601),
    '斯塔滕岛': (-74.1502, 40.5795),
    '阿尔伯克基-圣菲': (-106.6504, 35.0844),
    '曼哈顿': (-73.9712, 40.7831),
    '皇后区': (-73.7949, 40.7282),
    '长岛': (-73.4129, 40.7891),
    '泽西市': (-74.0431, 40.7178),
    '纽瓦克': (-74.1724, 40.7357),
    '爱迪生': (-74.4121, 40.5187),
    '昆西': (-71.0023, 42.2529),
    '罗克维尔': (-77.1528, 39.0840),
    '匹兹堡': (-79.9959, 40.4406),
    '尔湾': (-117.8265, 33.6846),
    '圣盖博': (-118.1080, 34.0961),
    '蒙特利公园': (-118.1270, 34.0625),
    '阿罕布拉': (-118.1270, 34.0953),
    '罗兰岗': (-117.9053, 33.9761),
    '钻石吧': (-117.8103, 34.0286),
    '核桃': (-117.8653, 34.0203),
    '哈仙达岗': (-117.9687, 33.9931),
    '阿凯迪亚': (-118.0353, 34.1397),
    '罗斯密': (-118.0728, 34.0806),
    '加迪纳': (-118.3089, 33.8883),
    '弗里蒙特': (-121.9886, 37.5485),
    '库比蒂诺': (-122.0322, 37.3229),
    '森尼韦尔': (-122.0363, 37.3688),
    '圣塔克拉拉': (-121.9552, 37.3541),
    '圣马刁': (-122.3255, 37.5630),
    '米尔皮塔斯': (-121.8996, 37.4323),
    '都柏林': (-121.9358, 37.7022),
    '伯克利': (-122.2730, 37.8715),
    '圣拉蒙': (-121.9780, 37.7799),
    '橙县': (-117.8311, 33.7175),
    '安纳海姆': (-117.9145, 33.8366),
    '圣塔安娜': (-117.8677, 33.7455),
    '河滨': (-117.3961, 33.9533),
    '安大略': (-117.6509, 34.0633),
    '贝尔维尤': (-122.2007, 47.6101),
    '比弗顿': (-122.8037, 45.4871),
    '普莱诺': (-96.6989, 33.0198),
    '凯蒂': (-95.8244, 29.7858),
    '糖城': (-95.6349, 29.6197),
    '罗利': (-78.6382, 35.7796),
    '纳什维尔': (-86.7816, 36.1627),
    '孟菲斯': (-90.0490, 35.1495),
    '新奥尔良': (-90.0715, 29.9511),
    '底特律': (-83.0458, 42.3314),
    '克利夫兰': (-81.6944, 41.4993),
    '辛辛那提': (-84.5120, 39.1031),
    '密尔沃基': (-87.9065, 43.0389),
    '明尼阿波利斯': (-93.2650, 44.9778),
    '堪萨斯城': (-94.5786, 39.0997),
    '盐湖城': (-111.8910, 40.7608),
    '檀香山': (-157.8583, 21.3069),
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
            pattern = re.compile(r'\b' + re.escape(_t) + r'\b', re.IGNORECASE | re.ASCII)
        _TOKENS.append((_t, _t, _region, pattern))
_TOKENS.sort(key=lambda x: len(x[0]), reverse=True)

_CITY_TOKENS = []  # list of (token, city_info, ascii_pattern_or_None)
for _city in CITY_MARKETS:
    for _t in _city["tokens"]:
        pattern = None
        if _is_ascii_token(_t):
            pattern = re.compile(r'\b' + re.escape(_t) + r'\b', re.IGNORECASE | re.ASCII)
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


def _with_coords(city: dict) -> dict:
    info = dict(city)
    coord = CITY_COORDS.get(city["name"])
    if coord:
        info["lon"], info["lat"] = coord
    return info


def city_info(name: str) -> Optional[dict]:
    """Look up a canonical city/metro entry by its Chinese `name`."""
    if not name:
        return None
    for city in CITY_MARKETS:
        if city["name"] == name:
            return _with_coords(city)
    return None


def city_catalog() -> List[dict]:
    """Return every known city market with coordinates when available."""
    return [_with_coords(city) for city in CITY_MARKETS]


def region_for(state: str) -> Optional[str]:
    """Look up the region for an already-known state token."""
    if not state:
        return None
    for token, _, region, _pat in _TOKENS:
        if token == state:
            return region
    return None
