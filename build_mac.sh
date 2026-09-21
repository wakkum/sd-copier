#!/bin/bash
# Build a double-clickable Mac app (no Python/terminal needed to run it).
# Run this ONCE on a Mac: ./build_mac.sh
# Result: dist/SD Video Backup.app  -- copy that to the non-technical user's Applications folder.
set -e
cd "$(dirname "$0")"
python3 -m venv .venv_build
source .venv_build/bin/activate
pip install --upgrade pip pyinstaller
pyinstaller --windowed --noconfirm --name "SD Video Backup" app.py
deactivate
echo ""
echo "Done. Find the app at: dist/SD Video Backup.app"
