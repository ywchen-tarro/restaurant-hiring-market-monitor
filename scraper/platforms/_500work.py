"""Scraper for 500work.com.

500work.com runs the same CMS as 168worker.com (same URL patterns,
same post IDs in many cases — they share data). The parsing logic is
identical; only the base URL differs.
"""

from __future__ import annotations

from . import _168worker as _i168
from .base import Post, post_id

BASE = "https://www.500work.com"


class Scraper(_i168.Scraper):
    id = "500work"
    name = "500work"

    def page_url(self, page_num: int) -> str:
        return f"{BASE}/list/{page_num}_0"

    def _parse_row(self, row):
        p = super()._parse_row(row)
        if p is None:
            return None
        # Re-key with this platform's id and remount the URL on this host.
        # (We rebuild the Post so cross-platform IDs stay distinct.)
        # The parent class hard-codes BASE = 168worker; replace the host.
        native_id = p.url.rsplit("/", 1)[-1]
        return Post(
            id=post_id(self.id, native_id),
            platform=self.id,
            title=p.title,
            date=p.date,
            region=p.region,
            state=p.state,
            keywords_matched=p.keywords_matched,
            url=f"{BASE}/page/{native_id}",
        )
