#!/bin/bash
# One-screen status report for the hiring monitor.
# Run anytime: `bash check-health.sh` (no arguments).

cd "$(dirname "$0")"

cyan="\033[36m"; green="\033[32m"; red="\033[31m"; yellow="\033[33m"; gray="\033[90m"; reset="\033[0m"

echo -e "${cyan}════════════════════════════════════════════════════${reset}"
echo -e "${cyan}  Restaurant Hiring Market Monitor — Health${reset}"
echo -e "${cyan}════════════════════════════════════════════════════${reset}"
echo ""

# 1) Heartbeat
HEARTBEAT="logs/last_success"
if [ -f "$HEARTBEAT" ]; then
    LAST=$(stat -f %m "$HEARTBEAT")
    NOW=$(date +%s)
    AGE_H=$(( (NOW - LAST) / 3600 ))
    AGE_D=$(( AGE_H / 24 ))
    LAST_HUMAN=$(date -r "$LAST" '+%Y-%m-%d %H:%M:%S')
    if [ "$AGE_H" -gt 36 ]; then
        echo -e "Last success: ${red}${LAST_HUMAN}  (${AGE_D}d ${AGE_H}h ago — STALE)${reset}"
    elif [ "$AGE_H" -gt 24 ]; then
        echo -e "Last success: ${yellow}${LAST_HUMAN}  (${AGE_D}d ${AGE_H}h ago)${reset}"
    else
        echo -e "Last success: ${green}${LAST_HUMAN}  (${AGE_H}h ago)${reset}"
    fi
else
    echo -e "Last success: ${red}no heartbeat file — never ran successfully${reset}"
fi
echo ""

# 2) posts.json snapshot
if [ -f docs/data/posts.json ]; then
    python3 << 'PY'
import json, sys
try:
    d = json.load(open("docs/data/posts.json"))
    meta = d["meta"]
    print(f'posts.json:    {meta["total_posts"]} posts, window {meta["date_from"]} → {meta["date_to"]}')
    print(f'last_updated:  {meta["last_updated"]}')
    print(f'unclassified:  {meta.get("unclassified_region", 0)}')
    warnings = meta.get("warnings", [])
    if warnings:
        print(f'WARNINGS ({len(warnings)}):')
        for w in warnings:
            print(f'  • {w}')
    else:
        print(f'warnings:      none')
    print()
    print("Per-platform:")
    for pid, info in d.get("by_platform", {}).items():
        diag = meta.get("diagnostics", {}).get(pid, {})
        status = diag.get("status", "?")
        rows = diag.get("rows_parsed", "—")
        print(f'  {pid:<16} total={info["total"]:>3}  status={status}  rows_parsed={rows}')
    print()
    print(f'History entries: {len(d.get("history", []))}')
except Exception as e:
    print(f'ERROR reading posts.json: {e}')
PY
else
    echo -e "${red}posts.json not found — has the scraper ever run?${reset}"
fi
echo ""

# 3) launchd status
echo -e "${cyan}--- launchd jobs ---${reset}"
LAUNCHD_DOMAIN="gui/$(id -u)"
if launchctl print "$LAUNCHD_DOMAIN/local.restaurant-hiring-monitor" >/dev/null 2>&1; then
    echo -e "  ${green}scrape job installed${reset}"
    launchctl print "$LAUNCHD_DOMAIN/local.restaurant-hiring-monitor" 2>/dev/null \
        | grep -E 'state =|runs =|last exit code =|run interval =' | sed 's/^/  /'
else
    echo -e "  ${yellow}scrape job NOT installed${reset} — run: bash install_schedule.sh"
fi
echo ""
if launchctl print "$LAUNCHD_DOMAIN/local.restaurant-hiring-monitor-watchdog" >/dev/null 2>&1; then
    echo -e "  ${green}watchdog installed${reset}"
    launchctl print "$LAUNCHD_DOMAIN/local.restaurant-hiring-monitor-watchdog" 2>/dev/null \
        | grep -E 'state =|runs =|last exit code =|run interval =' | sed 's/^/  /'
else
    echo -e "  ${yellow}watchdog NOT installed${reset} — run: bash install_schedule.sh"
fi
echo ""

# 4) Recent log tails
echo -e "${cyan}--- last 10 lines of logs/scraper.log ---${reset}"
if [ -f logs/scraper.log ]; then
    tail -10 logs/scraper.log | sed 's/^/  /'
else
    echo -e "  ${gray}(no log yet)${reset}"
fi
echo ""

echo -e "${cyan}--- last 5 lines of logs/scraper_error.log ---${reset}"
if [ -s logs/scraper_error.log ]; then
    tail -5 logs/scraper_error.log | sed 's/^/  /'
else
    echo -e "  ${gray}(no errors logged)${reset}"
fi
echo ""

# 5) git state
echo -e "${cyan}--- git ---${reset}"
git status --short | sed 's/^/  /'
echo ""
echo -e "  ${gray}Last commit:${reset} $(git log -1 --format='%h %s (%cr)')"
echo ""

echo -e "${cyan}════════════════════════════════════════════════════${reset}"
