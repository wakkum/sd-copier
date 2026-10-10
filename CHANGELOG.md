# Changelog

## 1.6.0

### Added
- **Format SD Card.** A button at the bottom wipes the chosen card so it
  is empty for the camera again, without leaving the app. It only ever
  formats an SD card: anything over 100 GB is refused, measured on the
  whole physical disk as well as the volume, so the backup hard drive - or
  a small partition on it - can never qualify. It also refuses the
  selected backup drive, the system disk, folders, disk images, network
  and CD drives, and any drive whose size it cannot read. Before erasing,
  it says whether this card's videos are in the backup drive's records,
  and asks a second time when they are not; both questions default to No.
  The card keeps the format it has now - FAT32 stays FAT32 - falling back
  to FAT32 up to 32 GB and exFAT above only if it cannot be read. Windows
  uses the system's own Format dialog for that one drive (no admin
  needed), and the confirmation names the format to check there; the Mac
  uses `diskutil eraseVolume`. Help explains it in all five languages.

  On Windows the Format window runs in a separate process: opening it from
  inside the app made the whole window shrink on a scaled display until it
  was resized.

  Not yet tried on a real card - see Known gaps in ARCHITECTURE.md.

## 1.5.4

### Added
- **The version is shown in the window.** It sits in the title bar and
  next to the heading. Previously the only way to find out which version
  was running was to click "Check for Updates" and read the dialog, which
  is no use when asking someone remotely what they have, or when
  confirming an update actually took.
- **A log file, and a "Report a Problem" button.** When something failed
  on the user's machine there was nothing to inspect: no console, and the
  dialog gone by the time they described it. The app now logs startup,
  every copy with its source, destination and result, each failed or
  unverified file, update attempts, and any unhandled error with its
  traceback, to `~/.sd_video_backup.log`. Tk errors are routed there too,
  since Tk otherwise prints them to a console nobody has and carries on.
  The log is trimmed to its recent half past 512 KB, and a log that
  cannot be written never stops the app starting.

  "Report a Problem" copies it to the Desktop as
  `SD_Backup_Report_<date>.txt` with the version, platform and selected
  drives on top, then opens the folder. Asking a non-technical person for
  a dotfile in their home folder does not work; this gives them something
  to attach.

- **One-click problem reports, if the endpoint is deployed.**
  `report-worker/` is a Cloudflare Worker that takes a report, stores the
  full log in R2 and opens a GitHub issue. The user needs no GitHub
  account and the app holds no credential: the token lives in the Worker,
  which is what allows the reports repo to be private while the app's own
  repo is public. `REPORT_ENDPOINT` is blank in the source, so until it is
  deployed and filled in the button behaves exactly as before. The Desktop
  copy is written before any upload and kept regardless, so a failed send
  never loses the report, and the app asks before every upload showing
  what is being sent.

### Changed
- The in-app help and `HOW_TO_USE.pdf` both document the above, and the
  guide's screenshots were regenerated: they still showed a window with
  no Help button, three days after it shipped.

## 1.5.3

### Changed
- **The Help window reads like a document rather than a text dump.**
  Section headings are bold and green, steps carry a bold number with
  hanging indent, bullets are real bullets at two levels, and the body is
  a proportional font on white with a titled header and a rule. The text
  is reflowed rather than shown with the line breaks it was typed with, so
  it wraps to the window width instead of being locked to a fixed column.
  Verified that no content is lost in the reflow, and that all five
  languages parse to the same structure: 6 headings, 7 steps, 9 bullets,
  5 sub-bullets.

## 1.5.2

### Added
- **A Help button, in all five languages.** The printed guide
  (`HOW_TO_USE.pdf`) only exists in English and Greek, so a French, German
  or Italian user had no instructions at all. The guide now lives inside
  the app, follows the language dropdown, and ships with every build. It
  sits in the utility row inside the scrolling form rather than the pinned
  strip at the bottom, which stays 86px.
- **A reminder when the event name or description is left empty.** Both
  are optional as far as the copy is concerned, but an empty description
  is the one thing that cannot be recovered later: the footage is still
  there, but what it was is gone. Clicking Copy with either field blank
  now asks whether to continue, naming which one was missed, and defaults
  to No. Answering yes copies exactly as before.

### Fixed
- **The pinned bottom strip took too much of a small screen.** Pinning the
  action area to the bottom kept the Copy button reachable, but it reserved
  its height permanently: 216px on a Mac and more at the larger font
  Windows uses, which on a 768px-high screen was a third of the window
  before anything had happened. Nothing in that strip is usable before the
  first copy, so none of it is shown until it is - the same-event button
  does nothing until an event exists, and an empty progress bar and status
  line say nothing at all. They appear when a copy or update starts, and
  the same-event row when a copy finishes. The idle strip is now 86px, and
  the window opens 138px shorter, which on a 760px window is the
  difference between the form scrolling and fitting entirely.

## 1.5.1

