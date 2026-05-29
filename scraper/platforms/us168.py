"""Scraper for us168.com (华人168).

The `/job` page is server-rendered by Nuxt and includes a devalue-style
`__NUXT_DATA__` payload with recruitment records. We parse that payload
instead of relying on the private POST API.

Important date note: us168 heavily refreshes / tops older jobs. The listing
order follows its business refresh time, not the original publish time, so we
use `bizUpdateTime` with sensible fallbacks. That makes the signal represent
active jobs currently resurfaced on the board.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date
from functools import lru_cache
from typing import Any, List, Optional
from urllib.parse import urlencode

from .. import regions
from .base import BasePlatformScraper, Post, post_id

log = logging.getLogger(__name__)

BASE = "https://us168.com"
NUXT_DATA_RE = re.compile(
    r'<script type="application/json" data-nuxt-data="nuxt-app"[^>]*>'
    r"(.*?)"
    r"</script>",
    re.S,
)
DEVALUE_WRAPPERS = {"ShallowReactive", "Reactive", "Ref"}


class Scraper(BasePlatformScraper):
    id = "us168"
    name = "华人168"
    base_url = BASE
    # US168 has very high volume and many refreshed listings. As of
    # 2026-05-29, the 7-day cutoff was around page 360; keep headroom and
    # let BasePlatformScraper stop once it sees older-than-window posts.
    max_pages = 450

    def page_url(self, page_num: int) -> str:
        return f"{self.base_url}/job?{urlencode({'page': page_num})}"

    def parse_page(self, html: str, page_num: int) -> List[Post]:
        records = _extract_records(html)
        posts: List[Post] = []
        seen_ids = set()

        for rec in records:
            native_id = str(rec.get("id") or "").strip()
            title = str(rec.get("title") or "").strip()
            if not native_id or not title or native_id in seen_ids:
                continue

            seen_ids.add(native_id)
            date_iso = _date_from_record(rec)
            area = str(rec.get("areaName") or "").strip() or None
            region, state = regions.classify(area or "")

            posts.append(
                Post(
                    id=post_id(self.id, native_id),
                    platform=self.id,
                    title=title,
                    date=date_iso,
                    region=region,
                    state=state or area,
                    keywords_matched=[],
                    url=f"{self.base_url}/job#{native_id}",
                )
            )

        return posts


def _extract_records(html: str) -> List[dict]:
    if not html:
        return []

    m = NUXT_DATA_RE.search(html)
    if not m:
        return []

    try:
        payload = json.loads(m.group(1))
        root = _revive_devalue(payload)
        records = root["data"]["recruitment"]["data"]["records"]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        log.warning("[us168] could not parse Nuxt recruitment payload: %s", exc)
        return []

    return [r for r in records if isinstance(r, dict)]


def _revive_devalue(values: list[Any]) -> Any:
    """Revive the subset of Nuxt/devalue encoding used in `__NUXT_DATA__`."""

    @lru_cache(maxsize=None)
    def revive_idx(idx: int) -> Any:
        value = values[idx]

        if isinstance(value, list):
            if value and isinstance(value[0], str):
                if value[0] == "BigInt":
                    return str(value[1])
                if value[0] in DEVALUE_WRAPPERS:
                    return revive_idx(value[1])
            return [
                revive_idx(item)
                if isinstance(item, int) and 0 <= item < len(values)
                else item
                for item in value
            ]

        if isinstance(value, dict):
            return {
                key: (
                    revive_idx(item)
                    if isinstance(item, int) and 0 <= item < len(values)
                    else item
                )
                for key, item in value.items()
            }

        return value

    if not values:
        return None
    return revive_idx(0)


def _date_from_record(rec: dict) -> str:
    for field in ("bizUpdateTime", "refreshUpdateTime", "updateTime", "publishTime"):
        parsed = _date_from_ms(rec.get(field))
        if parsed:
            return parsed
    return ""


def _date_from_ms(value: Any) -> Optional[str]:
    try:
        millis = int(value)
    except (TypeError, ValueError):
        return None
    if millis <= 0:
        return None
    return date.fromtimestamp(millis / 1000).isoformat()
