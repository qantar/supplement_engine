#!/usr/bin/env pwsh
# Phase 2b-prod gate validation (production pilot hardening)
# Prerequisite: Phase 2a gate should pass on dev profile first.
# Usage:
#   .\scripts\validate_phase2a_gate.ps1          # dev profile baseline
#   .\scripts\validate_phase2b_prod_gate.ps1      # prod hardening checks

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

$DefaultProdApiKey = "pilot-dev-key-change-me"
$patientId = "f47ac10b-58cc-4372-a567-0e02b2c3d479"
$prodComposeFile = "docker-compose.prod.yml"
$composeProd = @("docker-compose.yml", $prodComposeFile)

function Get-ProjectRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Invoke-DockerCompose {
    param(
        [string[]]$ComposeFiles = @("docker-compose.yml"),
        [Parameter(Mandatory)][string[]]$ComposeArgs
    )
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $cmd = @("compose")
    foreach ($f in $ComposeFiles) {
        $cmd += @("-f", $f)
    }
    $cmd += $ComposeArgs
    & docker @cmd 2>&1 | Out-Null
    $code = $LASTEXITCODE
    $ErrorActionPreference = $prev
    return $code
}

function Get-HttpStatusCode {
    param([scriptblock]$Request)
    try {
        & $Request | Out-Null
        return 200
    }
    catch {
        if ($_.Exception.Response) {
            return [int]$_.Exception.Response.StatusCode.value__
        }
        throw
    }
}

