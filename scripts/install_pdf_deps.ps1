#!/usr/bin/env pwsh
# Install PDF extraction deps into the Python that runs ProTrack API.
# Run THIS on the API host (e.g. 192.168.20.254), from the ProTrack deploy folder:
#   .\scripts\install_pdf_deps.ps1
# Then restart the API / IIS app pool / Windows service.

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

Write-Host "Python: $(python -c 'import sys; print(sys.executable)')"
Write-Host "Installing pdfplumber + pypdf..."
python -m pip install "pdfplumber>=0.11,<1.0" "pypdf>=5.0,<7.0"

python -c @"
import importlib
for name in ('pdfplumber', 'pypdf'):
    mod = importlib.import_module(name)
    print(f'OK {name} {getattr(mod, \"__version__\", \"?\")}')
"@

Write-Host ""
Write-Host "Done. Restart the ProTrack API process now, then retry Import workorder PDF."
