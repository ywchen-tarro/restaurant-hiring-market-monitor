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

# launchd inherits a stripped environment. git push will fail silently if
# git can't find a credential helper that works without a TTY. The gh CLI
# stores its token in macOS Keychain and is accessible from launchd as long
# as gh is configured as the helper. `gh auth setup-git` does this — it's
# idempotent so we re-run it here as defensive setup.
if command -v gh >/dev/null 2>&1; then
    if ! gh auth status >/dev/null 2>&1; then
        echo "Warning: gh CLI is not authenticated. Run 'gh auth login' first." >&2
    else
        gh auth setup-git
    fi
else
    echo "Warning: gh CLI not on PATH. Install it or git push will fail under launchd." >&2
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
