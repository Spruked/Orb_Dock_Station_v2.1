param(
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

$dockRoot = Split-Path -Parent $PSScriptRoot
$orbotRoot = Join-Path (Split-Path -Parent $dockRoot) 'Orbot'
$dockExecutable = Join-Path $dockRoot 'desktop\src-tauri\target\release\orbot-dock-station.exe'
$tokenPath = Join-Path $orbotRoot 'Orbot_Vault-Logic-System\.local\host-memory.token'
$logDirectory = Join-Path $dockRoot '.local'
$logPath = Join-Path $logDirectory 'restart-orbot.log'
$runtimePorts = @(16521, 16524, 16525)

New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null

function Write-RestartLog([string]$Message) {
    Add-Content -LiteralPath $logPath -Value ("{0} {1}" -f (Get-Date -Format o), $Message) -Encoding UTF8
}

function Invoke-LoopbackJson {
    param(
        [int]$Port,
        [string]$Path,
        [ValidateSet('Get', 'Post')][string]$Method = 'Get',
        [hashtable]$Headers = @{},
        [object]$Body = $null
    )
    $parameters = @{
        Uri = "http://127.0.0.1:$Port$Path"
        Method = $Method
        Headers = (@{ 'X-Orbot-Desktop' = '1' } + $Headers)
        TimeoutSec = 5
        UseBasicParsing = $true
    }
    if ($null -ne $Body) {
        $parameters.ContentType = 'application/json'
        $parameters.Body = ($Body | ConvertTo-Json -Compress)
    }
    Invoke-RestMethod @parameters
}

function Test-LoopbackPort([int]$Port) {
    try {
        $client = [System.Net.Sockets.TcpClient]::new()
        $async = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
        $connected = $async.AsyncWaitHandle.WaitOne(300)
        if ($connected) { $client.EndConnect($async) }
        $client.Close()
        return $connected
    } catch {
        return $false
    }
}

function Wait-PortsFree([int[]]$Ports, [int]$TimeoutSeconds = 60) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        $busy = @($Ports | Where-Object { Test-LoopbackPort $_ })
        if ($busy.Count -eq 0) { return }
        Start-Sleep -Seconds 1
    } while ((Get-Date) -lt $deadline)
    throw "Ports remain occupied after graceful shutdown: $($busy -join ', ')"
}

function Get-DockBackendProcesses {
    Get-CimInstance Win32_Process | Where-Object {
        $command = [string]$_.CommandLine
        $path = [string]$_.ExecutablePath
        $command -match '(?i)(^|\s)-m\s+uvicorn\s+app\.main:app' -and
        $command -match '(?i)(^|\s)--port\s+8000(\s|$)' -and
        (($command -like "*$dockRoot*") -or ($path -like "*$dockRoot*") -or ($path -like "*$dockRoot\backend\.venv\Scripts\python.exe*"))
    }
}

function Stop-OrphanedDockBackend {
    $processes = @(Get-DockBackendProcesses)
    if ($processes.Count -eq 0) { return $false }
    foreach ($process in $processes) {
        Write-RestartLog "Stopping verified orphaned Dock backend PID $($process.ProcessId)."
        Stop-Process -Id ([int]$process.ProcessId) -ErrorAction Stop
    }
    return $true
}

function Stop-OrbotSupervisorsGracefully {
    $supervisors = @(Get-CimInstance Win32_Process | Where-Object {
        $command = [string]$_.CommandLine
        $path = [string]$_.ExecutablePath
        $command -match '(?i)runtime\.supervisor' -and $path -like "$orbotRoot\*"
    })
    if ($supervisors.Count -eq 0) { return $false }

    $signalType = @'
using System;
using System.Runtime.InteropServices;
public static class OrbotRestartConsoleSignal {
    [DllImport("kernel32.dll", SetLastError=true)] public static extern bool FreeConsole();
    [DllImport("kernel32.dll", SetLastError=true)] public static extern bool AttachConsole(uint processId);
    [DllImport("kernel32.dll", SetLastError=true)] public static extern bool GenerateConsoleCtrlEvent(uint controlEvent, uint processGroupId);
}
'@
    Add-Type -TypeDefinition $signalType -ErrorAction SilentlyContinue
    foreach ($supervisor in $supervisors) {
        Write-RestartLog "Sending graceful Ctrl+Break to ORBOT supervisor PID $($supervisor.ProcessId)."
        [OrbotRestartConsoleSignal]::FreeConsole() | Out-Null
        if (-not [OrbotRestartConsoleSignal]::AttachConsole([uint32]$supervisor.ProcessId)) {
            throw "Could not attach to ORBOT supervisor console PID $($supervisor.ProcessId)."
        }
        if (-not [OrbotRestartConsoleSignal]::GenerateConsoleCtrlEvent(1, [uint32]$supervisor.ProcessId)) {
            [OrbotRestartConsoleSignal]::FreeConsole() | Out-Null
            throw "Could not send graceful Ctrl+Break to ORBOT supervisor PID $($supervisor.ProcessId)."
        }
        [OrbotRestartConsoleSignal]::FreeConsole() | Out-Null
    }
    return $true
}

