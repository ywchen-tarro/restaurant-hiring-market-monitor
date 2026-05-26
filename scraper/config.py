"""Single source of truth for all scraper tunables."""

from pathlib import Path
from typing import Optional

# ── Scrape window ─────────────────────────────────────────────
SCRAPE_DAYS_BACK = 7

# ── Schedule (informational; real schedule lives in launchd plist) ──
SCHEDULE_DAYS = ["Monday", "Thursday"]
SCHEDULE_TIME = "09:00"

# ── Politeness / anti-bot ─────────────────────────────────────
DELAY_MIN = 2
DELAY_MAX = 8
MAX_RETRIES = 3
# Generous timeout: uscanyin's deeper paginated pages can take ~17s to
# render server-side. A short timeout drops them entirely.
REQUEST_TIMEOUT = 30

# Cap pages per platform to stop runaway pagination. Real signal
# rarely needs more than this within a 7-day window.
MAX_PAGES_PER_PLATFORM = 30

# Desktop-only UAs. Mobile UAs trigger different HTML layouts on some sites
# (e.g. usahuarenjie returns a layout without the div.hover wrappers).
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

# ── Platforms ─────────────────────────────────────────────────
# `pagination`: 'path' or 'query'. The actual page-URL construction
# lives in each platform module — this just documents the shape.
PLATFORMS = [
    {
        "id": "168worker",
        "name": "168worker",
        "color": "#2563EB",
        "url": "https://www.168worker.com/list/1_0",
        "pagination": "path",
        "enabled": True,
    },
    {
        "id": "usahuarenjie",
        "name": "华人街生活网",
        "color": "#3D6B21",
        "url": "https://www.usahuarenjie.com/category-catid-251.html",
        "pagination": "path",
        "enabled": True,
    },
    {
        "id": "500work",
        "name": "500work",
        "color": "#B45309",
        "url": "https://www.500work.com/",
        "pagination": "query",
        "enabled": True,
    },
    {
        "id": "uscanyin",
        "name": "北美餐饮通",
        "color": "#9D174D",
        "url": "https://uscanyin.com/en/jobs",
        "pagination": "query",
        "enabled": True,
        # Deeper paginated pages take ~17s to render server-side. Cap tight:
        # ~16 posts per page × 8 pages = ~128 posts, far more than a 7-day
        # restaurant window needs from this site.
        "max_pages": 8,
    },
    {
        "id": "niuyuegongzuo",
        "name": "纽约工作网",
        "color": "#5B21B6",
        "url": "https://niuyuegongzuo.com/",
        "pagination": "query",
        "enabled": True,
    },
]


def platform_by_id(pid: str) -> Optional[dict]:
    for p in PLATFORMS:
        if p["id"] == pid:
            return p
    return None


# ── Paths ─────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_JSON = PROJECT_ROOT / "docs" / "data" / "posts.json"
LOG_DIR = PROJECT_ROOT / "logs"