function Test-FeatureImplemented {
    param(
        [string]$Name,
        [scriptblock]$Test
    )
    try {
        & $Test
        Write-Host "  PASS: $Name" -ForegroundColor Green
        return $true
    }
    catch {
        if ($_.Exception.Message -match "^SKIP:") {
            $reason = $_.Exception.Message -replace '^SKIP:\s*', ''
            Write-Host "  SKIP: $Name -- $reason" -ForegroundColor Yellow
            return $null
        }
        Write-Host "  FAIL: $Name -- $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

function Install-LocalTestDeps {
    $root = Get-ProjectRoot
    $venvPip = Join-Path $root ".venv\Scripts\pip.exe"
    $deps = @("fastapi", "httpx", "asyncpg", "pytest", "pytest-asyncio", "sqlalchemy", "neo4j")
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    if (Test-Path $venvPip) {
        & $venvPip install -q @deps 2>&1 | Out-Null
    }
    else {
        pip install -q @deps 2>&1 | Out-Null
    }
    $ErrorActionPreference = $prev
}

function Invoke-LocalPytest {
    param([Parameter(Mandatory)][string[]]$PytestArgs)
    $root = Get-ProjectRoot
    $venvPython = Join-Path $root ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        & $venvPython -m pytest @PytestArgs
    }
    else {
        python -m pytest @PytestArgs
    }
}

if (-not (Test-Path $prodComposeFile)) {
    throw "Missing $prodComposeFile - M1 not implemented"
}

$prodApiKey = if ($env:PHASE2B_TEST_API_KEY) { $env:PHASE2B_TEST_API_KEY } else { $DefaultProdApiKey }

Write-Host "=== Phase 2b-prod Gate Validation ===" -ForegroundColor Cyan

# ------------------------------------------------------------------
# [1/7] Dev stack smoke (Phase 2a regression, before prod switch)
# ------------------------------------------------------------------
Write-Host "`n[1/8] Phase 2a smoke on dev profile..."
$health = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 15
if (-not ($health.neo4j -and $health.postgres)) {
    Write-Host "Dev stack not healthy. Run: .\scripts\validate_phase2a_gate.ps1" -ForegroundColor Yellow
    throw "Dev stack not ready"
}
Write-Host "  Dev health OK"

# ------------------------------------------------------------------
# [2/8] Dev regression tests (before prod profile replaces api env)
# ------------------------------------------------------------------
Write-Host "`n[2/8] Dev regression tests (Phase 2a + M2 cache)..."
Install-LocalTestDeps
Invoke-LocalPytest -PytestArgs @(
    "tests/unit/test_phase2a.py",
    "tests/integration/test_phase2a_ingest.py",
    "tests/unit/test_api_key.py",
    "tests/unit/test_graph_cache.py",
    "-v"
)
if ($LASTEXITCODE -ne 0) { throw "Dev regression tests failed (exit $LASTEXITCODE)" }

# ------------------------------------------------------------------
# [3/8] Switch to prod profile
# ------------------------------------------------------------------
Write-Host "`n[3/8] Starting prod profile (ALLOW_INLINE_PATIENT=0, REQUIRE_API_KEY=1)..."
Invoke-DockerCompose -ComposeFiles $composeProd -ComposeArgs @("up", "-d", "--force-recreate", "api", "nginx") | Out-Null
Start-Sleep -Seconds 35
if ((Invoke-DockerCompose -ComposeFiles $composeProd -ComposeArgs @("exec", "-T", "nginx", "nginx", "-s", "reload")) -ne 0) {
    Invoke-DockerCompose -ComposeFiles $composeProd -ComposeArgs @("restart", "nginx") | Out-Null
    Start-Sleep -Seconds 3
}
Write-Host "  Prod profile active"

# ------------------------------------------------------------------
# [4/8] Inline patient blocked in prod (M1)
# ------------------------------------------------------------------
Write-Host "`n[4/8] Inline patient blocked when ALLOW_INLINE_PATIENT=0 (M1)..."
$inlineBlocked = Test-FeatureImplemented "inline patient rejected in prod" {
    $inlineBody = '{"patient":{"demographics":{"age":52,"sex":"F","region_code":"SA-01","bmi":31.0},"conditions":[],"medications":[],"labs":[]}}'
    $status = Get-HttpStatusCode {
        Invoke-RestMethod -Uri "http://localhost/v1/recommendations" -Method Post `
            -Body $inlineBody -ContentType "application/json" `
            -Headers @{ "X-API-Key" = $prodApiKey } -TimeoutSec 30 | Out-Null
    }
    if ($status -ne 400) { throw "Expected 400, got $status" }
}

# ------------------------------------------------------------------
# [5/8] API key required (M1)
# ------------------------------------------------------------------
Write-Host "`n[5/8] API key required on /v1/* (M1)..."
$apiKeyRequired = Test-FeatureImplemented "missing API key returns 401" {
    $body = @{ patient_id = $patientId; options = @{ max_recommendations = 1 } } | ConvertTo-Json
    $status = Get-HttpStatusCode {
        Invoke-RestMethod -Uri "http://localhost/v1/recommendations" -Method Post `
            -Body $body -ContentType "application/json" -TimeoutSec 30 | Out-Null
    }
    if ($status -ne 401) { throw "Expected 401, got $status" }
}

# ------------------------------------------------------------------
# [6/8] Authenticated patient_id score via nginx (M1)
# ------------------------------------------------------------------
Write-Host "`n[6/8] Authenticated patient_id score via nginx (M1)..."
$authenticatedScore = Test-FeatureImplemented "patient_id score with API key" {
    if ((Invoke-DockerCompose -ComposeFiles $composeProd -ComposeArgs @(
            "exec", "-T", "api", "python", "scripts/seed_patient_realm.py"
        )) -ne 0) {
        throw "Patient realm seed failed"
    }
    $body = @{ patient_id = $patientId; options = @{ max_recommendations = 6 } } | ConvertTo-Json
    $rec = Invoke-RestMethod -Uri "http://localhost/v1/recommendations" -Method Post `
        -Body $body -ContentType "application/json" `
        -Headers @{ "X-API-Key" = $prodApiKey } -TimeoutSec 60
    if (-not $rec.recommendations) { throw "No recommendations returned" }
    Write-Host "    Recommendations: $($rec.recommendations.Count)"
}

# ------------------------------------------------------------------
# [7/8] M2 prod integration tests (readiness + evidence)
# ------------------------------------------------------------------
Write-Host "`n[7/8] M2 prod integration tests (readiness + evidence)..."
$readinessOk = Test-FeatureImplemented "/health/ready returns 200" {
    $ready = Invoke-RestMethod -Uri "http://localhost/health/ready" -TimeoutSec 15
    if ($ready.status -ne "ready") { throw "status=$($ready.status)" }
    if (-not ($ready.neo4j -and $ready.postgres)) { throw "dependencies not healthy" }
}
$env:PHASE2B_TEST_API_KEY = $prodApiKey
Invoke-LocalPytest -PytestArgs @(
    "tests/integration/test_phase2b_prod.py",
    "-v",
    "-k", "health_live or readiness or evidence"
)
$m2PytestExit = $LASTEXITCODE
Remove-Item Env:PHASE2B_TEST_API_KEY -ErrorAction SilentlyContinue
if ($m2PytestExit -ne 0) { throw "M2 prod integration tests failed (exit $m2PytestExit)" }
$m2EvidenceOk = $true

# ------------------------------------------------------------------
# [8/8] Restore dev profile
# ------------------------------------------------------------------
Write-Host "`n[8/8] Restoring dev profile..."
Invoke-DockerCompose -ComposeFiles @("docker-compose.yml") -ComposeArgs @("up", "-d", "--force-recreate", "api") | Out-Null
Start-Sleep -Seconds 20
Write-Host "  Dev profile restored"

# ------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------
Write-Host "`n=== Phase 2b-prod Gate Summary (M1 + M2) ===" -ForegroundColor Cyan
$m1Checks = @($inlineBlocked, $apiKeyRequired, $authenticatedScore)
$m2Checks = @($readinessOk, $m2EvidenceOk)
$implemented = @($m1Checks + $m2Checks) | Where-Object { $_ -eq $true }
$failed = @($m1Checks + $m2Checks) | Where-Object { $_ -eq $false }

Write-Host "  Passed:  $($implemented.Count) / 5 checks (3 M1 + 2 M2)"
Write-Host "  Failed:  $($failed.Count)"

if ($failed.Count -gt 0) {
    throw "Phase 2b-prod gate FAILED - fix checks above"
}

if ($implemented.Count -lt 5) {
    throw "Phase 2b-prod gate incomplete - expected 5 M1+M2 checks"
}

Write-Host "`n=== Phase 2b-prod M1+M2 gate PASSED ===" -ForegroundColor Green
Write-Host "Prod API key (dev default): $DefaultProdApiKey"
Write-Host "Override with env: PHASE2B_TEST_API_KEY"
