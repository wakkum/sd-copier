#!/bin/bash
# Removes the auto-launch LaunchAgent installed by install.sh.
set -e
PLIST="$HOME/Library/LaunchAgents/com.sdbackup.watcher.plist"

if [ -f "$PLIST" ]; then
    launchctl unload "$PLIST" 2>/dev/null || true
    rm -f "$PLIST"
    echo "Removed. SD Video Backup will no longer open automatically."
else
    echo "Nothing to remove - the auto-launch watcher isn't installed."
fi

rm -f "$HOME/.sd_video_backup_seen_volumes"
