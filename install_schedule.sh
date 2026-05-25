#!/bin/bash
# Install the launchd schedule (Mon + Thu 09:00 scrape, daily 10:00 watchdog).
# Idempotent: re-running unloads previous copies first.

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
LAUNCH_AGENTS="${HOME}/Library/LaunchAgents"

mkdir -p "${PROJECT_DIR}/logs"
mkdir -p "${LAUNCH_AGENTS}"
chmod +x "${PROJECT_DIR}/run.sh" "${PROJECT_DIR}/watchdog.sh" "${PROJECT_DIR}/check-health.sh" 2>/dev/null || true

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

install_plist() {
    local label="$1"
    local template="${PROJECT_DIR}/${label}.plist"
    local installed="${LAUNCH_AGENTS}/${label}.plist"

    if [ ! -f "$template" ]; then
        echo "Template plist not found: $template" >&2
        return 1
    fi

    sed "s|__PROJECT_PATH__|${PROJECT_DIR}|g" "$template" > "$installed"
    launchctl unload "$installed" 2>/dev/null || true
    launchctl load "$installed"
    echo "  installed: $installed"
}

echo ""
echo "Installing launchd jobs..."
install_plist "local.restaurant-hiring-monitor"
install_plist "local.restaurant-hiring-monitor-watchdog"

cat <<'EOF'

═══════════════════════════════════════════════════════════════════
  ONE MANUAL STEP REQUIRED — macOS Full Disk Access
═══════════════════════════════════════════════════════════════════

This project lives in iCloud Drive. macOS blocks launchd-spawned
processes from reading ~/Library/Mobile Documents/ unless you grant
Full Disk Access to the shell. Without this step the schedule fires
but every run fails with "Operation not permitted".

To fix (one time):

  1. Open  System Settings → Privacy & Security → Full Disk Access
  2. Click the + button (authenticate if asked)
  3. Press Cmd+Shift+G in the file picker
  4. Type:  /bin/bash    and press Return
  5. Select bash and click Open
  6. Toggle bash ON in the list
  7. (Optional but recommended) repeat for /bin/zsh and python3

You can also grant it to the specific scripts via Finder:
  → Finder → Cmd+Shift+G → paste the project path → drag run.sh +
    watchdog.sh into the Full Disk Access list.

Verify by running:

    launchctl start local.restaurant-hiring-monitor
    tail -f logs/scraper.log

You should see "=== scrape start ===" within ~10 seconds.

═══════════════════════════════════════════════════════════════════

Other useful commands:

  bash check-health.sh                             # current status
  launchctl start local.restaurant-hiring-monitor  # manual scrape
  launchctl start local.restaurant-hiring-monitor-watchdog
  tail -f logs/scraper.log

Uninstall later:
  launchctl unload ~/Library/LaunchAgents/local.restaurant-hiring-monitor.plist
  launchctl unload ~/Library/LaunchAgents/local.restaurant-hiring-monitor-watchdog.plist
  rm ~/Library/LaunchAgents/local.restaurant-hiring-monitor*.plist

EOF
