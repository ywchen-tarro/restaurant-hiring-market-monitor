"""Scraper for uscanyin.com (北美餐饮通).

Structure observed (May 2026):
  - Pagination: `/en/community/jobs/paged/<N>` (page 1 is `/en/jobs`)
  - Each post link looks like `/community/jobs/<id>-<url-encoded-title-slug>`
  - On the list page the same post appears multiple times (image link,
    title link, "read more") — dedupe by id
  - Date sits in a sibling text node: "发布者: 匿名用户, 7小时前" or similar
  - Listing pages are huge (4,500+ pages site-wide) but date-sorted
    descending, so the standard 7-day cutoff stops pagination early.
"""

from __future__ import annotations

import logging
import re
from typing import List
from urllib.parse import unquote

from bs4 import BeautifulSoup

from .. import date_parser
from .base import BasePlatformScraper, Post, post_id

log = logging.getLogger(__name__)

BASE = "https://uscanyin.com"
LIST_FIRST = "/en/jobs"
LIST_TPL = "/en/community/jobs/paged/{n}"
ID_AND_SLUG = re.compile(r"/community/jobs/(\d+)-([^/?#]+)")
PREFIX_LINK = re.compile(r"view=prefix")

# uscanyin tags each post with an English state/region name on a sibling
# `<a href="...view=prefix&prefixi...">`. Map to a Chinese state token so the
# region classifier picks it up.
PREFIX_LABEL_MAP = {
    "new york": "纽约", "new jersey": "新泽西",
    "boston": "波士顿", "massachusetts": "麻州", "connecticut": "康州",
    "pennsylvania": "宾州", "virginia": "维吉尼亚",
    "florida": "佛州", "georgia": "乔治亚", "texas": "德州",
    "maryland": "马里兰", "north carolina": "北卡", "south carolina": "南卡",
    "tennessee": "田纳西", "louisiana": "路易斯安娜", "mississippi": "密西西比",
    "california": "加州", "washington": "华盛顿州", "oregon": "俄勒冈",
    "nevada": "内华达", "arizona": "亚利桑那", "colorado": "科罗拉多",
    "hawaii": "夏威夷", "utah": "犹他", "new mexico": "新墨西哥",
    "illinois": "伊州", "michigan": "密歇根", "ohio": "俄亥俄",
    "indiana": "印第安纳", "wisconsin": "威斯康星", "minnesota": "明尼苏达",
    "missouri": "密苏里",
    "new hampshire": "新罕布什尔", "rhode island": "罗得岛", "vermont": "佛蒙特",
    "maine": "缅因", "delaware": "特拉华", "west virginia": "西维吉尼亚",
    "kentucky": "肯塔基", "alabama": "阿拉巴马",
}
REL_DATE = re.compile(
    r"\d+\s*(?:分钟|分鐘|小时|小時|天|日|周|週|月|年)前"
    r"|刚刚|剛剛|今天|昨天|前天"
    r"|\d+\s+(?:minute|hour|day|week|month|year)s?\s+ago"
    r"|just\s+now|yesterday",
    re.IGNORECASE,
)


class Scraper(BasePlatformScraper):
    id = "uscanyin"
    name = "北美餐饮通"
    # Deeper pages render server-side at ~17s each; bound pagination tight.
    max_pages = 8

    def page_url(self, page_num: int) -> str:
        if page_num == 1:
            return f"{BASE}{LIST_FIRST}"
        return f"{BASE}{LIST_TPL.format(n=page_num)}"

    def parse_page(self, html: str, page_num: int) -> List[Post]:
        soup = BeautifulSoup(html, "html.parser")
        posts: List[Post] = []
        seen_native_ids = set()

        for a in soup.find_all("a", href=True):
            try:
                p = self._parse_link(a, seen_native_ids)
            except Exception as exc:  # noqa: BLE001
                log.warning("[%s] link parse error: %s", self.id, exc)
                continue
            if p is not None:
                posts.append(p)
        return posts

    def _parse_link(self, a, seen):
        m = ID_AND_SLUG.search(a["href"])
        if not m:
            return None
        native_id, slug = m.group(1), m.group(2)
        if native_id in seen:
            return None

        # Prefer the link variant whose text contains an actual title (not
        # an empty image-only link). On uscanyin the title link is one of
        # the duplicates per post.
        title = a.get_text(strip=True)
        if not title:
            # Fall back to URL slug if needed (URL-decoded)
            try:
                title = unquote(slug).replace("-", " ").strip()
            except Exception:
                return None
        if not title or len(title) < 2:
            return None

        seen.add(native_id)
        full_url = a["href"] if a["href"].startswith("http") else f"{BASE}{a['href']}"

        # Date: look at the surrounding text for relative-date markers
        date_iso = self._find_nearby_date(a)

        # State: walk up to the row and look for a "view=prefix" link whose
        # text is the English state name (e.g. "New York", "Texas").
        state = self._find_nearby_state(a)

        return Post(
            id=post_id(self.id, native_id),
            platform=self.id,
            title=title,
            date=date_iso,
            region=None,
            state=state,
            keywords_matched=[],
            url=full_url,
        )

    def _find_nearby_state(self, a):
        cur = a
        for _ in range(5):
            cur = cur.parent
            if cur is None:
                break
            for link in cur.find_all("a", href=PREFIX_LINK):
                label = link.get_text(strip=True).lower()
                if label in PREFIX_LABEL_MAP:
                    return PREFIX_LABEL_MAP[label]
        return None

    def _find_nearby_date(self, a) -> str:
        # Walk up at most 4 ancestors and look for "<N>小时前" / "昨天" / etc.
        cur = a
        for _ in range(5):
            cur = cur.parent
            if cur is None:
                break
            txt = cur.get_text(" ", strip=True)
            m = REL_DATE.search(txt)
            if m:
                d = date_parser.parse(m.group(0))
                if d:
                    return d.isoformat()
        return ""
