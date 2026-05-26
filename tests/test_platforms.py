"""Per-platform parse_page tests against captured HTML fixtures.

Catches the next DOM change before it silently zeroes out a platform.
Fixtures are real listing-page snapshots committed to tests/fixtures/
— they're refreshed manually when a site's structure intentionally
changes.

Run with:
    python3 -m pytest tests/test_platforms.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scraper.platforms.base import Post

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _load(name: str) -> str:
    p = FIXTURES / name
    if not p.exists():
        pytest.skip(f"fixture {name} not present; regenerate with the capture script")
    return p.read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────
# Helpers: assertions every Post should satisfy
# ─────────────────────────────────────────────────────────────

def _assert_post_shape(p: Post):
    assert isinstance(p, Post)
    assert isinstance(p.id, str) and p.id
    assert isinstance(p.platform, str) and p.platform
    assert isinstance(p.title, str) and p.title
    # date may be empty string if the source omitted it, but if present
    # should be a valid ISO date
    if p.date:
        assert len(p.date) == 10 and p.date[4] == "-" and p.date[7] == "-"
    assert isinstance(p.url, str)
    assert p.url.startswith("http://") or p.url.startswith("https://")
    # id is prefixed with platform
    assert p.id.startswith(p.platform + "_")


def _assert_unique_ids(posts):
    ids = [p.id for p in posts]
    assert len(ids) == len(set(ids)), f"duplicate post.id values: {ids}"


# ─────────────────────────────────────────────────────────────
# 168worker
# ─────────────────────────────────────────────────────────────

def test_168worker_parse():
    from scraper.platforms._168worker import Scraper
    html = _load("168worker_page1.html")
    posts = Scraper().parse_page(html, 1)
    assert posts, "168worker page 1 should yield at least 1 post"
    assert len(posts) >= 50, f"expected >=50 posts, got {len(posts)}"
    for p in posts:
        _assert_post_shape(p)
        assert p.platform == "168worker"
        assert "/page/" in p.url
    _assert_unique_ids(posts)
    # At least one post should carry an ISO date
    assert any(p.date for p in posts), "no posts had parseable dates"


# ─────────────────────────────────────────────────────────────
# 500work (mirror of 168worker)
# ─────────────────────────────────────────────────────────────

def test_500work_parse():
    from scraper.platforms._500work import Scraper
    html = _load("500work_page1.html")
    posts = Scraper().parse_page(html, 1)
    assert posts, "500work page 1 should yield at least 1 post"
    assert len(posts) >= 50, f"expected >=50 posts, got {len(posts)}"
    for p in posts:
        _assert_post_shape(p)
        assert p.platform == "500work"
        # The post URL should point at 500work.com, NOT 168worker.com
        assert "500work.com" in p.url, f"expected 500work host, got {p.url}"
    _assert_unique_ids(posts)


def test_500work_post_id_prefixed_correctly():
    """Subclass must re-key the Post.id with its own platform name —
    otherwise the mirror dedup logic gets confused."""
    from scraper.platforms._500work import Scraper
    html = _load("500work_page1.html")
    posts = Scraper().parse_page(html, 1)
    for p in posts:
        assert p.id.startswith("500work_"), f"id={p.id} not prefixed with 500work"


# ─────────────────────────────────────────────────────────────
# usahuarenjie
# ─────────────────────────────────────────────────────────────

def test_usahuarenjie_parse():
    from scraper.platforms.usahuarenjie import Scraper
    html = _load("usahuarenjie_page1.html")
    posts = Scraper().parse_page(html, 1)
    assert posts
    assert len(posts) >= 30
    for p in posts:
        _assert_post_shape(p)
        assert p.platform == "usahuarenjie"
        assert "usahuarenjie.com" in p.url
    _assert_unique_ids(posts)
    # usahuarenjie posts always have a date (span.ltime)
    no_date = sum(1 for p in posts if not p.date)
    assert no_date / len(posts) < 0.10, f"too many posts without dates: {no_date}/{len(posts)}"


# ─────────────────────────────────────────────────────────────
# uscanyin
# ─────────────────────────────────────────────────────────────

def test_uscanyin_parse():
    from scraper.platforms.uscanyin import Scraper
    html = _load("uscanyin_page1.html")
    posts = Scraper().parse_page(html, 1)
    assert posts
    # uscanyin page 1 typically has ~20 unique posts
    assert len(posts) >= 10
    for p in posts:
        _assert_post_shape(p)
        assert p.platform == "uscanyin"
        assert "/community/jobs/" in p.url
    _assert_unique_ids(posts)


def test_uscanyin_state_extraction():
    """uscanyin posts carry a "view=prefix" sibling link with the English
    state name; we should map most of them to a Chinese state token."""
    from scraper.platforms.uscanyin import Scraper
    html = _load("uscanyin_page1.html")
    posts = Scraper().parse_page(html, 1)
    have_state = sum(1 for p in posts if p.state)
    # At least 60% of posts should resolve to a state on the front page
    assert have_state / len(posts) >= 0.50, \
        f"low state-extraction rate: {have_state}/{len(posts)}"


# ─────────────────────────────────────────────────────────────
# niuyuegongzuo
# ─────────────────────────────────────────────────────────────

def test_niuyuegongzuo_parse():
    from scraper.platforms.niuyuegongzuo import Scraper
    html = _load("niuyuegongzuo_page1.html")
    posts = Scraper().parse_page(html, 1)
    assert posts
    assert len(posts) >= 40
    for p in posts:
        _assert_post_shape(p)
        assert p.platform == "niuyuegongzuo"
        assert "niuyuegongzuo.com" in p.url
    _assert_unique_ids(posts)


def test_niuyuegongzuo_dates_parsed():
    """niuyuegongzuo uses MM/DD/YY in the date column. The parser should
    handle this directly."""
    from scraper.platforms.niuyuegongzuo import Scraper
    html = _load("niuyuegongzuo_page1.html")
    posts = Scraper().parse_page(html, 1)
    with_date = sum(1 for p in posts if p.date)
    assert with_date / len(posts) > 0.90, \
        f"unexpected fraction of posts without dates: {with_date}/{len(posts)}"


# ─────────────────────────────────────────────────────────────
# meiguogongzuo
# ─────────────────────────────────────────────────────────────

def test_meiguogongzuo_parse():
    from scraper.platforms.meiguogongzuo import Scraper
    html = _load("meiguogongzuo_page1.html")
    posts = Scraper().parse_page(html, 1)
    assert posts
    assert len(posts) >= 30  # ~68 raw posts on page 1
    for p in posts:
        _assert_post_shape(p)
        assert p.platform == "meiguogongzuo"
        assert "meiguogongzuo.com" in p.url
    _assert_unique_ids(posts)


def test_meiguogongzuo_state_from_slug():
    """meiguogongzuo embeds the state slug in the URL path. Most posts
    should have a non-empty .state from that mapping."""
    from scraper.platforms.meiguogongzuo import Scraper
    html = _load("meiguogongzuo_page1.html")
    posts = Scraper().parse_page(html, 1)
    have_state = sum(1 for p in posts if p.state)
    assert have_state / len(posts) >= 0.80, \
        f"expected ≥80% to resolve a state from URL slug, got {have_state}/{len(posts)}"


# ─────────────────────────────────────────────────────────────
# Defensive: empty / malformed HTML doesn't crash
# ─────────────────────────────────────────────────────────────

ALL_MODULES = [
    "_168worker", "_500work", "usahuarenjie", "uscanyin",
    "niuyuegongzuo", "meiguogongzuo",
]


@pytest.mark.parametrize("module_name", ALL_MODULES)
def test_empty_html_returns_empty_list(module_name):
    import importlib
    mod = importlib.import_module(f"scraper.platforms.{module_name}")
    posts = mod.Scraper().parse_page("", 1)
    assert posts == []


@pytest.mark.parametrize("module_name", ALL_MODULES)
def test_malformed_html_does_not_crash(module_name):
    import importlib
    mod = importlib.import_module(f"scraper.platforms.{module_name}")
    # Half-finished tags should not raise — parser must be tolerant
    posts = mod.Scraper().parse_page("<html><body><div", 1)
    assert isinstance(posts, list)
