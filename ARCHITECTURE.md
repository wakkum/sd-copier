# SD Video Backup — Architecture

**Purpose of this document:** a self-contained reference to how the tool is
built, why the non-obvious decisions were made, and where the traps are.
Written so it can be read cold, without this project's conversation history.

The user-facing description lives in [README.md](README.md); the release
history and the reasoning behind each fix lives in
[CHANGELOG.md](CHANGELOG.md). This file covers structure and rationale.

---

## 1. What it is

A single-file Python/Tkinter desktop app that copies video files from an SD
card into a dated, structured folder on an external hard drive, verifies
every byte, and records what was copied. The operator is someone with no
technical background, working unsupervised, on either Windows or macOS.

That last sentence drives most of the design decisions below: no terminal,
no Python install, no choices that can silently destroy footage, and every
failure has to be visible rather than quiet.

## 2. Shape of the code

Everything is in [`app.py`](app.py), around 1,800 lines, deliberately one
file. It depends only on the Python standard library at runtime (`certifi`
is the single exception, and only for the update check). Tkinter ships with
Python on both target platforms, so there is nothing to install.

Rough layout, top to bottom:

| Region | What lives there |
| --- | --- |
| Constants | `APP_VERSION`, `UPDATE_REPO`, folder names, video extensions |
| `STRINGS` | Every piece of UI text, 5 languages × 59 keys |
| Config / registry | JSON read+write helpers, all pinned to UTF-8 |
| Drive detection | Per-platform enumeration and labelling |
| Copy engine | Hashing copy, verification, unique naming |
| Update | Release check, download, unpack, hand-off |
| `class App` | The whole GUI and its worker threads |

### Why one file

It is built by PyInstaller into a bundle the user double-clicks. A single
module keeps the build trivial and makes the whole program readable in one
pass, which matters more here than module hygiene at this size.

## 3. The folder convention

This is the fixed contract the whole tool exists to produce:

```
{HDD}/{YYYY_MM_DD}/{NN}_EVENT_{name}_{YYYY_MM_DD}/{Button camera|PB}/
```

- `NN` auto-increments per date, so a second shoot the same day becomes
  `02_EVENT_...` regardless of what it is named.
