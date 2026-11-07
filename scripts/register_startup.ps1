$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$executable = Join-Path $root 'desktop\src-tauri\target\release\orbot-dock-station.exe'
if (-not (Test-Path -LiteralPath $executable)) { throw "Build Dock first: $executable" }
$runPath = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
if (-not (Test-Path $runPath)) { New-Item -Path $runPath -Force | Out-Null }
Set-ItemProperty -Path $runPath -Name 'OrbotDockStation' -Value ('"{0}"' -f $executable)
Write-Host 'Orbot Dock Station will start with Windows and provide its tray icon.'
