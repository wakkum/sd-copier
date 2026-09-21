# Registers "SD Video Backup" as an AutoPlay option for removable drives.
#
# IMPORTANT - Windows limitation: unlike the old AutoRun.inf, Windows has
# not allowed a program to launch silently and automatically when a drive
# is inserted since Windows 7 (that was a common malware trick, so
# Microsoft locked it down). What THIS script can do is make the app show
# up as a one-click option in the AutoPlay popup that appears when a card
# is inserted, and the user can tick "Always do this for this device" so
# future insertions of the SAME card launch it with one click instead of
# none. It cannot be made fully silent/automatic like the Mac version.
#
# Run this ONCE, as the person who will be using the computer day to day,
# from a normal (non-admin) PowerShell window:
#   powershell -ExecutionPolicy Bypass -File register_autoplay.ps1
#
# Edit $AppPath below first if "SD Video Backup.exe" isn't at this location.

$AppPath = "$env:USERPROFILE\Desktop\SD Video Backup.exe"

if (-not (Test-Path $AppPath)) {
    Write-Host "Could not find the app at:" $AppPath
    Write-Host "Edit `$AppPath at the top of this script to point at your SD Video Backup.exe, then run it again."
    exit 1
}

$HandlerName = "SDVideoBackupHandler"
$HandlerBase = "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\AutoplayHandlers\Handlers\$HandlerName"

New-Item -Path $HandlerBase -Force | Out-Null
Set-ItemProperty -Path $HandlerBase -Name "Action" -Value "Back up videos with SD Video Backup"
Set-ItemProperty -Path $HandlerBase -Name "Provider" -Value "SD Video Backup"
Set-ItemProperty -Path $HandlerBase -Name "InvokeProgID" -Value ""
Set-ItemProperty -Path $HandlerBase -Name "InvokeVerb" -Value "open"
Set-ItemProperty -Path $HandlerBase -Name "DefaultIcon" -Value $AppPath
Set-ItemProperty -Path $HandlerBase -Name "ProgID" -Value ""
Set-ItemProperty -Path $HandlerBase -Name "ShellExecute" -Value "`"$AppPath`""
Set-ItemProperty -Path $HandlerBase -Name "InitCmdLine" -Value ""

# Make it available as a choice for generic removable-storage arrival
# (covers most SD card readers) and for the camera/"pictures" arrival
# event (covers readers Windows recognizes as a camera/WPD device).
$Events = @("StorageOnArrival", "PlayCameraOnArrival")
foreach ($EventName in $Events) {
    $EventPath = "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\AutoplayHandlers\EventHandlers\$EventName"
    New-Item -Path $EventPath -Force | Out-Null
    New-ItemProperty -Path $EventPath -Name $HandlerName -PropertyType String -Value "" -Force | Out-Null
}

Write-Host "Done. Insert an SD card and 'Back up videos with SD Video Backup' should now"
Write-Host "appear as an option in the AutoPlay popup. Tick 'Always do this for this"
Write-Host "device' to skip the popup for that same card in future."
