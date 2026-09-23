#!/usr/bin/env pwsh
# SERVER-SIDE ONLY — install PDF deps into the Python that runs the ProTrack API.
# End users / browsers never run this. Run once on the API host (e.g. 192.168.20.254):
#   .\scripts\install_pdf_deps.ps1
# Or prefer the full host deploy:
#   .\scripts\deploy_api_host.ps1
#
# After a normal API restart, missing deps are also auto-installed by the backend
# (PROTRACK_AUTO_INSTALL_DEPS=1, default) into the same Python process.

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
