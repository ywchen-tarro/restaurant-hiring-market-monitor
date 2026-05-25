"""Base class for platform scrapers."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import date, timedelta
from typing import Iterable, List, Optional

import requests

from .. import config, keywords, regions

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
    def fetch_page(self, page_num: int) -> Optional[str]:
        from ..http_client import polite_get
        url = self.page_url(page_num)
        log.info("[%s] GET page %d: %s", self.id, page_num, url)
        r = polite_get(url, session=self.session)
        if r is None:
            return None
        return r.text

    def run(self, days_back: int = None) -> List[Post]:
        """Paginate until posts fall outside the lookback window or max pages."""
        days_back = days_back if days_back is not None else config.SCRAPE_DAYS_BACK
        cutoff = date.today() - timedelta(days=days_back)

        collected: List[Post] = []
        seen_ids = set()
        consecutive_empty = 0

        for page_num in range(1, config.MAX_PAGES_PER_PLATFORM + 1):
            html = self.fetch_page(page_num)
            if html is None:
                log.warning("[%s] page %d returned nothing; stopping", self.id, page_num)
                break

            page_posts = self.parse_page(html, page_num)
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
                    continue
                seen_ids.add(p.id)

                try:
                    post_d = date.fromisoformat(p.date)
                except (ValueError, TypeError):
                    # Unparsed date — assume current, don't let it stop pagination
                    post_d = date.today()

                if post_d < cutoff:
                    stop_paginating = True
                    continue

                # restaurant keyword filter
                hits = keywords.match(p.title)
                if not hits:
                    continue
                p.keywords_matched = hits

                # region classification
                if not p.region:
                    if p.state:
                        p.region = regions.region_for(p.state)
                    if not p.region:
                        region, state = regions.classify(p.title)
                        p.region = region
                        if not p.state:
                            p.state = state

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
        return collected


def post_id(platform: str, native_id: str) -> str:
    return f"{platform}_{native_id}"
