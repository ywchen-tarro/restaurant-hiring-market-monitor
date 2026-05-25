"""Scraper for niuyuegongzuo.com.

Structure observed (May 2026):
  - Pagination: `/?page=N`
  - Each post sits in `div.jobs-grid1.dash-tall`
  - Title link: `a[href^="/<location>/<category>/<slug>/<id>"]` (id is digits)
  - Date column: `div.jobs-item.small_screen` text like "05/25/26"
  - Row text columns: emoji | title | salary | location | views | author | date
"""

from __future__ import annotations

import logging
import re
from typing import List
from urllib.parse import urljoin, unquote

from bs4 import BeautifulSoup

from .. import date_parser
from .base import BasePlatformScraper, Post, post_id

log = logging.getLogger(__name__)

BASE = "https://niuyuegongzuo.com"
ID_FROM_URL = re.compile(r"/(\d+)/?$")
DATE_TEXT = re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b")


# URL-path location slug → Chinese state name (used for region classification)
LOCATION_SLUG_MAP = {
    "flushing": "法拉盛",
    "queens": "皇后区",
    "manhattan": "曼哈顿",
    "brooklyn": "布鲁克林",
    "bronx": "纽约",
    "longisland": "长岛",
    "upstate": "上州",
    "newjersey": "新泽西",
    "connecticut": "康州",
    "pennsylvania": "宾州",
    "boston": "波士顿",
    "philadelphia": "费城",
    "washingtondc": "华盛顿DC",
    "florida": "佛州",
    "california": "加州",
    "texas": "德州",
    "chicago": "芝加哥",
    "atlanta": "亚特兰大",
}


class Scraper(BasePlatformScraper):
    id = "niuyuegongzuo"
    name = "纽约工作网"

    def page_url(self, page_num: int) -> str:
        if page_num == 1:
            return f"{BASE}/"
        return f"{BASE}/?page={page_num}"

    def parse_page(self, html: str, page_num: int) -> List[Post]:
        soup = BeautifulSoup(html, "html.parser")
        posts: List[Post] = []

        for row in soup.select("div.jobs-grid1.dash-tall"):
            link = row.find(
                "a",
                href=lambda h: bool(h and ID_FROM_URL.search(h)),
            )
            if not link:
                continue
            href = link["href"]
            m = ID_FROM_URL.search(href)
            if not m:
                continue
            native_id = m.group(1)
            full_url = urljoin(BASE, href)
            title = link.get_text(strip=True).lstrip("📜").strip()
            if not title:
                continue

            # Date: text matching MM/DD/YY anywhere in the row
            date_iso = self._extract_date(row)

            # Location from URL slug
            state = None
            try:
                slug = unquote(href).split("/")[1].lower()
                state = LOCATION_SLUG_MAP.get(slug)
            except IndexError:
                pass

            posts.append(Post(
                id=post_id(self.id, native_id),
                platform=self.id,
                title=title,
                date=date_iso or "",
                region=None,  # base class will classify
                state=state,
                keywords_matched=[],
                url=full_url,
            ))

        return posts

    def _extract_date(self, row) -> str:
        for el in row.select("div.jobs-item.small_screen"):
            txt = el.get_text(strip=True)
            m = DATE_TEXT.search(txt)
            if m:
                d = date_parser.parse(m.group(0))
                if d:
                    return d.isoformat()
        # fallback: search entire row text
        m = DATE_TEXT.search(row.get_text(" ", strip=True))
        if m:
            d = date_parser.parse(m.group(0))
            if d:
                return d.isoformat()
        return ""


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    scraper = Scraper()
    posts = scraper.run()
    print(f"\nTOTAL KEPT: {len(posts)}")
    for p in posts[:10]:
        print(f"  [{p.date}] [{p.region}/{p.state}] {p.title[:60]}")
