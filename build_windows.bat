@echo off
REM Build a double-clickable Windows .exe (no Python needed to run it).
REM Run this ONCE on a Windows PC: build_windows.bat
REM Result: dist\SD Video Backup.exe -- copy that anywhere for the non-technical user.
cd /d "%~dp0"
python -m venv .venv_build
call .venv_build\Scripts\activate.bat
pip install --upgrade pip pyinstaller certifi
pyinstaller --windowed --noconfirm --name "SD Video Backup" app.py
call .venv_build\Scripts\deactivate.bat
echo.
echo Done. Find the app at: dist\SD Video Backup.exe
pause
