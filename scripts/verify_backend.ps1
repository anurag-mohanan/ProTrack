#!/usr/bin/env pwsh
# Verify the running ProTrack API matches the current codebase.
# Usage: .\scripts\verify_backend.ps1 [port]

param([int]$Port = 8002)

$base = "http://127.0.0.1:$Port"
try {
    $schema = Invoke-RestMethod -Uri "$base/openapi.json" -TimeoutSec 5
} catch {
    Write-Host "FAIL: No API responding on $base"
    exit 1
}

$projectParams = @($schema.paths.'/api/v1/projects'.get.parameters | ForEach-Object { $_.name })
$lifecycleEnum = $schema.components.schemas.ProjectLifecycleFilter.enum

Write-Host "API port: $Port"
Write-Host "Project params: $($projectParams -join ', ')"

if ($projectParams -notcontains 'lifecycle') {
    Write-Host "FAIL: Stale API — missing lifecycle parameter (found: $($projectParams -join ', '))"
    Write-Host "Stop old servers and run: .\scripts\start_backend.ps1"
    exit 1
}

if ($lifecycleEnum -notcontains 'all') {
    Write-Host "FAIL: Stale API — lifecycle enum missing 'all' (found: $($lifecycleEnum -join ', '))"
    exit 1
}

$login = Invoke-RestMethod -Uri "$base/api/v1/auth/login" -Method Post `
    -ContentType 'application/json' `
    -Body '{"email":"admin@prosohm.com","password":"Password@123"}'
$headers = @{ Authorization = "Bearer $($login.access_token)" }
$projects = Invoke-RestMethod -Uri "$base/api/v1/projects?lifecycle=all&limit=500" -Headers $headers

Write-Host "OK: lifecycle=all returns $($projects.Count) projects"
if ($projects.Count -lt 1) {
    Write-Host "WARN: Expected imported projects in protrack.db"
}
exit 0
