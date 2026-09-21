# Removes the AutoPlay handler registered by register_autoplay.ps1.
# Run from a normal (non-admin) PowerShell window:
#   powershell -ExecutionPolicy Bypass -File unregister_autoplay.ps1

$HandlerName = "SDVideoBackupHandler"

Remove-Item -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\AutoplayHandlers\Handlers\$HandlerName" -Force -ErrorAction SilentlyContinue

foreach ($EventName in @("StorageOnArrival", "PlayCameraOnArrival")) {
    Remove-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\AutoplayHandlers\EventHandlers\$EventName" -Name $HandlerName -ErrorAction SilentlyContinue
}

Write-Host "Removed. SD Video Backup will no longer appear in the AutoPlay popup."
