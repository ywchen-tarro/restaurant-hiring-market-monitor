"""Scraper for 500work.com.

500work.com runs the same CMS as 168worker.com — same URL patterns, often
the same post IDs. The two are deduped against each other by
`scraper.output.MIRROR_GROUPS`.

This scraper subclasses 168worker's and overrides only the host URL.
"""

from __future__ import annotations

from . import _168worker as _i168
from .base import Post, post_id

BASE = "https://www.500work.com"


class Scraper(_i168.Scraper):
    id = "500work"
    name = "500work"
    base_url = BASE

    def _parse_row(self, row):
        p = super()._parse_row(row)
        if p is None:
            return None
        # Re-key with this platform's id so cross-platform Post.id stays
        # distinct. base_url override already produced the right host in
        # p.url via urljoin in the parent.
        native_id = getattr(p, "_native_id", "")
        return Post(
            id=post_id(self.id, native_id) if native_id else post_id(self.id, "unknown"),
            platform=self.id,
            title=p.title,
            date=p.date,
            region=p.region,
            state=p.state,
            keywords_matched=p.keywords_matched,
            url=p.url,
        )
