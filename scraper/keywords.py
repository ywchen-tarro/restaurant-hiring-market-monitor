"""Restaurant-job keyword filter.

A post is classified as restaurant-related when its title matches at least one
**strong** keyword (a clear restaurant venue or restaurant-specific role).
Weak/ambiguous terms (招聘 / 招人 / 请人 / 前台 / 收银) appear in many
non-restaurant industries (medical front desk, retail cashier, beauty/spa
hiring etc.); they are still surfaced in `keywords_matched` for display, but
they alone do not qualify a post as restaurant.

Background: an early pass keyed off bare `招聘` produced ~3-5% false
positives (medical-supply, swim school, etc.).
"""

from __future__ import annotations

from typing import List, Tuple


# Strong indicator: clearly a restaurant venue or food service.
VENUE_KEYWORDS: List[str] = [
    "餐馆", "餐館", "餐厅", "餐廳", "餐饮", "餐飲", "餐",
    "火锅", "火鍋", "奶茶", "日餐", "中餐", "日料",
    "寿司", "壽司", "烧烤", "燒烤",
    "外卖", "外賣", "面馆", "麵館", "茶餐厅", "茶餐廳",
    "牛排", "甜品", "饭店", "飯店",
]

# Strong indicator: a role overwhelmingly used in restaurant context.
ROLE_KEYWORDS: List[str] = [
    "炒锅", "炒鍋", "油锅", "油鍋",
    "厨师", "廚師", "厨房", "廚房",
    "师傅", "師傅", "后厨", "後廚",
    "企台", "帮厨", "幫廚",
    "打杂", "打雜", "洗碗", "打包",
    "服务员", "服務員",  # in Chinese-US context, dominated by restaurants
    "点餐", "點餐", "送餐", "捡码", "撿碼",
    "抓码", "抓碼", "面点", "麵點",
]

# Display-only: surfaced in keywords_matched but not used to gate inclusion.
WEAK_KEYWORDS: List[str] = [
    "招聘", "招人", "请人", "請人", "招工",
    "前台", "前臺", "收银", "收銀",
]

KEYWORDS: List[str] = VENUE_KEYWORDS + ROLE_KEYWORDS + WEAK_KEYWORDS
_STRONG = set(VENUE_KEYWORDS + ROLE_KEYWORDS)


def match(title: str) -> List[str]:
    """Return all KEYWORDS that appear in `title` (strong + weak). Order
    preserves the KEYWORDS list ordering. Empty list = nothing matched."""
    if not title:
        return []
    return [k for k in KEYWORDS if k in title]


def is_restaurant(title: str) -> bool:
    """A title is a restaurant post iff at least one strong keyword matches."""
    if not title:
        return False
    return any(k in title for k in _STRONG)


def split_matches(title: str) -> Tuple[List[str], List[str]]:
    """Return (strong_hits, weak_hits) — useful for diagnostics."""
    if not title:
        return [], []
    strong = [k for k in VENUE_KEYWORDS + ROLE_KEYWORDS if k in title]
    weak = [k for k in WEAK_KEYWORDS if k in title]
    return strong, weak
