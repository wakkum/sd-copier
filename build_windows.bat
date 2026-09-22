@echo off
REM Build a double-clickable Windows app (no Python needed to run it).
REM Run this ONCE on a Windows PC: build_windows.bat
REM Result: dist\SD Video Backup\ -- copy that whole folder for the user.
setlocal
cd /d "%~dp0"

python -m venv .venv_build || goto :failed
call .venv_build\Scripts\activate.bat || goto :failed

REM pip cannot replace itself while it is the running process on Windows, so
REM the upgrade has to go through `python -m pip` and stay a separate step -
REM bundling it with the other packages fails the whole install.
python -m pip install --upgrade pip || goto :failed
python -m pip install --upgrade pyinstaller certifi || goto :failed

REM Invoked as a module rather than the pyinstaller.exe shim so this doesn't
REM depend on the venv's Scripts folder being on PATH.
python -m PyInstaller --windowed --noconfirm --name "SD Video Backup" app.py || goto :failed

call .venv_build\Scripts\deactivate.bat
echo.
echo Done. Find the app at: dist\SD Video Backup\SD Video Backup.exe
echo Copy the whole "dist\SD Video Backup" folder - the .exe alone will not run.
REM Keep the window open so a human can read the output, but not on CI,
REM where nobody is there to press a key and the job would hang.
if not defined CI pause
exit /b 0

:failed
echo.
echo BUILD FAILED - see the error above. No app was produced.
if not defined CI pause
exit /b 1
