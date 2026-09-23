#!/usr/bin/env pwsh
# One-time / post-sync deploy on the ProTrack API HOST (e.g. 192.168.20.254).
# This is SERVER-SIDE — end users and browsers do nothing.
#
#   .\scripts\deploy_api_host.ps1
#
# What it does:
#   1. Installs requirements.txt into the Python that runs the API
#   2. Verifies pdfplumber + pypdf import
#   3. Restarts uvicorn / ProTrackBackend service if present

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

Write-Host "==== ProTrack API host deploy (server-side) ====" -ForegroundColor Cyan
Write-Host "Directory : $(Get-Location)"
Write-Host "Python    : $(python -c 'import sys; print(sys.executable)')"
Write-Host ""

Write-Host "Installing dependencies from requirements.txt ..."
python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

python -c @"
import pdfplumber, pypdf, sys
print('OK pdfplumber', pdfplumber.__version__)
print('OK pypdf', pypdf.__version__)
print('OK python', sys.executable)
"@
if ($LASTEXITCODE -ne 0) { throw "Dependency verification failed" }

Write-Host ""
Write-Host "Restarting API processes ..."

$svc = Get-Service -Name "ProTrackBackend" -ErrorAction SilentlyContinue
if ($svc) {
    Restart-Service -Name "ProTrackBackend" -Force
    Write-Host "Restarted Windows service ProTrackBackend" -ForegroundColor Green
} else {
    Get-CimInstance Win32_Process -Filter "name='python.exe'" |
        Where-Object { $_.CommandLine -match 'uvicorn app\.main:app' } |
        ForEach-Object {
            Write-Host "Stopping uvicorn PID $($_.ProcessId)"
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
    Start-Sleep -Seconds 2
    $port = if ($env:PROTRACK_API_PORT) { [int]$env:PROTRACK_API_PORT } else { 8000 }
    Write-Host "Starting uvicorn on 127.0.0.1:$port"
    Start-Process -FilePath "python" -ArgumentList "-m","uvicorn","app.main:app","--host","127.0.0.1","--port","$port" -WorkingDirectory (Get-Location) -WindowStyle Hidden
    Write-Host "uvicorn start requested" -ForegroundColor Green
}

Write-Host ""
Write-Host "Done. All users of http://<api-host>/finance will use this shared backend." -ForegroundColor Green
Write-Host "No browser or workstation install is required."
