"""Polite HTTP client.

Two transports are supported:

- **requests** (default): plain Python stdlib-ish HTTP. Works for sites
  without anti-bot protection.
- **curl_cffi**: libcurl-impersonate, sends a TLS handshake (JA3) and
  HTTP/2 frame ordering that exactly matches a real Chrome browser.
  Required for sites fronted by Cloudflare-class anti-bot.

A platform opts into curl_cffi by setting `"impersonate": "chrome120"`
(or another browser tag) in its `PLATFORMS` entry. `polite_get` reads
that and routes accordingly. The polite-retry / UA-rotation / delay
behavior is the same for both transports.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Any, Optional

import requests

from . import config

log = logging.getLogger(__name__)

# Lazy import so the dependency stays optional. Platforms that don't use
# curl_cffi never trip this import.
_CURL_CFFI = None


def _curl_cffi():
    global _CURL_CFFI
    if _CURL_CFFI is None:
        try:
            from curl_cffi import requests as cf
            _CURL_CFFI = cf
        except ImportError as exc:
            raise RuntimeError(
                "curl_cffi is required for impersonating platforms. "
                "Install with: pip install -r scraper/requirements.txt"
            ) from exc
    return _CURL_CFFI


def _headers() -> dict:
    return {
        "User-Agent": random.choice(config.USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Upgrade-Insecure-Requests": "1",
    }


def polite_get(
    url: str,
    session: Optional[Any] = None,
    retries: Optional[int] = None,
    impersonate: Optional[str] = None,
):
    """Sleep, then GET; retry on transient failures.

    `impersonate` is a curl_cffi browser tag (e.g. "chrome120", "safari17_0").
    When set, curl_cffi is used instead of `requests` to defeat TLS-
    fingerprint-based anti-bot.

    Returns the response on 2xx, otherwise None after exhausting retries.
    """
    retries = retries if retries is not None else config.MAX_RETRIES

    if impersonate:
        cf = _curl_cffi()
        get = lambda u: cf.get(  # noqa: E731
            u,
            headers=_headers(),
            timeout=config.REQUEST_TIMEOUT,
            impersonate=impersonate,
        )
    else:
        session = session or requests.Session()
        get = lambda u: session.get(  # noqa: E731
            u,
            headers=_headers(),
            timeout=config.REQUEST_TIMEOUT,
        )

    for attempt in range(retries):
        time.sleep(random.uniform(config.DELAY_MIN, config.DELAY_MAX))
        try:
            r = get(url)
            if r.status_code == 200:
                return r
            log.warning(
                "GET %s returned %s (attempt %d/%d, impersonate=%s)",
                url, r.status_code, attempt + 1, retries, impersonate or "off",
            )
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "GET %s raised %s (attempt %d/%d)",
                url, exc.__class__.__name__, attempt + 1, retries,
            )

        time.sleep(random.uniform(5, 15))

    log.error("Giving up on %s after %d attempts", url, retries)
    return None


def make_session() -> requests.Session:
    return requests.Session()
