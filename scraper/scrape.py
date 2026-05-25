"""Entry point: scrape every enabled platform and write the dashboard JSON."""

from __future__ import annotations

import importlib
import logging
import sys
from typing import List

from . import config
from .output import write_posts_json
from .platforms.base import Post

log = logging.getLogger("scrape")


# Map platform id → module name under scraper.platforms
PLATFORM_MODULE = {
    "168worker": "_168worker",
    "usahuarenjie": "usahuarenjie",
    "500work": "_500work",
    "uscanyin": "uscanyin",
    "niuyuegongzuo": "niuyuegongzuo",
}


def _load_scraper(platform_id: str):
    """Dynamically import scraper.platforms.<module>:Scraper."""
    mod_name = PLATFORM_MODULE.get(platform_id)
    if not mod_name:
        return None
    try:
        mod = importlib.import_module(f"scraper.platforms.{mod_name}")
    except ModuleNotFoundError as exc:
        log.info("Platform %s not implemented yet (%s)", platform_id, exc)
        return None
    return getattr(mod, "Scraper", None)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    all_posts: List[Post] = []
    summary_lines = []

    enabled = [p for p in config.PLATFORMS if p.get("enabled", False)]
    log.info(
        "Running %d enabled platform(s): %s",
        len(enabled), ", ".join(p["id"] for p in enabled),
    )

    for plat in enabled:
        pid = plat["id"]
        ScraperCls = _load_scraper(pid)
        if not ScraperCls:
            log.warning("Skipping %s (no scraper class)", pid)
            summary_lines.append(f"  {pid:<16} SKIPPED (not implemented)")
            continue
        try:
            scraper = ScraperCls()
            posts = scraper.run(days_back=config.SCRAPE_DAYS_BACK)
            all_posts.extend(posts)
            summary_lines.append(f"  {pid:<16} {len(posts):>4} posts")
        except Exception as exc:  # noqa: BLE001 — keep one platform's failure isolated
            log.exception("Platform %s failed: %s", pid, exc)
            summary_lines.append(f"  {pid:<16} ERROR ({exc.__class__.__name__})")

    if not all_posts:
        log.warning("No posts collected from any platform.")

    out_path = write_posts_json(all_posts, config.SCRAPE_DAYS_BACK)

    print()
    print("=" * 60)
    print(f"Scrape complete. Output: {out_path}")
    print(f"Total restaurant posts (last {config.SCRAPE_DAYS_BACK}d): {len(all_posts)}")
    print("Per platform:")
    for line in summary_lines:
        print(line)
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
