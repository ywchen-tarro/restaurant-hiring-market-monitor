#!/bin/bash
# Scrape every enabled platform, write docs/data/posts.json, commit, push.
# Triggered manually or by launchd (local.restaurant-hiring-monitor).
#
# Emits a macOS Notification Center notification on success and on failure
# so a missed/failed run is visible without checking logs. Writes a heartbeat
# file at logs/last_success which the watchdog plist reads.

set -e

cd "$(dirname "$0")"

mkdir -p logs

# launchd uses a minimal PATH; ensure git, python3, gh are reachable.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

PROJECT="$(pwd)"
PROJECT_BASENAME="$(basename "$PROJECT")"

notify() {
    # $1 = title, $2 = message, $3 (optional) = sound name
    local title="$1"
    local message="$2"
    local sound="${3:-}"
    local sound_clause=""
    [ -n "$sound" ] && sound_clause=" sound name \"$sound\""
    # Best-effort: never let notification failure mask the real exit code
    osascript -e "display notification \"$message\" with title \"$title\"$sound_clause" 2>/dev/null || true
}

on_error() {
    local code=$?
    notify "Hiring Monitor: FAIL" "Scrape failed (exit $code). See logs/scraper_error.log." "Basso"
    exit $code
}
trap 'on_error' ERR

echo "[$(date '+%Y-%m-%d %H:%M:%S')] === scrape start ==="

# Defense in depth: bail if .gitignore has been broken and our internal-only
# files would otherwise become trackable.
for f in CLAUDE.md local; do
    if [ -e "$f" ] && ! git check-ignore -q "$f" 2>/dev/null; then
        echo "[FATAL] .gitignore no longer covers '$f' — refusing to run." >&2
        notify "Hiring Monitor: FAIL" ".gitignore broken — refusing to run." "Basso"
        exit 1
    fi
done

python3 -m scraper.scrape

# Heartbeat — the watchdog reads this file's mtime
date +%s > logs/last_success

# Pull the headline number out of the JSON for the success notification
TOTAL=$(python3 -c "import json; print(json.load(open('docs/data/posts.json'))['meta']['total_posts'])" 2>/dev/null || echo "?")
WARN_COUNT=$(python3 -c "import json; print(len(json.load(open('docs/data/posts.json'))['meta'].get('warnings', [])))" 2>/dev/null || echo 0)

# Only commit if either data file actually changed.
DATA_FILES="docs/data/posts.json docs/data/daily.json"
if git diff --quiet -- $DATA_FILES 2>/dev/null; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] data files unchanged; skipping commit."
    notify "Hiring Monitor: OK (no change)" "${TOTAL} posts · ${WARN_COUNT} warnings"
else
    git add -- $DATA_FILES
    git commit -m "data: update $(date '+%Y-%m-%d %H:%M')" || {
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] git commit failed (maybe nothing staged)"
        notify "Hiring Monitor: commit skipped" "Nothing to commit"
        exit 0
    }
    if git remote get-url origin >/dev/null 2>&1; then
        if git push origin main; then
            notify "Hiring Monitor: OK" "${TOTAL} posts · ${WARN_COUNT} warnings · pushed"
        else
            notify "Hiring Monitor: push FAILED" "Commit landed locally; check 'git push' auth." "Basso"
            exit 1
        fi
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] no 'origin' remote configured; commit kept locally."
        notify "Hiring Monitor: OK (no remote)" "${TOTAL} posts · committed locally"
    fi
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] === scrape complete ==="
