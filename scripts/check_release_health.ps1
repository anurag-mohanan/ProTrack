# Production / staging host health check for ProTrack release gate.
# Usage:
#   .\scripts\check_release_health.ps1
#   .\scripts\check_release_health.ps1 -BaseUrl http://192.168.20.254

param(
    [string]$BaseUrl = "http://192.168.20.254"
)

$ErrorActionPreference = "Continue"
$script:failed = 0

function Test-Endpoint {
    param(
        [string]$Name,
        [string]$Method = "GET",
        [string]$Path,
        [hashtable]$Headers = @{},
        [string]$Body = $null,
        [int[]]$AcceptStatus = @(200),
        [string]$MustContain = $null
    )
    $uri = "$BaseUrl$Path"
    try {
        if ($Method -eq "POST") {
            $response = Invoke-WebRequest -Uri $uri -Method Post -Headers $Headers -ContentType "application/json" -Body $Body -UseBasicParsing -TimeoutSec 15
        }
        else {
            $response = Invoke-WebRequest -Uri $uri -Method Get -Headers $Headers -UseBasicParsing -TimeoutSec 15
        }
        $code = [int]$response.StatusCode
        if ($AcceptStatus -contains $code) {
            if ($MustContain -and ($response.Content -notmatch $MustContain)) {
                Write-Host "FAIL  $Name ($code but body missing expected content) $Path"
                $script:failed++
                return $null
            }
            Write-Host "PASS  $Name ($code) $Path"
            return $response
        }
        Write-Host "FAIL  $Name ($code) $Path"
        $script:failed++
        return $null
    }
    catch {
        $code = $null
        if ($_.Exception.Response) {
            $code = [int]$_.Exception.Response.StatusCode
        }
        if ($code -and ($AcceptStatus -contains $code)) {
            Write-Host "PASS  $Name ($code) $Path"
            return $null
        }
        Write-Host "FAIL  $Name ($($_.Exception.Message)) $Path"
        $script:failed++
        return $null
    }
}

Write-Host "ProTrack release health check against $BaseUrl"
Write-Host ""
Write-Host "NOTE: Do not trust bare /health via IIS - SPA rewrite often returns HTML 200."
Write-Host ""

# Canonical gate: API must answer through the reverse proxy.
Test-Endpoint -Name "Public settings" -Path "/api/v1/settings/public" -MustContain '"company"' | Out-Null

$loginBody = '{"email":"admin@prosohm.com","password":"Password@123"}'
$loginResponse = Test-Endpoint -Name "Login" -Method POST -Path "/api/v1/auth/login" -Body $loginBody -AcceptStatus @(200, 401)

$token = $null
if ($loginResponse) {
    try {
        $token = ($loginResponse.Content | ConvertFrom-Json).access_token
    }
    catch {
        $token = $null
    }
}

if ($token) {
    $auth = @{ Authorization = "Bearer $token" }
    Test-Endpoint -Name "Report catalog" -Path "/api/v1/reports/catalog" -Headers $auth | Out-Null
    Test-Endpoint -Name "Projects list" -Path "/api/v1/projects?limit=5" -Headers $auth | Out-Null
    Test-Endpoint -Name "Lookups teams" -Path "/api/v1/lookups/teams" -Headers $auth | Out-Null
}
else {
    Write-Host "WARN  Skipping authenticated checks (login did not return a token)."
    Write-Host "      If login returned 401, password may differ on this host - still OK if status is not 502."
}

Write-Host ""
if ($script:failed -gt 0) {
    Write-Host "RESULT: FAIL - $($script:failed) checks failed. Backend/proxy is unhealthy (typical 502 = API process down)."
    Write-Host "Next steps for senior tester ON 192.168.20.254:"
    Write-Host "  1. Confirm IIS ARR reverse-proxy target (usually 127.0.0.1:8000)."
    Write-Host "  2. On the server, curl http://127.0.0.1:8000/api/v1/settings/public"
    Write-Host "  3. If local curl fails, start API: python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
    Write-Host "  4. If local curl works but /api via IIS is 502, fix ARR/web.config proxy to that port."
    Write-Host "  5. Deploy latest code + pip install -r requirements.txt, then restart API."
    Write-Host "  6. Re-run this script until RESULT: PASS."
    exit 1
}

Write-Host "RESULT: PASS - host API is reachable for release testing."
exit 0
