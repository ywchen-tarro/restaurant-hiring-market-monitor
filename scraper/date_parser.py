"""Parse the various date formats job-board posts use.

Returns `datetime.date` (in US/Eastern day — we don't track timezone strictly;
all that matters for the daily-bucket aggregation is the calendar day).
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Optional


_REL_RE = re.compile(
    r"(?P<n>\d+)\s*(?P<unit>分钟|分鐘|小时|小時|天|日|周|週|月|年)前"
)

# English equivalents (uscanyin renders dates in English):
#   "1 hour ago", "5 hours ago", "2 days ago", "1 minute ago", "3 weeks ago"
_REL_EN_RE = re.compile(
    r"(?P<n>\d+)\s+(?P<unit>minute|hour|day|week|month|year)s?\s+ago",
    re.IGNORECASE,
)


def parse(text: str, today: Optional[date] = None, now: Optional[datetime] = None) -> Optional[date]:
    """Parse a date string in any of the formats job-boards use.

    Supports:
      - "刚刚" / "剛剛"             → today
      - "今天"                       → today
      - "昨天"                       → today - 1
      - "前天"                       → today - 2
      - "N分钟前" / "N小时前"        → today  (sub-day)
      - "N天前" / "N日前"            → today - N
      - "N周前" / "N月前" / "N年前"  → approximate
      - "YYYY-MM-DD"                 → that date
      - "YYYY/MM/DD"                 → that date
      - "MM/DD/YY"                   → that date  (2000+YY)
      - "MM/DD/YYYY"                 → that date

    Returns None if the input doesn't match any of the above.
    """
    if not text:
        return None
    s = text.strip()
    if now is None and today is not None:
        now = datetime.combine(today, datetime.max.time())
    now = now or datetime.now()
    today = today or now.date()

    s_lower = s.lower()
    if s in ("刚刚", "剛剛", "今天") or s_lower in ("just now", "now", "today"):
        return today
    if s == "昨天" or s_lower == "yesterday":
        return today - timedelta(days=1)
    if s == "前天":
        return today - timedelta(days=2)

    m = _REL_RE.search(s)
    if m:
        n = int(m.group("n"))
        unit = m.group("unit")
        if unit in ("分钟", "分鐘"):
            return (now - timedelta(minutes=n)).date()
        if unit in ("小时", "小時"):
            return (now - timedelta(hours=n)).date()
        if unit in ("天", "日"):
            return today - timedelta(days=n)
        if unit in ("周", "週"):
            return today - timedelta(days=7 * n)
        if unit == "月":
            return today - timedelta(days=30 * n)
        if unit == "年":
            return today - timedelta(days=365 * n)

    m = _REL_EN_RE.search(s)
    if m:
        n = int(m.group("n"))
        unit = m.group("unit").lower()
        if unit == "minute":
            return (now - timedelta(minutes=n)).date()
        if unit == "hour":
            return (now - timedelta(hours=n)).date()
        if unit == "day":
            return today - timedelta(days=n)
        if unit == "week":
            return today - timedelta(days=7 * n)
        if unit == "month":
            return today - timedelta(days=30 * n)
        if unit == "year":
            return today - timedelta(days=365 * n)

    # ISO-ish: YYYY-MM-DD or YYYY/MM/DD
    m = re.fullmatch(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None

    # MM/DD/YY or MM/DD/YYYY
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", s)
    if m:
        mm, dd, yy = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if yy < 100:
            yy += 2000
        try:
            return date(yy, mm, dd)
        except ValueError:
            return None

    return None