No functional changes. Published so an installed 1.5.0 has something newer
to find, which is the only way to exercise the Windows self-update end to
end: the swap code has to already be in the running copy, so it cannot be
tested by updating *to* the version that introduces it.

## 1.5.0

### Added
- **The Windows build now installs its own updates.** "Check for Updates"
  previously only opened the release page, leaving the user to unzip a
  folder and replace the old one by hand. On Windows it now downloads the
  new version with a progress bar, unpacks it beside the current folder,
  and hands over to a small detached script that waits for the app to
  close, swaps the folders, and starts the new version. Everything happens
  under the user's own profile, so no admin rights are needed.

  Safeguards: the download host must be github.com or
  githubusercontent.com over HTTPS; the archive must match the size the
  release API reported; archive entries that would write outside the
  destination are rejected; and an archive that does not contain the
  application is refused. The previous folder is kept until the swap
  succeeds and is restored if it fails, so a failed update leaves the
  working app in place. Updating is blocked while a copy is running.

  Mac and Linux, and the unfrozen script, keep the previous behaviour of
  opening the download page - replacing a .app safely needs code signing.

## 1.4.0

Interface fixes, both reported from real use on Windows.

### Fixed
- **The green "Copy videos now" button was missing on Windows.** Every
  control was packed top to bottom into a fixed-height window. Windows
  draws the system font larger than macOS does, so the form outgrew the
  window, and Tk's packer silently drops whatever no longer fits rather
  than scrolling or clipping - taking the Copy button, the progress bar
  and the status line with it. The action area is now pinned to the
  bottom of the window and claims its space before the form, the form
  scrolls when it does not fit, and the window opens sized to its own
  content (capped to the screen height).

### Changed
- **Detected drives now show their size.** A row of buttons reading
  `E:` and `F:` gave no clue which was the SD card and which was
  the backup drive. Each drive is now a full-width button showing the
  letter, the volume name and the total capacity, e.g.
  "E:  SDCARD  (59.5 GB)" next to "F:  BACKUP HDD  (3.6 TB)" - the size
  being the fastest way to tell the two apart. On Mac the volume name is
  shown with the size in the same way.

## 1.3.0

Fixes from a full code and security review.

### Fixed
- **Copy could silently hang on Windows.** `info.txt` and the `IMPORTANT`
  marker were written without an explicit encoding, so on a Windows machine
  with a cp1252 locale any non-ASCII description raised `UnicodeEncodeError`
  — which isn't an `OSError` and so escaped the error handling, killing the
  copy thread after the files had copied. The app was left with a frozen
  progress bar and a permanently disabled Copy button. All file reads and
  writes (including the config and duplicate-detection registry) now pin
  UTF-8.
- **PowerShell injection in the Windows eject path.** The drive path was
  interpolated into a PowerShell `-Command` string; a non-drive-letter path
  (e.g. a UNC share) could inject arbitrary commands. The path is now passed
  as a bound parameter instead.
- **Eject was clickable during a copy**, allowing the drive to be unmounted
  mid-write and corrupting the file in flight. The copy, eject and
  same-event buttons are now locked for the duration of a copy.
- **Metadata write failures were reported as success.** If the drive went
  away after the last video copied but before the notes/log were written,
  the user still saw "Success!". Those writes now report failure and
  downgrade the dialog to a warning.
- **"Check for Updates" never worked in the built app.** A PyInstaller
  bundle ships its own OpenSSL with no trust store, so every HTTPS request
  failed certificate verification and the update check reported "couldn't
  check for updates" on every machine, regardless of network. The CA
  bundle (`certifi`) is now bundled at build time and used explicitly.
- **Stale event number after editing the date.** Using "Add Another Camera
  to This Event" and then changing the date could merge footage into an
  unrelated event folder. The pinned number is now invalidated if the date
  or destination changes.

### Changed
- **Verification is roughly twice as fast.** Files were previously copied
  and then re-read in full for a byte-for-byte comparison, reading the
  (slow) SD card twice. The copy now hashes the source as it streams and
  compares against a hash of the destination — same integrity guarantee,
  one source read instead of two.

### Removed
- Unused `eject_result` translation key (all five languages) and the
  now-dead `files_match` helper.

## 1.2.0

- Added French, German and Italian alongside English and Greek.
- "Add Another Camera to This Event" for adding a second camera's footage
  to the same event.
- Searchable backup history viewer.
- Duplicate-card detection, free-space check before copying, and a safe
  eject button.
- "Check for Updates" against the project's GitHub releases.
- Optional auto-launch-on-insert installers for Mac and Windows.

## 1.1.0

- Event name (free text) replaced the numeric event field.
- Interface language switchable between English and Greek.
- Byte-for-byte verification of every copied file, a running
  `All_Descriptions.txt` log, and automatic opening of the destination
  folder when a copy finishes.

## 1.0.0

- Initial version: copy video files from an SD card into a dated,
  structured folder on an external hard drive.
