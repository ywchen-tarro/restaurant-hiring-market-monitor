"""Scraper for meiguogongzuo.com (美国工作网).

Structure observed (May 2026):
  - Plain HTTP GET returns 403 — needs curl_cffi with Chrome TLS fingerprint
  - Pagination: `?page=N` (page 1 is `/`)
  - Each post is a link with href pattern `/<state-slug>/<title-slug>/<id>/`
  - Row text format: `📜 | <title> | <salary> | <location-zh> | <date-MM/DD/YY>`
  - Posts are NOT restaurant-only — site mixes all categories; the
    `is_restaurant` keyword filter weeds out non-restaurant rows.

This site (Similarweb US rank #4,783) has much higher traffic than
168worker (#685,532) so it's likely to become the dominant source of
the signal over time.
"""

from __future__ import annotations

import logging
import re
from typing import List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .. import date_parser
from .base import BasePlatformScraper, Post, post_id

log = logging.getLogger(__name__)

BASE = "https://www.meiguogongzuo.com"
POST_URL_RE = re.compile(r"^/([a-z][a-z\-]*)/([^/]+)/(\d+)/?$")
ABSOLUTE_DATE = re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b")

# State slug (URL segment, e.g. `new-york`) → Chinese state token.
# Falls back to None when unknown — the title-text classifier may still resolve it.
SLUG_TO_STATE = {
    "new-york": "纽约", "new-jersey": "新泽西",
    "massachusetts": "麻州", "connecticut": "康州",
    "pennsylvania": "宾州", "virginia": "维吉尼亚",
    "vermont": "佛蒙特", "delaware": "特拉华",
    "new-hampshire": "新罕布什尔", "rhode-island": "罗得岛",
    "maine": "缅因", "maryland": "马里兰",
    "washington-dc": "华盛顿DC",
    "florida": "佛州", "georgia": "乔治亚", "texas": "德州",
    "north-carolina": "北卡", "south-carolina": "南卡",
    "tennessee": "田纳西", "louisiana": "路易斯安娜",
    "mississippi": "密西西比", "alabama": "阿拉巴马",
    "arkansas": "阿肯色", "oklahoma": "俄克拉荷马",
    "kentucky": "肯塔基", "west-virginia": "西维吉尼亚",
    "california": "加州", "washington": "华盛顿州",
    "oregon": "俄勒冈", "nevada": "内华达", "arizona": "亚利桑那",
    "colorado": "科罗拉多", "hawaii": "夏威夷", "utah": "犹他",
    "new-mexico": "新墨西哥", "alaska": "阿拉斯加",
    "idaho": "爱达荷", "montana": "蒙大拿", "wyoming": "怀俄明",
    "illinois": "伊州", "michigan": "密歇根", "ohio": "俄亥俄",
    "indiana": "印第安纳", "wisconsin": "威斯康星",
    "minnesota": "明尼苏达", "missouri": "密苏里",
    "iowa": "爱荷华", "kansas": "堪萨斯",
    "nebraska": "内布拉斯加",
    "north-dakota": "北达科他", "south-dakota": "南达科他",
}


class Scraper(BasePlatformScraper):
    id = "meiguogongzuo"
    name = "美国工作网"
    base_url = BASE
    impersonate = "chrome120"

    def page_url(self, page_num: int) -> str:
        if page_num == 1:
            return f"{self.base_url}/"
        return f"{self.base_url}/?page={page_num}"

    def parse_page(self, html: str, page_num: int) -> List[Post]:
        soup = BeautifulSoup(html, "html.parser")
        posts: List[Post] = []
        seen_ids = set()

        for a in soup.find_all("a", href=POST_URL_RE):
            try:
                p = self._parse_link(a, seen_ids)
            except Exception as exc:  # noqa: BLE001
                log.warning("[%s] link parse error: %s", self.id, exc)
                continue
            if p is not None:
                posts.append(p)
        return posts

    def _parse_link(self, a, seen_ids):
        m = POST_URL_RE.match(a["href"])
        if not m:
            return None
        slug, _title_slug, native_id = m.group(1), m.group(2), m.group(3)
        if native_id in seen_ids:
            return None

        title = a.get_text(strip=True)
        if not title:
            return None
        seen_ids.add(native_id)

        full_url = urljoin(self.base_url, a["href"])

        # Date: walk up to the row, find MM/DD/YY in the row's text
        date_iso = ""
        cur = a
        for _ in range(4):
            cur = cur.parent
            if cur is None:
                break
            txt = cur.get_text(" ", strip=True)
            dm = ABSOLUTE_DATE.search(txt)
            if dm:
                d = date_parser.parse(dm.group(0))
                if d:
                    date_iso = d.isoformat()
                break

        # State: derive from URL slug; the base-class classifier may
        # override using the title if more specific.
        state = SLUG_TO_STATE.get(slug)

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
