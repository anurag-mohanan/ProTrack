#!/usr/bin/env pwsh
# Install PDF extraction deps into the Python that runs ProTrack API.
# Run THIS on the API host (e.g. 192.168.20.254), from the ProTrack deploy folder:
#   .\scripts\install_pdf_deps.ps1
# Then restart the API / IIS app pool / Windows service.

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

Write-Host "==== ProTrack PDF dependency install ====" -ForegroundColor Cyan
Write-Host "Working directory: $(Get-Location)"
Write-Host "Python: $(python -c 'import sys; print(sys.executable)')"
Write-Host "Version: $(python -c 'import sys; print(sys.version)')"
Write-Host ""
Write-Host "Installing from requirements.txt (pdfplumber, pypdf, Pillow, ...)..."
python -m pip install -r requirements.txt

Write-Host ""
python -c @"
import importlib
import sys
print('exe', sys.executable)
for name in ('pdfplumber', 'pypdf', 'PIL'):
    mod = importlib.import_module(name if name != 'PIL' else 'PIL')
    ver = getattr(mod, '__version__', '?')
    print(f'OK {name} {ver} -> {mod.__file__}')
"@

Write-Host ""
Write-Host "Done. Restart the ProTrack API process / IIS app pool now." -ForegroundColor Green
Write-Host "Then open Finance and retry Extract for review."
