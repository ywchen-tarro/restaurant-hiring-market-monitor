#!/bin/bash
# Watchdog — runs once a day and notifies if the scraper hasn't succeeded
# recently. Catches the case where the Mac was asleep through the Mon/Thu
# 09:00 window and missed the run, or where every run since the last good
# one has failed.

set -u  # NOT set -e: we want this script to keep going on a missing file
cd "$(dirname "$0")"

mkdir -p logs

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

# Max age before we consider the data stale. 96h = 4 days; scrape runs every
# 3-4 days (Mon → Thu = 3, Thu → Mon = 4). Anything > 4 days is suspicious.
MAX_AGE_HOURS=96

notify() {
    local title="$1"
    local message="$2"
    osascript -e "display notification \"$message\" with title \"$title\" sound name \"Basso\"" 2>/dev/null || true
}

HEARTBEAT="logs/last_success"

if [ ! -f "$HEARTBEAT" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] watchdog: no heartbeat file at $HEARTBEAT"
    notify "Hiring Monitor: never ran" "No successful run on record. Try: bash run.sh"
    exit 0
fi

# stat -f %m on macOS prints mtime as a unix epoch
LAST=$(stat -f %m "$HEARTBEAT")
NOW=$(date +%s)
AGE_SECONDS=$((NOW - LAST))
AGE_HOURS=$((AGE_SECONDS / 3600))
AGE_DAYS=$((AGE_HOURS / 24))

echo "[$(date '+%Y-%m-%d %H:%M:%S')] watchdog: last successful run was ${AGE_HOURS}h ago"

if [ "$AGE_HOURS" -gt "$MAX_AGE_HOURS" ]; then
    notify "Hiring Monitor: STALE" "Last successful scrape was ${AGE_DAYS}d ${AGE_HOURS}h ago"
fi
