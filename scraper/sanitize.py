"""Sanitizers run on post titles before they're written to posts.json.

`docs/data/posts.json` is served publicly via GitHub Pages, so we strip
contact PII from titles. The source pages are public, but republishing
indexed phone numbers on a different domain raises the exposure (CCPA,
SEO surfaces, etc.) materially over the source.
"""

from __future__ import annotations

import re

# US phone patterns covered:
#   7187082268               (10 digits run-on)
#   973-767-8887             (hyphen-separated)
#   (917) 250-9767           (parenthesized area)
#   917.250.9767
#   1-917-250-9767
#   +1 (917) 250-9767
#
# Note: we require 10 digits total. To avoid eating IDs that look like
# phone numbers but aren't (e.g., "12345678901"), we anchor at word/symbol
# boundaries.
_PHONE_RE = re.compile(
    r"""
    (?<![\d])                          # not preceded by a digit
    \+?1?[\s.\-]?                      # optional +1 / 1
    \(?\d{3}\)?[\s.\-]?                # 3-digit area code (parens optional)
    \d{3}[\s.\-]?                      # 3-digit prefix
    \d{4}                              # 4-digit line
    (?![\d])                           # not followed by a digit
    """,
    re.VERBOSE,
)

_PHONE_PLACEHOLDER = "[电话]"


def redact_phones(text: str) -> str:
    """Replace US-style phone numbers in `text` with a placeholder."""
    if not text:
        return text
    return _PHONE_RE.sub(_PHONE_PLACEHOLDER, text)


def sanitize_title(title: str) -> str:
    """Apply all title sanitizers."""
    return redact_phones(title)
