#!/usr/bin/env pwsh
# Start ProTrack backend on the configured dev port (default 8000).
# Run from the repository root:  .\scripts\start_backend.ps1

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$port = 8000
if ($env:PROTRACK_API_PORT) {
    $port = [int]$env:PROTRACK_API_PORT
}

Write-Host "Stopping existing uvicorn processes..."
Get-CimInstance Win32_Process -Filter "name='python.exe'" |
    Where-Object { $_.CommandLine -match 'uvicorn app\.main:app' } |
    ForEach-Object {
        Write-Host "  killing PID $($_.ProcessId)"
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }

Start-Sleep -Seconds 2

Write-Host "Starting ProTrack API on http://127.0.0.1:$port"
python -m uvicorn app.main:app --host 127.0.0.1 --port $port --reload
