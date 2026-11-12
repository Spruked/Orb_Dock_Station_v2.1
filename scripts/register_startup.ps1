$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$executable = Join-Path $root 'desktop\src-tauri\target\release\orbot-dock-station.exe'
if (-not (Test-Path -LiteralPath $executable)) { throw "Build Dock first: $executable" }
$runPath = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
if (-not (Test-Path $runPath)) { New-Item -Path $runPath -Force | Out-Null }
Set-ItemProperty -Path $runPath -Name 'OrbotDockStation' -Value ('"{0}"' -f $executable)
$desktop = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop 'Orbot Dock Station.lnk'
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $executable
$shortcut.WorkingDirectory = Split-Path -Parent $executable
$shortcut.IconLocation = (Join-Path $root 'desktop\src-tauri\icons\orbot-dock-station.ico')
$shortcut.Description = 'Launch Orbot through DockStation'
$shortcut.Save()
Write-Host "Startup entry configured: $executable"
Write-Host "Desktop shortcut configured: $shortcutPath"
