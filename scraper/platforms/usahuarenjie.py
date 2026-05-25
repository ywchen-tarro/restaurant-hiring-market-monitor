"""Scraper for usahuarenjie.com (华人街生活网) restaurant category.

Structure observed (May 2026):
  - Pagination: `/category-catid-251-page-N.html`
  - Each post sits inside `div.hover`. Inside that:
      * `span.ltitle > div.inforbox > div.tipsbox` holds h3+description
      * `span.ltime` (sibling of span.ltitle) holds the date text
  - Title: `h3` inside the wrapper
  - Date: `span.ltime` — relative ("7小时前", "昨天", "2天前") or absolute ("2026-05-22")
  - Detail-page URL: `https://www.usahuarenjie.com/city/<region>/information-id-<id>.html`
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

BASE = "https://www.usahuarenjie.com"
LIST_PATH_TPL = "/category-catid-251-page-{n}.html"
LIST_FIRST = "/category-catid-251.html"
ID_FROM_URL = re.compile(r"information-id-(\d+)\.html")
CITY_FROM_URL = re.compile(r"/city/([^/]+)/information-id-")

# URL `/city/<slug>/` segment → Chinese state/city. Slugs are PascalCase or
# Hyphen-Separated. Normalize to lowercase before lookup.
CITY_SLUG_MAP = {
    # East
    "new-york": "纽约", "ny": "纽约", "newyork": "纽约",
    "new-jersey": "新泽西", "nj": "新泽西",
    "boston": "波士顿", "ma": "麻州",
    "connecticut": "康州", "ct": "康州",
    "pennsylvania": "宾州", "philadelphia": "费城",
    "washington-dc": "华盛顿DC",
    "long-island": "长岛",
    # South
    "florida": "佛州", "miami": "迈阿密", "orlando": "奥兰多",
    "georgia": "乔治亚", "atlanta": "亚特兰大",
    "texas": "德州", "dallas": "达拉斯", "houston": "休斯顿", "austin": "德州",
    "north-carolina": "北卡", "charlotte": "夏洛特",
    "maryland": "马里兰",
    # West
    "california": "加州",
    "los-angeles": "洛杉矶", "san-francisco": "旧金山",
    "san-diego": "圣地亚哥", "san-jose": "圣何塞",
    "irvine": "尔湾", "oakland": "奥克兰",
    "seattle": "西雅图", "washington": "华盛顿州",
    "portland": "波特兰", "oregon": "俄勒冈",
    "phoenix": "凤凰城", "arizona": "亚利桑那",
    "colorado": "科罗拉多", "denver": "丹佛",
    "las-vegas": "拉斯维加斯", "nevada": "内华达",
    "utah": "犹他", "salt-lake-city": "盐湖城",
    "hawaii": "夏威夷",
    # Midwest
    "illinois": "伊州", "chicago": "芝加哥",
    "michigan": "密歇根", "detroit": "底特律",
    "ohio": "俄亥俄", "cleveland": "克利夫兰",
    "minneapolis": "明尼阿波利斯", "minnesota": "明尼苏达",
    "indiana": "印第安纳",
    # "Qtcs" = 其他城市 (other cities) — leave unmapped
}


class Scraper(BasePlatformScraper):
    id = "usahuarenjie"
    name = "华人街生活网"

    def page_url(self, page_num: int) -> str:
        if page_num == 1:
            return f"{BASE}{LIST_FIRST}"
        return f"{BASE}{LIST_PATH_TPL.format(n=page_num)}"

    def parse_page(self, html: str, page_num: int) -> List[Post]:
        soup = BeautifulSoup(html, "html.parser")
        posts: List[Post] = []

        for wrapper in soup.select("div.hover"):
            try:
                p = self._parse_row(wrapper)
            except Exception as exc:  # noqa: BLE001
                log.warning("[%s] row parse error: %s", self.id, exc)
                continue
            if p is not None:
                posts.append(p)

        return posts

    def _parse_row(self, wrapper) -> "Post | None":
        h3 = wrapper.find("h3")
        if not h3:
            return None
        title = h3.get_text(strip=True)
        if not title:
            return None

        a = h3.find("a", href=True) or wrapper.find(
            "a", href=lambda h: h and "information-id-" in h
        )
        if not a:
            return None
        href = a["href"]
        m = ID_FROM_URL.search(href)
        if not m:
            return None
        native_id = m.group(1)
        full_url = urljoin(BASE, href)

        ltime = wrapper.find("span", class_="ltime")
        date_iso = ""
        if ltime:
            parsed = date_parser.parse(ltime.get_text(strip=True))
            if parsed:
                date_iso = parsed.isoformat()

        state = None
        city_m = CITY_FROM_URL.search(href)
        if city_m:
            slug = city_m.group(1).lower()
            state = CITY_SLUG_MAP.get(slug)

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


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    scraper = Scraper()
    posts = scraper.run()
    print(f"\nTOTAL KEPT: {len(posts)}")
    for p in posts[:10]:
        print(f"  [{p.date}] [{p.region}/{p.state}] {p.title[:60]}")
