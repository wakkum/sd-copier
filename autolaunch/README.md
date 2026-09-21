# Auto-launch on SD card insert (optional)

These scripts are **not** run automatically by the app or by anyone else -
you run them yourself, once, on the computer that will actually be used day
to day. They change startup/AutoPlay configuration on that machine, so they
are kept separate from the main app on purpose.

## Mac (`mac/`)

Installs a LaunchAgent (a per-user background helper, no admin rights
needed) that watches for a newly-inserted volume containing a `DCIM`
folder and opens "SD Video Backup" automatically - genuinely silent and
automatic, matching how the app is meant to be used.

```bash
cd mac
./install.sh
```

To remove it later: `./uninstall.sh` in the same folder.

Requires `SD Video Backup.app` to be discoverable by Spotlight (e.g. in
`/Applications`).

## Windows (`windows/`)

Registers the app as an option in the AutoPlay popup that appears when a
card is inserted.

```powershell
cd windows
powershell -ExecutionPolicy Bypass -File register_autoplay.ps1
```

**Windows limitation:** Microsoft removed the ability for a program to
launch completely silently on drive insertion years ago (it was a common
malware trick). This script gets the app listed as a one-click choice in
the AutoPlay popup - the user still sees that popup, but can tick "Always
do this for this device" so the *same* card opens it with one click next
time, without needing to browse for the app. That's the practical ceiling
on Windows; there's no way around it without asking the user to disable a
Windows security feature, which isn't worth the trade-off for this tool.

To remove it later: `powershell -ExecutionPolicy Bypass -File unregister_autoplay.ps1`.

Edit `$AppPath` at the top of `register_autoplay.ps1` first if
`SD Video Backup.exe` isn't on the Desktop.
