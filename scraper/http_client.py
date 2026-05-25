"""Polite HTTP client: rotating User-Agents, randomized delays, retries."""

from __future__ import annotations

import logging
import random
import time
from typing import Optional

import requests

from . import config

log = logging.getLogger(__name__)


def _headers() -> dict:
    return {
        "User-Agent": random.choice(config.USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }


def polite_get(
    url: str,
    session: Optional[requests.Session] = None,
    retries: int = None,
) -> Optional[requests.Response]:
    """Sleep, then GET; retry on transient failures.

    Returns the Response on 2xx, otherwise None after exhausting retries.
    """
    session = session or requests.Session()
    retries = retries if retries is not None else config.MAX_RETRIES

    for attempt in range(retries):
        delay = random.uniform(config.DELAY_MIN, config.DELAY_MAX)
        time.sleep(delay)
        try:
            r = session.get(
                url,
                headers=_headers(),
                timeout=config.REQUEST_TIMEOUT,
            )
            if r.status_code == 200:
                return r
            log.warning(
                "GET %s returned %s (attempt %d/%d)",
                url, r.status_code, attempt + 1, retries,
            )
        except requests.RequestException as exc:
            log.warning(
                "GET %s raised %s (attempt %d/%d)",
                url, exc.__class__.__name__, attempt + 1, retries,
            )

        # backoff before next try
        time.sleep(random.uniform(5, 15))

    log.error("Giving up on %s after %d attempts", url, retries)
    return None


def make_session() -> requests.Session:
    return requests.Session()
