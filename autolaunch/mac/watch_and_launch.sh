#!/bin/bash
# Runs each time /Volumes changes (a drive mounts or unmounts), triggered by
# the LaunchAgent in com.sdbackup.watcher.plist via its WatchPaths key.
#
# Looks for a newly-mounted volume that looks like a camera SD card (has a
# DCIM folder) and, if it hasn't already opened the app for that volume,
# launches "SD Video Backup". Volumes already handled are remembered in
# STATE_FILE so re-triggering on unrelated mount/unmount events doesn't
# reopen the app repeatedly.

APP_NAME="SD Video Backup"
STATE_FILE="$HOME/.sd_video_backup_seen_volumes"

touch "$STATE_FILE"

for vol in /Volumes/*/; do
  vol="${vol%/}"
  name=$(basename "$vol")

  # Skip the boot volume and anything already handled.
  [ "$name" = "Macintosh HD" ] && continue
  grep -qxF "$name" "$STATE_FILE" && continue

  if [ -d "$vol/DCIM" ]; then
    echo "$name" >> "$STATE_FILE"
    open -a "$APP_NAME"
    break
  fi
done

# Forget volumes that are no longer mounted, so re-inserting the same card
# later triggers the app again.
if [ -s "$STATE_FILE" ]; then
  tmp=$(mktemp)
  while IFS= read -r name; do
    [ -d "/Volumes/$name" ] && echo "$name" >> "$tmp"
  done < "$STATE_FILE"
  mv "$tmp" "$STATE_FILE"
fi
