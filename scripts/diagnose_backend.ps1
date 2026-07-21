#!/usr/bin/env pwsh
# Diagnose why the ProTrackBackend service fails to start.
#
# The Windows Service Manager only reports a generic "service did not return an
# error" message when the backend process crashes on startup. Run this from the
# repository root ON THE SERVER, using the SAME Python the service uses:
#
#     .\scripts\diagnose_backend.ps1
#
# It prints the real Python traceback plus the two most common post-upgrade
# causes: missing dependencies and the production secret guard.

$ErrorActionPreference = "Continue"
Set-Location (Join-Path $PSScriptRoot "..")

Write-Host ""
Write-Host "==== Python interpreter ====" -ForegroundColor Cyan
python --version
$py = (Get-Command python).Source
Write-Host "Executable: $py"

Write-Host ""
Write-Host "==== Required dependencies ====" -ForegroundColor Cyan
foreach ($mod in @("cryptography", "slowapi", "fastapi", "uvicorn", "sqlalchemy")) {
    $result = python -c "import $mod; print(getattr($mod, '__version__', 'ok'))" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host ("  {0,-14} {1}" -f $mod, $result) -ForegroundColor Green
    } else {
        Write-Host ("  {0,-14} MISSING  -> pip install -r requirements.txt" -f $mod) -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "==== Relevant environment ====" -ForegroundColor Cyan
$secretSet = if ($env:PROTRACK_SECRET_KEY) { "set" } else { "NOT set" }
$encSet = if ($env:PROTRACK_ENCRYPTION_KEY) { "set" } else { "NOT set" }
Write-Host "  PROTRACK_ENV            = $($env:PROTRACK_ENV)"
Write-Host "  INTERNAL_RELEASE        = $($env:INTERNAL_RELEASE)"
Write-Host "  PROTRACK_SECRET_KEY     = $secretSet"
Write-Host "  PROTRACK_ENCRYPTION_KEY = $encSet"

Write-Host ""
Write-Host "==== Importing app.main (real startup error, if any) ====" -ForegroundColor Cyan
$importOutput = python -c "import app.main; print('IMPORT OK')" 2>&1
Write-Host $importOutput
Write-Host ""
if ($LASTEXITCODE -ne 0) {
    Write-Host "Backend failed to import. The traceback above is the true cause of the crash." -ForegroundColor Red
} else {
    Write-Host "Backend imported cleanly. If the service still fails, the problem is in the" -ForegroundColor Yellow
    Write-Host "service wrapper (working directory, Python path, or account), not the app." -ForegroundColor Yellow
}
