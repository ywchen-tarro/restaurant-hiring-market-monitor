# Roadmap

Tracks the engineering work needed to take this from "MVP with 2 platforms" to a robust 5+ platform signal.

---

## Now: 5/5 platforms active

| Platform | Status | Transport |
|---|---|---|
| niuyuegongzuo.com | ✅ Active | `requests` (plain) |
| usahuarenjie.com | ✅ Active | `requests` (plain) |
| 168worker.com | ✅ Active | `curl_cffi` impersonating chrome120 (TLS-fingerprint bypass) |
| 500work.com | ✅ Active | `curl_cffi` impersonating chrome120 (same CMS as 168worker) |
| uscanyin.com | ✅ Active | `requests` (plain, 30s timeout for slow paginated pages) |

All 5 platforms are now scraping. The 168worker / 500work block turned out to be a TLS-fingerprint check — Level 2 of the escalation ladder (`curl_cffi`) cleared it on the first try.

### Known data quality issue — 168 ↔ 500work overlap

168worker.com and 500work.com share the same CMS *and the same post database*: identical `/page/<id>` URLs, identical titles, byte-for-byte the same listings. Enabling both inflates the aggregate `total_posts` because the same job is counted twice (once per host).

**Per-platform breakdowns still tell the truth** — the dashboard shows each platform's reach independently. The aggregate signal is approximately doubled for whatever portion is co-listed. Until cross-platform deduplication lands (below), trust per-platform trends; treat the aggregate as a directional indicator only.

---

## Anti-bot escalation ladder

Try in order; stop at the first level that works for a given platform. **Don't jump straight to Playwright** — each level up trades reliability for weight, fragility, and a much larger attack surface.

### Level 1: Better headers (≈ 1 hour of work)

What plain `requests` sends today is good enough for most sites but misses a few signals Cloudflare reads:

