"""Restaurant-job keyword filter. Both simplified and traditional forms."""

from __future__ import annotations

from typing import List

KEYWORDS: List[str] = [
    # 场所 — venue
    "餐馆", "餐館", "餐厅", "餐廳", "餐饮", "餐飲",
    "火锅", "火鍋", "奶茶", "日餐", "寿司", "壽司",
    # 招聘意图 — hiring intent
    "请人", "請人", "招人", "招聘",
    # FOH
    "前台", "前臺", "服务员", "服務員", "企台", "收银", "收銀",
    # BOH
    "厨房", "廚房", "炒锅", "炒鍋", "油锅", "油鍋",
    "厨师", "廚師", "师傅", "師傅", "后厨", "後廚",
    # 操作类 — operations
    "洗碗", "打杂", "打雜", "打包", "外卖", "外賣",
    "帮厨", "幫廚", "点餐", "點餐",
]


def match(title: str) -> List[str]:
    """Return all KEYWORDS that appear in `title`. Empty list = not a match."""
    if not title:
        return []
    return [k for k in KEYWORDS if k in title]


def is_restaurant(title: str) -> bool:
    return bool(match(title))
