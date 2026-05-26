"""Restaurant-job keyword filter.

A post is classified as restaurant-related when its title matches at least
one **strong** keyword (a clear restaurant venue or restaurant-specific
role) AND does not look like a non-restaurant trade (negative-keyword
filter).

Weak/ambiguous terms (招聘 / 招人 / 请人 / 前台 / 收银 / 师傅 / 打包)
appear in many other industries (medical front desk, retail cashier,
beauty/spa hiring, marble installation, warehouse packing, etc.); they
are still surfaced in `keywords_matched` for display but they alone do
not qualify a post as restaurant.

History:
- Early pass keyed off bare `招聘` → ~3-5% false positives.
- Tightened: split into STRONG (venue + role) vs WEAK (intent).
- Tightened further: removed 师傅 / 師傅 / 打包 from STRONG roles
  because they showed up on 安装/装修/裁缝/拣货 trades.
- Added NEGATIVE_KEYWORDS for trade jobs that contain a strong role
  term but are clearly non-restaurant (rare; venue protection lets
  things like "餐馆水电维修工" still pass).
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
# NOTE: 师傅 / 師傅 / 打包 were REMOVED from this list because they
# showed up on non-restaurant trade jobs (干洗师傅, 安装师傅, 仓库打包).
# They're still surfaced in `keywords_matched` via WEAK_KEYWORDS but
# don't alone qualify a post as restaurant.
ROLE_KEYWORDS: List[str] = [
    "炒锅", "炒鍋", "油锅", "油鍋",
    "厨师", "廚師", "厨房", "廚房",
    "后厨", "後廚",
    "企台", "帮厨", "幫廚",
    "打杂", "打雜", "洗碗",
    "服务员", "服務員",
    "点餐", "點餐", "送餐", "捡码", "撿碼",
    "抓码", "抓碼", "面点", "麵點",
]

# Display-only: surfaced in keywords_matched but not used to gate inclusion.
WEAK_KEYWORDS: List[str] = [
    "招聘", "招人", "请人", "請人", "招工",
    "前台", "前臺", "收银", "收銀",
    # Moved from ROLE — too ambiguous on their own:
    "师傅", "師傅", "打包",
]

# Negative keywords: indicators of a non-restaurant trade. If a post hits
# any of these AND has no STRONG VENUE keyword (餐馆/火锅/etc.) anchoring
# it to restaurants, the post is rejected even if it has a strong role
# keyword. Venue presence wins — "餐馆水电维修工" still counts as a
# restaurant job (restaurant supply chain).
NEGATIVE_KEYWORDS: List[str] = [
    "电工", "電工",
    "装修", "裝修",
    "门窗", "門窗",
    "叉车", "叉車",
    "仓库", "倉庫",
    "干洗", "乾洗",
    "裁缝", "裁縫",
    "改衣",
    "安装", "安裝",
    "技工",
    "维修", "維修",
    "拣货", "揀貨",
]

KEYWORDS: List[str] = VENUE_KEYWORDS + ROLE_KEYWORDS + WEAK_KEYWORDS
_STRONG = set(VENUE_KEYWORDS + ROLE_KEYWORDS)
_VENUE = set(VENUE_KEYWORDS)


def match(title: str) -> List[str]:
    """Return all KEYWORDS that appear in `title` (strong + weak). Order
    preserves the KEYWORDS list ordering. Empty list = nothing matched.

    Note: negative keywords are NOT surfaced here — `match()` is used to
    populate the dashboard's display tags, and we don't want to label a
    restaurant post with "电工" just because it co-occurred.
    """
    if not title:
        return []
    return [k for k in KEYWORDS if k in title]


def is_restaurant(title: str) -> bool:
    """A title qualifies as a restaurant post iff:

    1. At least one STRONG keyword (venue or role) is present, AND
    2. If any NEGATIVE keyword is present, at least one VENUE keyword
       is ALSO present (venue presence anchors the post to restaurants
       — e.g. "餐馆水电维修工" still counts).
    """
    if not title:
        return False
    has_strong = any(k in title for k in _STRONG)
    if not has_strong:
        return False
    has_negative = any(n in title for n in NEGATIVE_KEYWORDS)
    if has_negative:
        has_venue = any(v in title for v in _VENUE)
        if not has_venue:
            return False
    return True


def split_matches(title: str) -> Tuple[List[str], List[str]]:
    """Return (strong_hits, weak_hits) — useful for diagnostics."""
    if not title:
        return [], []
    strong = [k for k in VENUE_KEYWORDS + ROLE_KEYWORDS if k in title]
    weak = [k for k in WEAK_KEYWORDS if k in title]
    return strong, weak


def matched_negatives(title: str) -> List[str]:
    """Return all NEGATIVE keywords that appear in `title` (diagnostic)."""
    if not title:
        return []
    return [k for k in NEGATIVE_KEYWORDS if k in title]
