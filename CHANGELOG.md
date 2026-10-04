# Changelog

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
