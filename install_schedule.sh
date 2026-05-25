#!/bin/bash
# Install the launchd schedule (Mon + Thu 09:00 local time).
# Idempotent: re-running unloads any previously installed copy first.

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
LABEL="local.restaurant-hiring-monitor"
TEMPLATE="${PROJECT_DIR}/${LABEL}.plist"
INSTALLED="${HOME}/Library/LaunchAgents/${LABEL}.plist"

if [ ! -f "$TEMPLATE" ]; then
    echo "Template plist not found: $TEMPLATE" >&2
    exit 1
fi

mkdir -p "${PROJECT_DIR}/logs"
mkdir -p "${HOME}/Library/LaunchAgents"

# Substitute the absolute project path into the template
sed "s|__PROJECT_PATH__|${PROJECT_DIR}|g" "$TEMPLATE" > "$INSTALLED"

# Best-effort unload of any previous version, then load.
launchctl unload "$INSTALLED" 2>/dev/null || true
launchctl load "$INSTALLED"

echo ""
echo "Schedule installed → $INSTALLED"
echo "Runs at: Mon + Thu 09:00 local time"
echo ""
echo "Trigger a test run manually:"
echo "  launchctl start ${LABEL}"
echo ""
echo "Tail logs:"
echo "  tail -f ${PROJECT_DIR}/logs/scraper.log"
echo ""
echo "Uninstall later:"
echo "  launchctl unload ${INSTALLED} && rm ${INSTALLED}"
