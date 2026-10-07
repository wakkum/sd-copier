# SD Video Backup

A simple point-and-click tool to copy video files from an SD card to a
labelled, verified folder on an external hard drive. Built for someone with
no technical background to use unsupervised.

## What it does

1. User inserts the SD card and connects the external HDD.
2. Opens the app, picks the SD card and the HDD. Both are auto-detected
   and listed with their volume name and total size (and, on Windows,
   the drive letter), so the small card is easy to tell from the big
   backup drive.
3. Fills in: date, camera (`Button` or `Powerbank`), an event name (e.g.
   "Birthday party" - free text, optional), a description, and whether to
   mark the day as very important.
4. Clicks "Copy videos now".

The interface language can be switched from the dropdown in the top right
corner of the app: **English, Greek, French, German, Italian**. The choice
is remembered for next time.

The app copies every video file it finds (recursively, so it doesn't matter
which subfolder the camera stored them in) into:

```
{HDD}/{YYYY_MM_DD}/{NN}_EVENT_{name}_{YYYY_MM_DD}/{Button camera|PB}/
```

matching the existing folder convention. Every copied file is verified
byte-for-byte against the original on the SD card before it's counted as
successful. Original files on the SD card are never deleted or modified.

For each event, it writes:

- `info.txt` inside the event folder — date, camera, description, important
  flag, and a list of any files that failed to copy or failed verification.
- An `IMPORTANT` marker file inside the event folder, if marked important.
- An entry appended to `All_Descriptions.txt` at the root of the hard drive —
  a single running log of every description ever entered, in the order the
  events were copied, so there's one place to read through everything that's
  been backed up without opening each folder individually.

When the copy finishes, the destination folder opens automatically in
Finder/Explorer so the user can see the result right away.

The leading number (`NN`) auto-increments if you run the tool again for the
same date (e.g. a second recording later the same day becomes `02_EVENT_...`),
regardless of what the event is named. The event name is typed freely by the
user (letters and numbers from any of the supported alphabets are all
fine, accents included); it's cleaned up automatically for use in a folder
name (spaces become underscores, symbols like `/` or `:` are stripped).
Leaving it blank just calls the folder "Event".

## One-time setup (do this once per computer, as the technical person)

You need Python 3 installed to build the app once. After that, the
non-technical user just double-clicks the resulting app/exe — no Python or
terminal required for them.

### Mac

```bash
./build_mac.sh
```

Produces `dist/SD Video Backup.app`. Copy it to `/Applications` (or
anywhere) on the user's Mac. On first launch, right-click > Open once to
bypass the "unidentified developer" warning (unsigned app).

### Windows

Double-click `build_windows.bat` (or run it from a Command Prompt) on a
Windows machine with Python installed.

Produces `dist\SD Video Backup\`, a folder containing
`SD Video Backup.exe` alongside an `_internal` folder it needs to run.
Copy the **whole folder** to the user's PC (e.g. Desktop) — the .exe on its
own won't start. Right-click the .exe > "Send to" > "Desktop (create
shortcut)" gives them something simple to double-click. Windows SmartScreen
may warn on first run since it's unsigned — click "More info" > "Run
anyway".

> Note: you must build the Windows version on a Windows machine and the Mac
> version on a Mac — PyInstaller doesn't cross-compile. Only rebuild when
> `app.py` changes; the built app/exe runs indefinitely on its own after that.

### Or let GitHub build them for you

You don't have to build either one by hand.
[`.github/workflows/build.yml`](.github/workflows/build.yml) builds both on
GitHub's runners and attaches the zips to a release: push a version tag and
it runs automatically, or trigger it from the Actions tab against a tag that
already exists. This is the practical way to get the Windows build without
owning a Windows machine. The apps it produces are still unsigned, so the
first-run warnings above apply either way.

## Other features

- **Add Another Camera to This Event** — after a successful copy, this
  button lights up. It reuses the same date, event name, description and
  importance flag, flips to the other camera, and clears the source field
  so you can plug in the second camera's card and land its footage in the
  *same* event folder instead of creating a new one.
- **View Backup History** — opens a searchable window listing every backup
  ever logged to the currently selected hard drive (reads
  `All_Descriptions.txt`), most recent first.
- **Duplicate-card detection** — before copying, the app fingerprints the
  card's contents (filenames + sizes) against a small registry file kept
  on the destination drive. If it looks like the same card was already
  backed up, it asks for confirmation instead of silently re-copying.
- **Report a Problem** — copies `~/.sd_video_backup.log` to the Desktop as
  `SD_Backup_Report_<date>.txt`, prefixed with the version, platform and
  selected drives, and opens the folder. The log records startup, each
  copy and its result, every failed or unverified file, update attempts
  and any unhandled error with a traceback.
- **Help / How to use** — opens the full guide inside the app, in whichever
  of the five languages the interface is set to. The separate
  `HOW_TO_USE.pdf` is English and Greek only, so this is the only
  instructions a French, German or Italian user has; keep it in step with
  the UI when behaviour changes.
- **Empty-field reminder** — clicking Copy with the event name or the
  description left blank asks whether to continue, naming which one was
  missed. Both stay optional; the prompt defaults to No so a stray Enter
  does not skip past it.
- **Free space check** — refuses to start (with a clear error) if the
  destination drive doesn't have enough room for the files being copied.
- **Eject SD Card & Hard Drive** — safely ejects both drives from within
  the app once you're done.
- **Check for Updates** — looks at this repo's
  [latest release](https://github.com/wakkum/sd-copier/releases/latest).
  On Windows the app installs the update itself: it downloads the release
  zip, unpacks it next to the current folder, then a detached script waits
  for the app to exit, swaps the folders and relaunches. The old folder is
  kept until the swap succeeds, so a failure rolls back rather than
  leaving a broken install, and it all happens under the user's profile
  with no admin rights. Downloads are restricted to GitHub hosts over
  HTTPS and checked against the size the release API reported; archives
  containing paths outside the destination are refused. On Mac the app
  offers the download page instead, since replacing a signed `.app` in
  place is a different problem. Updating is blocked during a copy.

See [autolaunch/](autolaunch/) for optional, opt-in scripts that open the
app automatically when an SD card is inserted (Mac: fully automatic via a
LaunchAgent; Windows: added as a one-click AutoPlay option — see that
folder's README for why Windows can't be made fully silent).

## Notes

- The app remembers the last hard drive you used and suggests it next time.
- The window opens sized to its contents and the form scrolls, so the
  green Copy button stays reachable on short screens and at the larger
  system font Windows uses.
- Video formats recognized: mp4, mov, m4v, avi, mts, m2ts, wmv, flv, mkv,
  3gp, 3gpp.
- If a file with the same name already exists in the destination, the copy
  is renamed (`_2`, `_3`, ...) rather than overwritten.
- If any files fail to copy or fail verification, they're listed in
  `info.txt` and flagged in the on-screen result — nothing fails silently.

## Releasing an update

`UPDATE_REPO` in `app.py` points at this repo. To make "Check for Updates"
find something: bump `APP_VERSION` in `app.py`, rebuild the app/exe, and
publish a [GitHub Release](https://github.com/wakkum/sd-copier/releases/new)
tagged with that version (e.g. `v1.3.0`) with the built `.app`/`.exe`
attached. Until a release exists, "Check for Updates" just reports it
couldn't reach anything — this is expected on a fresh repo.
