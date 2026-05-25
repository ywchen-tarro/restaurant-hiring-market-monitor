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


def parse(text: str, today: Optional[date] = None) -> Optional[date]:
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
    today = today or date.today()

    if s in ("刚刚", "剛剛", "今天"):
        return today
    if s == "昨天":
        return today - timedelta(days=1)
    if s == "前天":
        return today - timedelta(days=2)

    m = _REL_RE.search(s)
    if m:
        n = int(m.group("n"))
        unit = m.group("unit")
        if unit in ("分钟", "分鐘", "小时", "小時"):
            return today
        if unit in ("天", "日"):
            return today - timedelta(days=n)
        if unit in ("周", "週"):
            return today - timedelta(days=7 * n)
        if unit == "月":
            return today - timedelta(days=30 * n)
        if unit == "年":
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
