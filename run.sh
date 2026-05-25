#!/bin/bash
# Scrape every enabled platform, write docs/data/posts.json, commit and push.
# Triggered manually or by launchd (com.local.restaurant-hiring-monitor).

set -e

# Always operate from the repo root regardless of where launchd cd's first.
cd "$(dirname "$0")"

mkdir -p logs

# launchd uses a minimal PATH; make sure /usr/local and Homebrew are reachable
# so git and python3 resolve consistently across login + agent contexts.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] === scrape start ==="

# Defense in depth: bail if .gitignore has been broken and our internal-only
# files would otherwise become trackable.
for f in CLAUDE.md local; do
    if [ -e "$f" ] && ! git check-ignore -q "$f" 2>/dev/null; then
        echo "[FATAL] .gitignore no longer covers '$f' — refusing to run." >&2
        exit 1
    fi
done

python3 -m scraper.scrape

# Only commit if posts.json actually changed
if git diff --quiet docs/data/posts.json 2>/dev/null; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] posts.json unchanged; skipping commit."
else
    git add docs/data/posts.json
    git commit -m "data: update $(date '+%Y-%m-%d %H:%M')" || {
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] git commit failed (maybe nothing staged)"
        exit 0
    }
    if git remote get-url origin >/dev/null 2>&1; then
        git push origin main
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] no 'origin' remote configured; commit kept locally."
    fi
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] === scrape complete ==="
