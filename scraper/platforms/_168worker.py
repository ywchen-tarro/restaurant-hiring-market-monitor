"""Scraper for 168worker.com (the historical baseline platform).

Structure observed (May 2026):
  - Plain HTTP GET returns 403 — needs curl_cffi with Chrome TLS fingerprint
  - Pagination: `/list/<N>_0` (N=1, 2, 3, …) at the restaurant category
  - Each post sits in `div.listdata`
  - Inside: a `<a href="/page/<id>">` for title, a `(<location>)` span,
    a salary cell, then a `YYYY-MM-DD` date

Note: 168worker.com and 500work.com share post IDs and likely the same
CMS. Cross-platform deduplication is a known follow-up (see ROADMAP).
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

BASE = "https://www.168worker.com"
ID_FROM_URL = re.compile(r"^/page/(\d+)")
ABSOLUTE_DATE = re.compile(r"\b\d{4}-\d{1,2}-\d{1,2}\b")
LOCATION_RE = re.compile(r"[（(]([^()）]+)[）)]")


class Scraper(BasePlatformScraper):
    id = "168worker"
    name = "168worker"
    base_url = BASE
    # Anti-bot is fronted by a TLS-fingerprint check — Chrome impersonation
    # via curl_cffi clears it. Plain `requests` gets a 403.
    impersonate = "chrome120"

    def page_url(self, page_num: int) -> str:
        return f"{self.base_url}/list/{page_num}_0"

    def parse_page(self, html: str, page_num: int) -> List[Post]:
        soup = BeautifulSoup(html, "html.parser")
        posts: List[Post] = []
        for row in soup.select("div.listdata"):
            try:
                p = self._parse_row(row)
            except Exception as exc:  # noqa: BLE001
                log.warning("[%s] row parse error: %s", self.id, exc)
                continue
            if p is not None:
                posts.append(p)
        return posts

    def _parse_row(self, row):
        link = row.find("a", href=ID_FROM_URL)
        if not link:
            return None
        m = ID_FROM_URL.search(link["href"])
        if not m:
            return None
        native_id = m.group(1)
        full_url = urljoin(self.base_url, link["href"])
        title = link.get_text(strip=True)
        if not title:
            return None

        row_text = row.get_text(" ", strip=True)

        date_iso = ""
        dm = ABSOLUTE_DATE.search(row_text)
        if dm:
            d = date_parser.parse(dm.group(0))
            if d:
                date_iso = d.isoformat()

        # Location: "（纽约/曼哈顿）" inside row text; take the part after a slash
        # if present, else the whole parenthetical.
        state = None
        lm = LOCATION_RE.search(row_text)
        if lm:
            loc = lm.group(1).strip()
            # If "区域/州", prefer the more specific (right-most) token.
            tokens = [t.strip() for t in re.split(r"[/／]", loc) if t.strip()]
            if tokens:
                state = tokens[-1]

        # Save native_id on Post so subclasses (500work) can rebuild URL
        # without string-splitting.
        post = Post(
            id=post_id(self.id, native_id),
            platform=self.id,
            title=title,
            date=date_iso,
            region=None,
            state=state,
            keywords_matched=[],
            url=full_url,
        )
        post._native_id = native_id  # ad-hoc; only used by _500work subclass
        return post
