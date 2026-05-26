"""Base class for platform scrapers."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import date, timedelta
from typing import Iterable, List, Optional

import requests

from .. import config, keywords, regions, sanitize

log = logging.getLogger(__name__)


@dataclass
class Post:
    id: str            # globally unique, "<platform>_<native-id>"
    platform: str
    title: str
    date: str          # ISO YYYY-MM-DD
    region: Optional[str]   # 东部/南部/中部/西部 or None
    state: Optional[str]    # matched token (Chinese name preferred)
    keywords_matched: List[str]
    url: str

    def to_dict(self) -> dict:
        return asdict(self)


class BasePlatformScraper(ABC):
    """Override `id`, `page_url(n)`, `parse_page(html) -> List[Post]`."""

    id: str = ""
    name: str = ""

    def __init__(self, session: Optional[requests.Session] = None):
        from ..http_client import make_session
        self.session = session or make_session()

    # ── subclass contract ─────────────────────────────────────
    @abstractmethod
    def page_url(self, page_num: int) -> str: ...

    @abstractmethod
    def parse_page(self, html: str, page_num: int) -> List[Post]: ...

    # ── default driver ────────────────────────────────────────
    # Subclass can override to pass impersonate="chrome120" etc.
    impersonate: Optional[str] = None

    def fetch_page(self, page_num: int) -> Optional[str]:
        from ..http_client import polite_get
        url = self.page_url(page_num)
        log.info("[%s] GET page %d: %s", self.id, page_num, url)
        r = polite_get(url, session=self.session, impersonate=self.impersonate)
        if r is None:
            return None
        return r.text

    # Subclass may override to cap pagination shorter than the default.
    max_pages: Optional[int] = None

    def run(self, days_back: int = None) -> List[Post]:
        """Paginate until posts fall outside the lookback window or max pages.

        Returns a tuple of (kept_posts, diagnostics) — diagnostics is exposed
        via the instance attribute `last_diagnostics` after run() completes.
        """
        days_back = days_back if days_back is not None else config.SCRAPE_DAYS_BACK
        cutoff = date.today() - timedelta(days=days_back)
        # Per-platform override, then config default
        page_cap = (
            self.max_pages
            if self.max_pages is not None
            else config.MAX_PAGES_PER_PLATFORM
        )

        collected: List[Post] = []
        seen_ids = set()
        consecutive_empty = 0
        # Diagnostics surfaced via meta.warnings
        diag = {
            "pages_fetched": 0,
            "rows_parsed": 0,
            "dropped_unparseable_date": 0,
            "dropped_out_of_window": 0,
            "dropped_not_restaurant": 0,
            "dropped_duplicate": 0,
            "fetch_failures": 0,
        }

        for page_num in range(1, page_cap + 1):
            html = self.fetch_page(page_num)
            if html is None:
                diag["fetch_failures"] += 1
                log.warning("[%s] page %d returned nothing; stopping", self.id, page_num)
                break
            diag["pages_fetched"] += 1

            try:
                page_posts = self.parse_page(html, page_num)
            except Exception as exc:  # noqa: BLE001
                log.exception("[%s] parse_page raised on page %d: %s", self.id, page_num, exc)
                page_posts = []

            diag["rows_parsed"] += len(page_posts)

            if not page_posts:
                consecutive_empty += 1
                if consecutive_empty >= 2:
                    log.info("[%s] 2 consecutive empty pages; stopping", self.id)
                    break
                continue
            consecutive_empty = 0

            kept = 0
            stop_paginating = False
            for p in page_posts:
                if p.id in seen_ids:
                    diag["dropped_duplicate"] += 1
                    continue
                seen_ids.add(p.id)

                # Drop posts whose date didn't parse — silently re-dating them
                # to today inflates today's bucket and disables the lookback
                # cutoff. If a platform stops returning dates entirely we'd
                # rather see a 0-post run and investigate.
                try:
                    post_d = date.fromisoformat(p.date)
                except (ValueError, TypeError):
                    diag["dropped_unparseable_date"] += 1
                    continue

                if post_d < cutoff:
                    diag["dropped_out_of_window"] += 1
                    stop_paginating = True
                    continue

                # Sanitize the title (strips PII before publication)
                p.title = sanitize.sanitize_title(p.title)

                # Restaurant filter (must hit a strong venue/role keyword)
                if not keywords.is_restaurant(p.title):
                    diag["dropped_not_restaurant"] += 1
                    continue
                # Still record all matched terms (incl. weak) for display
                p.keywords_matched = keywords.match(p.title)

                # Region classification: prefer title (more specific), use
                # the URL-derived state as a fallback only when the title
                # has no region tokens. (URL slugs lump multi-state cross-
                # listings under a default like "New-York" — bad signal.)
                title_region, title_state = regions.classify(p.title)
                if title_region:
                    p.region = title_region
                    p.state = title_state or p.state
                elif p.state:
                    p.region = regions.region_for(p.state)
                # else: leaves region=None — surfaced as 'unknown'

                collected.append(p)
                kept += 1

            log.info(
                "[%s] page %d: parsed=%d kept=%d",
                self.id, page_num, len(page_posts), kept,
            )

            if stop_paginating:
                log.info(
                    "[%s] hit posts older than %d days; stopping",
                    self.id, days_back,
                )
                break

        log.info("[%s] total kept: %d", self.id, len(collected))
        self.last_diagnostics = diag
        return collected


def post_id(platform: str, native_id: str) -> str:
    return f"{platform}_{native_id}"