- `{name}` is free text, sanitised by `sanitize_event_name()`. The
  allowlist keeps letters and digits from every alphabet the app's
  languages use (accented Latin and Greek included) and strips everything
  else. A side effect worth knowing: because `.`, `/` and `\` are stripped,
  a name of `../..` collapses to `Event`, so path traversal through the
  event name is not possible.
- `Button` and `Powerbank` map to the on-disk folder names
  `Button camera` and `PB` via `CAMERA_FOLDER_NAMES`.

Alongside the footage: `info.txt` inside each event folder, an `IMPORTANT`
marker file when the day is flagged, and one running `All_Descriptions.txt`
at the root of the drive. The last of these is append-only and is what the
history viewer reads.

## 4. Copying and verification

`copy_with_hash()` streams the file in 1 MB chunks, writing the destination
while hashing the source in the same pass, and `hash_file()` then hashes
what landed. Equal digests mean the copy is good.

The reason it is written this way rather than copy-then-compare: the SD card
is the slow device, and a naive verify reads it twice. Hashing during the
copy halves the reads from the card.

**Nothing is ever overwritten.** `unique_destination()` checks the target
name immediately before each copy and falls back to `_2`, `_3`, … Two cards
with identical camera filenames both survive in full. The residual risk is
not data loss but *silent accumulation*: unrelated shoots landing in one
folder as `VID_0001.MP4` and `VID_0001_2.MP4` with no warning. Deliberately
left alone, pending real-world use.

Source files are never deleted or modified.

## 5. Threading model

Copying and updating run on daemon threads. Tkinter is not thread-safe, so
**every** UI touch from a worker goes through `self.after(0, ...)`. This is
not optional politeness — calling a widget method directly from a worker
raises `RuntimeError: main thread is not in main loop`, or worse, corrupts
the event loop silently.

`_set_busy()` locks the copy, eject and same-event buttons for the duration
of a copy. Ejecting a drive mid-write corrupts the copy in flight, so the
button is disabled rather than merely warned about. Update checks are
refused while a copy is running for the same reason.

## 6. Layout: why the form scrolls

Originally every widget packed top-to-bottom into a fixed-size window. On
Windows, where the system font is larger than on macOS, the form outgrew the
window — and Tk's packer **drops widgets that no longer fit** rather than
clipping or scrolling them. The green Copy button, the progress bar and the
status line were simply never drawn. The app looked complete and was
unusable.

The fix, and the rule to preserve:

- `_build_action_area()` is packed **before** the form, with `side="bottom"`,
  so the controls that must always be reachable claim their space first.
- The form lives in a scrolling canvas (`_build_scrollable_form()`) and
  absorbs whatever space is left.
- `_size_to_content()` opens the window at the form's natural height, capped
  to the screen.

Anything added to the bottom bar competes with the form for space. Anything
added to the form is free.

### The strip only shows what is usable

Pinning the strip solved the missing button but created the opposite
problem: it reserved its full height permanently. Measured at launch it was
216px — same-event row 80, Copy 48, eject/update 38, status 30, progress 20
— which on a 768px-high screen is a third of the window before anything has
happened, and more at Windows' larger font.

Three of those five rows say nothing at launch, so they are not shown until
they do: `_show_progress_area()` reveals the progress bar and status line
when a copy or update starts, and `_show_same_event()` reveals the
same-event row when a copy finishes. Idle strip is 86px and the window
opens at 707px rather than 845px.

**The trap:** `pack_forget()` followed by a plain `pack()` sends a widget to
the *end* of the pack order, not back where it was. For `side="bottom"`
widgets that silently moves the row — the same-event frame reappeared above
the form instead of above Copy. Every re-pack therefore passes an explicit
`before=`: progress before `action_frame`, status before `progress`, and
the same-event row before `_form_container`. Preserve this if you add a row.

## 7. Drive detection

`list_candidate_drives()` is per-platform: `/Volumes` on macOS, a
`GetLogicalDrives` bitmask on Windows (skipping `C:`), `/media` and `/mnt`
on Linux. Both removable and fixed types are accepted on Windows, because
card readers and external enclosures report inconsistently.

`drive_label()` builds the button text: volume name plus total capacity,
and the drive letter as well on Windows, e.g. `E:  SDCARD  (59.5 GB)` next
to `F:  BACKUP HDD  (3.6 TB)`. The size is the point — it is the fastest way
for a non-technical user to tell a card from a backup drive. Drives are
listed one per row because these labels overflow a horizontal strip.

### Formatting the card

`check_formattable()` is the single gate, and it fails closed: every
refusal raises `NotFormattable` with the message to show, and a drive whose
size cannot be read is refused rather than allowed. In order:

- The path must be a volume root (`E:\` / a mount point), not a folder.
- Not the selected destination, not the system volume, not the volume the
  app itself runs from (compared by `st_dev`, which is the volume serial on
  Windows).
- Windows: drive type removable or fixed only. Mac: not a disk image,
  virtual or read-only volume - a mounted `.dmg` is small and ejectable,
  exactly what a card looks like by size alone.
- Size: the largest of the volume size, the **whole physical disk** size
  and `shutil.disk_usage` must be at most `MAX_FORMAT_BYTES` (100 GB). The
  disk size is what keeps a small partition on the backup drive out. On
  Windows it comes from `IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS` then
  `IOCTL_DISK_GET_DRIVE_GEOMETRY_EX`, both `FILE_ANY_ACCESS`, so no admin;
  on the Mac from `diskutil info` on the volume's parent whole disk.
- Windows: never the same physical disk as the system drive.

The gate runs again right before formatting and must return the same
result, in case the card was swapped while the dialogs were open.

The backup check is advisory, not a gate: the card may have been backed up
some other way. It uses the duplicate-card fingerprint registry on the
selected destination, and the wording - and a second confirmation - make
plain when there is no record of a backup.

The card keeps its current file system (`card_file_system()`:
`GetVolumeInformationW` on Windows, `diskutil info` on the Mac). Only when
that is unknown, or not a card format such as NTFS, does
`target_file_system()` fall back to the size rule: FAT32 to 32 GiB, exFAT
above, which is how SDHC and SDXC cards ship.

Windows formats through `SHFormatDrive`, the dialog Explorer uses, run in
a **separate process**: the app starts a second copy of itself as
`<exe> --format-drive E`, which opens only that dialog and exits with 0
(formatted), 1 (cancelled) or 2 (failed). Called in-process, the dialog
changed the main window's DPI scaling - on a scaled display everything was
redrawn smaller until the window was resized. The dialog needs no
elevation for removable media and offers only that one drive, but it
cannot be told the file system - so the confirmation names the
one to check in the dialog. Its own default is the size rule, which
matches in nearly every case. It cannot make FAT32 above 32 GB at all, so
a larger FAT32 card can only come back as exFAT on Windows (the Mac keeps
it FAT32). The Mac runs `diskutil eraseVolume` with the exact file system.
Neither path has been run against a real card yet - see Known gaps.

## 8. Update mechanism

`check_for_update()` reads `releases/latest` from the GitHub API
unauthenticated, strips a leading `v` from `tag_name`, and compares against
`APP_VERSION`. **The tag is what counts, not the release title.** Releases
are also where the built apps are attached, so the API is both the version
oracle and the download source.

### TLS inside a bundle

A PyInstaller bundle carries its own OpenSSL with **no trust store** —
`ssl.get_default_verify_paths().cafile` is `None` inside the app, so every
HTTPS request fails verification. Because the failure is caught and reported
as "couldn't check for updates", this looked like a network problem for a
full release cycle. `ssl_context()` resolves it by using `certifi`'s bundle,
which the build scripts install so PyInstaller packs it. **Any new network
call must go through `ssl_context()`.**

### Self-update, Windows only

A running `.exe` cannot replace itself, but the Windows build is a *onedir*
folder, which is the opening: unpack the new version beside it and swap the
folders from outside the process.

1. Download the release asset to `%LOCALAPPDATA%\SDVideoBackup\update`.
2. Unpack to a staging folder.
3. Write `apply_update.bat` and launch it detached (`CREATE_NO_WINDOW`),
   with its working directory outside the folder about to be renamed.
4. Quit, so the folder is no longer locked.
5. The script waits on the old PID, renames the app folder to `.old`, moves
   the new one in, relaunches, and deletes itself.

Guards, all of which have tests behind them: the download host must be
`github.com` or `*.githubusercontent.com` over HTTPS; the archive must match
the size the API reported; archive entries resolving outside the destination
are rejected; an archive not containing the executable is refused. The old
folder is kept until the swap succeeds and restored if it fails, so a failed
update leaves the working app in place rather than nothing.

Two traps in the batch script: `timeout` needs a console and the script runs
without one, so `ping` is used to pause; and the script must not live inside
the folder it is about to move.

macOS, Linux and the unfrozen script fall back to opening the release page.
Replacing a `.app` in place safely needs code signing, which needs the Apple
Developer Program.

> **Proven working on Windows, October 2026.** A copy running 1.5.1
> installed 1.5.2 through the updater: it downloaded, closed, reopened on
> the new version, and the new feature was present. The swap script, the
> detached hand-off and the relaunch all work on a real machine.
>
> It could not be tested by updating *to* the version that introduced it,
> because the installed copy must already contain the swap code, which is
> why 1.5.0 and 1.5.1 were both released: 1.5.1 carries no functional
> change and exists only to give 1.5.0 something to find.
>
> When testing a change here, read the version back from the app after it
> reopens rather than assuming success. The designed failure modes both
> look like "the app is still here": the swap is refused and the old
> version reopens unchanged, or the move half-fails and the rollback
> restores it.

## 8a. Logging and problem reports

`setup_logging()` writes to `~/.sd_video_backup.log`: startup with version
and platform, each copy with source, destination and result, every failed or
unverified file, update attempts, and unhandled errors with tracebacks.
`App.report_callback_exception` is redirected there too, because Tk
otherwise prints callback errors to a console the user does not have and
carries on as if nothing happened.

Two deliberate choices. It is a single file trimmed to its recent half past
512 KB rather than a rotating set, because the user has to find and send it.
And a log that cannot be opened falls back to a `NullHandler`, so a
read-only home directory can never stop the app starting.

"Report a Problem" copies the log to the Desktop as
`SD_Backup_Report_<date>.txt` with version, platform, language and the
selected drives on top, then opens the folder. Asking a non-technical person
for a dotfile in their home directory does not work.

### Uploading a report

`report-worker/` is a Cloudflare Worker that receives a report, stores the
full log in R2, and opens a GitHub issue summarising it.

**The point of the Worker is the token.** Opening an issue needs one, and a
token inside a binary handed to users is extractable with a text editor — the
same constraint that made the updater use a public repo rather than a private
one with an embedded credential. Moving it server-side removes the constraint
entirely: the app posts anonymously and holds no GitHub access at all, so the
reports repo can be private even though the app's own repo is public. That
matters, because a report carries folder names, drive labels and file paths,
which for this app means event and people names.

`REPORT_ENDPOINT` is blank in the shipped source. With it blank the button
behaves exactly as before and writes only to the Desktop, so the feature is
inert until someone deploys the Worker and fills it in.

The endpoint has no user accounts and so is necessarily open. `REPORT_KEY`
ships inside the app and is therefore friction, not security; the design
assumes anyone can post. Bodies are capped at 256 KB, issue creation is
capped per hour when the KV namespace is bound, and the token is scoped to
one private repo. Worst case someone wastes free-tier quota.

Two ordering decisions worth preserving: the Desktop copy is written
**before** any upload is attempted and kept regardless, so a dead connection
never loses a report; and if R2 succeeds but GitHub fails, the Worker returns
success rather than an error, because the report is safely stored and telling
the user it failed would invite them to give up.

The app asks before every upload and shows what is being sent. Do not make
this silent or remembered: it is a disclosure, not a preference.

## 9. Build and release

PyInstaller does not cross-compile, so each platform builds on itself:
`build_mac.sh` produces `dist/SD Video Backup.app`, `build_windows.bat`
produces `dist\SD Video Backup\` — a **folder**, not a lone `.exe`; the
executable will not run without the `_internal` folder beside it.

To try a change on a real machine before releasing it, use
[`.github/workflows/test-build.yml`](.github/workflows/test-build.yml)
instead: run it by hand against a branch or commit, and the zip is kept as
an artifact on that run. It has read-only permissions and never touches a
release, so the self-updater cannot offer a test build to anyone.

[`.github/workflows/build.yml`](.github/workflows/build.yml) builds both on
GitHub's runners and attaches the zips to a release, triggered by a version
tag or manually against an existing tag. The manual trigger takes a separate
`ref`, because a tag can predate a fix to the build scripts themselves.

Releasing is just pushing a version tag. The workflow's first job creates
the GitHub release for that tag if it does not exist yet, with the tag's
section of `CHANGELOG.md` as the notes, and the two builds wait for it
before uploading onto it. (Up to 1.5.3 the release had to be created
first, with `gh release create <tag> --target main`, or the upload failed.)
The new release is marked latest, which is what the self-updater reads.

Gotchas the CI run exposed, both now fixed but worth not reintroducing:
`pip install --upgrade pip <other packages>` fails on Windows because pip
cannot replace itself while running, and a `.bat` does not propagate exit
codes, so a failed build happily printed "Done" and exited 0.

Both builds are unsigned: Gatekeeper on macOS needs a right-click → Open on
first launch, SmartScreen on Windows needs "More info" → "Run anyway".

## 10. Deliberately not in the repo

`HOW_TO_USE.pdf` is the bilingual guide for the end user and is **not
published** — it is gitignored at the owner's request. `howto/` holds its
generator (`build_howto.py`) and the mockup screenshots
(`make_screens.py`), and is gitignored for the same reason: it contains the
guide's full text.

The PDF covers English and Greek only. The in-app Help button
(`HELP_TEXT` in `app.py`, one entry per language) is what a French, German
or Italian user reads instead, and it is the only guide that ships with
the build. **Two places to keep in step when behaviour changes**, and the
in-app one matters more because it reaches every user.

The mockups are HTML re-creations of the UI, not real screenshots, because
capturing the Tk window needs Screen Recording permission that the build
machine does not grant. **They must be kept in step with `app.py` by hand.**

An earlier copy of the generator was lost when a scratch directory was
cleared; it was reconstructed from the PDF's own embedded text and images.
That is why it now lives inside the project rather than in temporary space.

## 10a. Current state (8 October 2026)

- Latest **release** is 1.5.3. `main` is at **1.5.4**, committed and
  pushed but not released, so the version display, the log file and
  "Report a Problem" are not yet in anyone's hands.
- `report-worker/` is written and tested but **not deployed**: no Worker,
  no R2 bucket, no token, and `wakkum/sd-copier-reports` does not exist
  yet. `REPORT_ENDPOINT` is blank, so the button writes only to the
  Desktop. Deploying is the owner's job (see that folder's README).
- Uploading footage to cloud storage was discussed and **rejected as part
  of this app**. Proton Drive has no usable API: the SDK cannot
  authenticate, is not sanctioned for third-party production use, and
  Proton's crypto migration in late 2026 or early 2027 will break older
  releases; rclone's backend is beta, reverse-engineered, and loads whole
  files into memory, which is unworkable for video. The watched-folder
  approach (drop files where a vendor's own desktop client syncs them)
  works for any provider and needs no credentials, and remains the
  fallback if this is revisited.
- The decision instead was a **separate, private tool** that uploads from
  the backup drive to the user's own NAS over Tailscale and SSH, kept out
  of this public repo because it carries hostnames and paths. Not started:
  it is blocked on two answers - whether it runs on the owner's Mac (CLI)
  or the non-technical user's Windows laptop (a second GUI app), and which
  path on `/volume1` it writes to.

## 11. Known gaps

- **Format SD Card is untested on the Mac** (1.6.0). On Windows it was
  tried with a real card before release: the card formatted and the backup
  hard drive was refused. The Mac path (`diskutil eraseVolume`) has only
  run against simulated drives.

- The mockups in `howto/` are hand-maintained and drift from the UI
  unless regenerated after a layout change (§10). This has already
  happened once: they showed a window with no Help button for three days
  after it shipped.
- There are no automated tests. Everything verified so far has been ad hoc
  and discarded, including checks that caught real bugs (string-key
  parity, pack ordering, the zip traversal guard).
- No warning when an event folder already contains files (§4).
- `webbrowser.open()` is called on a URL from the GitHub API without
  validating it; low severity, consciously accepted.
- The registry JSON is read without a size bound — a local denial of
  service at worst.
- The LaunchAgent log path under `/tmp` is predictable; only relevant on
  multi-user Macs.
- `autolaunch/` installers are opt-in and are never run by the app.
