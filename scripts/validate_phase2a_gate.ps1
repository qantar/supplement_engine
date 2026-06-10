#!/usr/bin/env pwsh
# Phase 2a gate validation - ASCII only for Windows PowerShell
# Usage: .\scripts\validate_phase2a_gate.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

function Get-ProjectRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Invoke-DockerCompose {
    param([Parameter(Mandatory)][string[]]$ComposeArgs)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & docker compose @ComposeArgs 2>&1 | Out-Null
    $code = $LASTEXITCODE
    $ErrorActionPreference = $prev
    return $code
}

function Install-LocalTestDeps {
    $root = Get-ProjectRoot
    $venvPip = Join-Path $root ".venv\Scripts\pip.exe"
    $deps = @("fastapi", "httpx", "asyncpg", "pytest", "pytest-asyncio", "sqlalchemy")
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

Write-Host "=== Phase 2a Gate Validation ===" -ForegroundColor Cyan

Write-Host "`n[1/5] Building and starting stack..."
docker compose build api
docker compose up -d api neo4j postgres redis nginx
Start-Sleep -Seconds 35
if ((Invoke-DockerCompose -ComposeArgs @("exec", "-T", "nginx", "nginx", "-s", "reload")) -ne 0) {
    docker compose restart nginx
    Start-Sleep -Seconds 3
}

Write-Host "`n[2/5] Health check..."
$health = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 15
$health | ConvertTo-Json
if (-not ($health.neo4j -and $health.postgres)) {
    throw "Health check failed - neo4j or postgres not healthy"
}
$nginxHealth = Invoke-RestMethod -Uri "http://localhost/health" -TimeoutSec 15
if (-not ($nginxHealth.neo4j -and $nginxHealth.postgres)) {
    throw "Nginx proxy health check failed - run: docker compose restart nginx"
}

Write-Host "`n[3/5] Seeding patient realm..."
if ((Invoke-DockerCompose -ComposeArgs @("exec", "-T", "api", "python", "scripts/seed_patient_realm.py")) -ne 0) {
    throw "Patient realm seed failed"
}

Write-Host "`n[4/5] Score by patient_id (via nginx)..."
$patientId = "f47ac10b-58cc-4372-a567-0e02b2c3d479"
$body = @{ patient_id = $patientId; options = @{ max_recommendations = 6 } } | ConvertTo-Json
$rec = Invoke-RestMethod -Uri "http://localhost/v1/recommendations" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 60
if (-not $rec.recommendations) {
    throw "No recommendations returned for patient_id"
}
Write-Host "Recommendations: $($rec.recommendations.Count)"

Write-Host "`n[5/5] Delta lab append + integration tests..."
$labBody = @{
    loinc = "1989-3"
    value = 12
    unit = "ng/mL"
    reference_low = 30
    reference_high = 80
} | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost/v1/patients/$patientId/labs" -Method Post -Body $labBody -ContentType "application/json" -TimeoutSec 30

Install-LocalTestDeps
Invoke-LocalPytest -PytestArgs @(
    "tests/unit/test_phase2a.py",
    "tests/integration/test_phase2a_ingest.py",
    "-v"
)
if ($LASTEXITCODE -ne 0) { throw "Integration tests failed (exit $LASTEXITCODE)" }

Write-Host "`n=== Phase 2a gate PASSED ===" -ForegroundColor Green
