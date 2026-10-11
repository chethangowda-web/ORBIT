# Keeps the ORBIT backend reachable for Google Chat on a Windows dev machine.
# Idempotent: does nothing when everything is already running. Run by the scheduled task
# "ORBIT keep running" at logon and every 5 minutes (see docs/OPERATIONS.md).
#
#   1. starts Docker Desktop if it is not running and waits for it
#   2. brings up postgres, redis and the backend (existing images; no rebuild)
#
# Log: %LOCALAPPDATA%\orbit-autostart.log

$ErrorActionPreference = "Continue"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$log = Join-Path $env:LOCALAPPDATA "orbit-autostart.log"
$dockerExe = Join-Path $env:LOCALAPPDATA "Programs\DockerDesktop\Docker Desktop.exe"

function Write-Log($message) {
    $line = "{0:yyyy-MM-dd HH:mm:ss} {1}" -f (Get-Date), $message
    Add-Content -Path $log -Value $line
    if ((Get-Item $log).Length -gt 512KB) { Get-Content $log -Tail 200 | Set-Content $log }
}

function Test-Docker {
    docker info *> $null
    return ($LASTEXITCODE -eq 0)
}

if (-not (Test-Docker)) {
    Write-Log "Docker is not responding; starting Docker Desktop"
    if (-not (Get-Process "Docker Desktop" -ErrorAction SilentlyContinue) -and (Test-Path $dockerExe)) {
        Start-Process $dockerExe
    }
    for ($i = 0; $i -lt 36; $i++) {
        Start-Sleep -Seconds 5
        if (Test-Docker) { break }
    }
}

if (-not (Test-Docker)) {
    Write-Log "Docker did not become ready within 3 minutes"
    exit 1
}

$running = docker ps --filter "name=orbit-backend" --filter "status=running" --format "{{.Names}}"
if (-not "$running".Contains("orbit-backend")) {  # "$running" is a string even when docker printed nothing
    Write-Log "orbit-backend is not running; bringing the stack up"
    $env:REDIS_PORT = "6380"
    $env:PYTHON_IMAGE = "mirror.gcr.io/library/python:3.11-slim"
    $env:NODE_IMAGE = "mirror.gcr.io/library/node:20-alpine"
    docker compose -f (Join-Path $root "docker-compose.yml") up -d postgres redis backend 2>&1 | ForEach-Object { Write-Log "compose: $_" }
}
