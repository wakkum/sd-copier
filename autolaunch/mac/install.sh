#!/bin/bash
# Installs a LaunchAgent that opens "SD Video Backup" automatically whenever
# an SD card (a volume with a DCIM folder) is inserted.
#
# This runs at login, watches for changes under /Volumes, and only acts on
# a genuine new card - it does not run with elevated privileges and does
# not touch anything outside your own user account.
#
# Run this ONCE, as the person who will be using the computer day to day:
#   ./install.sh
#
# To remove it later, run uninstall.sh in this same folder.
set -e
cd "$(dirname "$0")"

SCRIPT_PATH="$(pwd)/watch_and_launch.sh"
PLIST_DEST="$HOME/Library/LaunchAgents/com.sdbackup.watcher.plist"

chmod +x "$SCRIPT_PATH"
mkdir -p "$HOME/Library/LaunchAgents"

sed "s#__SCRIPT_PATH__#$SCRIPT_PATH#" com.sdbackup.watcher.plist.template > "$PLIST_DEST"

launchctl unload "$PLIST_DEST" 2>/dev/null || true
launchctl load "$PLIST_DEST"

echo "Installed. From now on, inserting an SD card with a DCIM folder will"
echo "automatically open SD Video Backup."
echo ""
echo "Note: this only works while 'SD Video Backup.app' is in a fixed"
echo "location Spotlight can find it (e.g. /Applications). If you move the"
echo "app, no changes are needed here - it launches it by name via Spotlight."
