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

mark_success() {
    # Heartbeat — the watchdog reads this file's mtime
    date +%s > logs/last_success
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

TARGET_DATE=$(python3 - <<'PY'
from datetime import date, timedelta
from scraper import config
print((date.today() - timedelta(days=getattr(config, "SCRAPE_END_LAG_DAYS", 1))).isoformat())
PY
)
CURRENT_DATE=$(python3 - <<'PY'
import json
try:
    with open("docs/data/posts.json", encoding="utf-8") as f:
        print(json.load(f).get("meta", {}).get("date_to", ""))
except Exception:
    print("")
PY
)

if [ "${RHMM_FORCE:-0}" != "1" ] && [ "$CURRENT_DATE" = "$TARGET_DATE" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] already current through ${TARGET_DATE}; skipping scrape."
    mark_success
    notify "Hiring Monitor: OK (current)" "Data current through ${TARGET_DATE}"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] === scrape complete ==="
    exit 0
fi

python3 -m scraper.scrape

# Pull the headline number out of the JSON for the success notification
TOTAL=$(python3 -c "import json; print(json.load(open('docs/data/posts.json'))['meta']['total_posts'])" 2>/dev/null || echo "?")
WARN_COUNT=$(python3 -c "import json; print(len(json.load(open('docs/data/posts.json'))['meta'].get('warnings', [])))" 2>/dev/null || echo 0)

# Only commit if any generated dashboard data file changed.
DATA_FILES="docs/data/posts.json docs/data/daily.json docs/data/cities.json"
CRITICAL_WARNINGS=$(python3 - <<'PY'
import json

try:
    meta = json.load(open("docs/data/posts.json", encoding="utf-8")).get("meta", {})
except Exception:
    print("could not read generated posts.json")
    raise SystemExit

critical_markers = (
    "all platforms returned 0",
    "dropped to 0",
    "dropped >70%",
    "fetch failure",
    "reached page cap",
    "scraper raised",
    "unparseable dates",
)

for warning in meta.get("warnings", []):
    text = str(warning)
    if any(marker in text for marker in critical_markers):
        print(text)
PY
)

if [ -n "$CRITICAL_WARNINGS" ] && [ "${RHMM_ALLOW_WARNINGS:-0}" != "1" ]; then
    echo "[FATAL] Critical scrape warning(s); refusing to commit or push generated data:" >&2
    echo "$CRITICAL_WARNINGS" >&2
    git restore -- $DATA_FILES 2>/dev/null || true
    notify "Hiring Monitor: BLOCKED" "Critical scrape warning; kept previous dashboard data." "Basso"
    exit 1
fi

if git diff --quiet -- $DATA_FILES 2>/dev/null; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] data files unchanged; skipping commit."
    mark_success
    notify "Hiring Monitor: OK (no change)" "${TOTAL} posts · ${WARN_COUNT} warnings"
else
    git add -- $DATA_FILES
    git commit -m "data: update $(date '+%Y-%m-%d %H:%M')" || {
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] git commit failed (maybe nothing staged)"
        mark_success
        notify "Hiring Monitor: commit skipped" "Nothing to commit"
        exit 0
    }
    if git remote get-url origin >/dev/null 2>&1; then
        if git push origin main; then
            mark_success
            notify "Hiring Monitor: OK" "${TOTAL} posts · ${WARN_COUNT} warnings · pushed"
        else
            notify "Hiring Monitor: push FAILED" "Commit landed locally; check 'git push' auth." "Basso"
            exit 1
        fi
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] no 'origin' remote configured; commit kept locally."
        mark_success
        notify "Hiring Monitor: OK (no remote)" "${TOTAL} posts · committed locally"
    fi
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] === scrape complete ==="