- `Accept-Language` with realistic regional values, not just `zh-CN,zh;q=0.9`
- `Sec-Ch-Ua`, `Sec-Ch-Ua-Mobile`, `Sec-Ch-Ua-Platform` (the Chromium client hints)
- `Sec-Fetch-Dest: document`, `Sec-Fetch-Mode: navigate`, `Sec-Fetch-Site: none` (or `same-origin` for in-site navigation)
- `Upgrade-Insecure-Requests: 1`
- `Referer` set to the previous page (or the platform's own homepage on first request)
- A persistent `requests.Session()` so cookies set on the first request are sent on the next

Add these to `scraper/http_client.py` and try again. Free, no new dependencies, no behavioral change for the working platforms.

### Level 2: `curl_cffi` (≈ 2 hours)

`curl_cffi` is a Python wrapper around libcurl-impersonate. It produces a TLS handshake (JA3 / JA4 fingerprint) and HTTP/2 frame ordering that exactly match a real Chrome/Safari/Firefox. Many Cloudflare-class anti-bots compare the TLS fingerprint against a known-good list; plain Python `requests` fails because it uses urllib3's openssl defaults.

```bash
pip install curl_cffi
```

```python
from curl_cffi import requests as cf_requests
r = cf_requests.get(url, impersonate="chrome120", timeout=15)
```

Integration: introduce a per-platform `HTTP_CLIENT` option in `scraper/config.py`. Platforms can opt into `curl_cffi` while others stay on plain `requests`. `polite_get` already abstracts the request — just need a fan-out by client name.

This is the most likely thing that fixes 168worker and 500work. Try this **before** anything heavier.

### Level 3: `cloudscraper` (≈ 2 hours)

`cloudscraper` solves the JavaScript challenge Cloudflare serves as an interstitial. Useful only when the protection is the older "I'm under attack" challenge page (you'll know — the 403 body will look like a Cloudflare page, not a generic 403).

```bash
pip install cloudscraper
```

Same integration pattern as curl_cffi.

### Level 4: Playwright headless (≈ 4 hours setup + ongoing maintenance)

Reach for this only if levels 1-3 don't work or the platform JS-renders its listing client-side.

```bash
pip install playwright
playwright install chromium
```

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(user_agent="Mozilla/5.0 ...")
    page = ctx.new_page()
    page.goto(url)
    page.wait_for_selector(".jobs-grid1")
    html = page.content()
    browser.close()
```

Tradeoffs:
- +300 MB browser binary
- 5-10× slower per request
- Whole new failure surface (zombie processes, font issues, timeouts)
- Significantly larger memory footprint (each `page` is ~50 MB)

Integration: subclass `BasePlatformScraper` with a `fetch_page` override that uses Playwright instead of `polite_get`. Keep this opt-in per-platform.

### Level 5: CDP against the system Chrome (≈ 6 hours setup)

The most sophisticated option — drive your already-running macOS Chrome via the Chrome DevTools Protocol. Inherits the real user profile's cookies, JA3 fingerprint, browser version, even logged-in sessions. Effectively unbeatable by anti-bot.

```bash
# Launch Chrome with remote debugging:
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir=$HOME/Library/Application\ Support/Google/Chrome
```

```python
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    ctx = browser.contexts[0]  # uses the existing profile
    page = ctx.new_page()
    page.goto(url)
    # ...
```

Tradeoffs:
- Requires Chrome to be running (or launched on demand). Fine on a personal Mac, hostile to headless servers.
- The scrape now leaves cookies and history in your real Chrome — small privacy footprint.
- Most fragile setup: any Chrome update can break the CDP version.

This is the option mentioned by the user. Recommended path: **only fall to this if curl_cffi + good headers don't move the needle**.

---

## Per-platform plan

### 168worker.com (priority 1)

1. Capture the exact failure: hit https://www.168worker.com/list/1_0 with `curl -v` and save the 403 body. Inspect for Cloudflare markers (`__cf_bm` cookie hint, `cf-ray` header).
2. Try Level 1 headers. If still 403 → Level 2.
3. Once a page returns 200, build `scraper/platforms/_168worker.py`. Pagination from the PRD says `path` style — confirm against a real fetch.
4. Set `"enabled": true` in `config.PLATFORMS`.

### 500work.com (priority 2)

Same playbook as 168worker. Both came back 403 in the same probe; they may be on the same anti-bot product. If Level 2 fixes one it likely fixes both.

### uscanyin.com (priority 3)

Plain GET works (confirmed in probes). The issue is scale: ~4,593 pages × ~50 listings/page is ~225k posts to iterate before hitting the 7-day cutoff if the listing isn't strictly date-sorted. Two options:

- Hope it's date-sorted (most listing sites are) — let `MAX_PAGES_PER_PLATFORM` cap it. Likely fine since restaurant-only volume is probably modest.
- Find a sort or filter parameter to apply (`?sort=newest`, etc.) — read the page source.

The pagination is `query`-style; URL likely `/en/community/jobs/paged/<N>`.

### meiguogongzuo.com (priority 4 — new platform)

Similarweb rank #4,783 (much higher than 168worker's #685,532). Worth adding once the existing 3 are unblocked because its higher traffic likely correlates with higher post volume. No structure investigation done yet.

### us168168.com (priority 5 — new platform)

Similarweb rank #4,518. Likely similar to meiguogongzuo. Same status — uninvestigated.

---

## Other follow-ups from review

### Correctness / robustness (P1)

- [ ] **Cross-platform deduplication** (HIGH — promoted to P0 after enabling 168+500work): track normalized-title hashes across platforms; expose `meta.unique_posts` distinct from `meta.total_posts`; dashboard headline should use unique. Without this the aggregate signal is inflated by the 168/500work overlap.
- [ ] **Add tests**: pytest fixtures with saved HTML pages per platform; unit tests for `date_parser`, `regions.classify`, `keywords.is_restaurant`, `output._merge_history`. The MVP currently relies on manual smoke tests — first DOM change is silent breakage.
- [ ] **English 2-letter state code matching**: require word boundaries for `NY`/`NJ`/`MA`/`CT`/`PA`/`VA` to avoid `SUNNYVALE → NY` false matches.
- [ ] **launchd missed-run catch-up**: if the Mac was asleep on a scheduled run, fire a catch-up on next wake. (Watchdog notification is in place; actual catch-up scrape on wake is not.)
- [x] **Stale-data alerting** — done. Watchdog plist + macOS Notification Center.

### Signal quality (P2)

- [ ] **Per-day time series**: today's `posts.json` is a rolling-7-day snapshot. Storing per-day rows enables moving averages, weekday adjustment, and step-change detection.
- [ ] **Weekday-adjusted aggregates**: weekends post 30-50% less; raw WoW deltas at the run level mix this signal in.
- [ ] **Platform-mix decomposition**: when 168worker comes back online, the total will jump from a *source* change, not a *market* change. Report `share_of_signal` per platform so consumers can see this. Consider a chained index (Laspeyres or geometric) on per-platform daily counts.

### UX (P2)

- [ ] **CSV export from the posts tab** — Growth/BDR will want to hand a region-filtered list to a campaign tool.
- [ ] **Choropleth state map on the region tab** — much higher signal density than the current top-5 mini-bars.
- [ ] **A one-sentence "headline" at the top of the page** — auto-generated summary like "本周招聘市场 ▲ 增长 18%，东部最活跃" before the KPI cards.
- [ ] **Screenshot in the README** — replace the sample-JSON snippet with an actual rendered image.

### Operational

- [ ] **Branch protection on `main`** — block `--force` push on the public repo.
- [ ] **Dependabot + secret-scanning** — free on public repos; turn on.
- [ ] **`gh auth setup-git` documented in install_schedule.sh** — without it, launchd push will fail silently.