function Read-VaultToken {
    if (-not (Test-Path -LiteralPath $tokenPath -PathType Leaf)) {
        throw "Owner Vault token is missing: $tokenPath"
    }
    $token = (Get-Content -LiteralPath $tokenPath -Raw).Trim()
    if (-not $token) { throw "Owner Vault token is empty: $tokenPath" }
    return $token
}

if (-not (Test-Path -LiteralPath $dockExecutable -PathType Leaf)) {
    throw "Built Dock Station executable is missing: $dockExecutable"
}

Write-RestartLog 'Complete Orbot restart requested.'
if ($DryRun) {
    Write-RestartLog "Dry run: would gracefully close Dock, stop owned runtimes on $($runtimePorts -join ', '), and launch $dockExecutable."
    exit 0
}

$token = Read-VaultToken

# Ask the native Dock control listener to close the current Dock frontend. Its
# lifecycle supervisor then closes any runtimes it owns and performs AIMS review.
try {
    $dockStatus = Invoke-LoopbackJson -Port 16522 -Path '/status'
    $launchId = [string]$dockStatus.launch_id
    if ($launchId) {
        Write-RestartLog "Requesting graceful Dock shutdown for launch $launchId."
        Invoke-LoopbackJson -Port 16522 -Path '/shutdown' -Method Post `
            -Headers @{ 'Authorization' = "Bearer $token"; 'X-Orbot-Launch' = $launchId } -Body @{} | Out-Null
    }
} catch {
    Write-RestartLog "Dock was not running or did not accept shutdown: $($_.Exception.Message)"
}

# A previous failed launch can leave only Dock's backend behind after the
# native controller exits. There is no backend shutdown route; stop it only
# after proving its command line belongs to this Dock checkout.
if (-not (Test-LoopbackPort 16522) -and (Test-LoopbackPort 8000)) {
    if (-not (Stop-OrphanedDockBackend)) {
        throw 'Port 8000 is occupied, but its owner is not the verified Dock backend; refusing to stop it.'
    }
}

try {
    Wait-PortsFree @(16522, 8000) 45
} catch {
    throw "Dock frontend/backend did not shut down cleanly. $($_.Exception.Message)"
}

# If the runtimes were attached rather than Dock-owned, explicitly request a
# graceful Communication shutdown. The supervisor then stops its peers. This
# never touches shared llama.cpp, VIV, or Windows scheduled tasks.
try {
    $health = Invoke-LoopbackJson -Port 16521 -Path '/health'
    $instance = [string]$health.process_instance_id
    if ($instance) {
        Write-RestartLog "Requesting graceful Communication shutdown for instance $instance."
        Invoke-LoopbackJson -Port 16521 -Path '/lifecycle/shutdown' -Method Post `
            -Headers @{ 'Authorization' = "Bearer $token" } -Body @{ process_instance_id = $instance } | Out-Null
    }
} catch {
    Write-RestartLog "Communication was already stopped or rejected shutdown: $($_.Exception.Message)"
}

if ((Test-LoopbackPort 16521) -or (Test-LoopbackPort 16524) -or (Test-LoopbackPort 16525)) {
    Stop-OrbotSupervisorsGracefully | Out-Null
}

Wait-PortsFree $runtimePorts 45
Write-RestartLog 'ORBOT runtimes are stopped; launching complete Dock-owned application.'
Start-Process -FilePath $dockExecutable -WorkingDirectory $dockRoot
Write-RestartLog 'Dock Station launch submitted.'
