# Changelog

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
