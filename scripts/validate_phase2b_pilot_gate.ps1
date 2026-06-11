#!/usr/bin/env pwsh
# Phase 2b pilot gate — multi-patient prod scoring + clinical sanity hooks
# Prerequisite: validate_phase2b_prod_gate.ps1 should pass first.
# Usage: .\scripts\validate_phase2b_pilot_gate.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

$DefaultProdApiKey = "pilot-dev-key-change-me"
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

function Install-LocalTestDeps {
    $root = Get-ProjectRoot
    $venvPip = Join-Path $root ".venv\Scripts\pip.exe"
    $deps = @("fastapi", "httpx", "asyncpg", "pytest", "pytest-asyncio", "sqlalchemy", "neo4j")
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    if (Test-Path $venvPip) {
        & $venvPip install -q @deps 2>&1 | Out-Null
    } else {
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
    } else {
        python -m pytest @PytestArgs
    }
}

$prodApiKey = if ($env:PHASE2B_TEST_API_KEY) { $env:PHASE2B_TEST_API_KEY } else { $DefaultProdApiKey }

Write-Host "=== Phase 2b Pilot Gate ===" -ForegroundColor Cyan

Write-Host "`n[1/4] Starting prod profile + Kafka..."
Invoke-DockerCompose -ComposeFiles $composeProd -ComposeArgs @("up", "-d", "--force-recreate", "api", "nginx", "kafka") | Out-Null
Start-Sleep -Seconds 40
if ((Invoke-DockerCompose -ComposeFiles $composeProd -ComposeArgs @("exec", "-T", "nginx", "nginx", "-s", "reload")) -ne 0) {
    Invoke-DockerCompose -ComposeFiles $composeProd -ComposeArgs @("restart", "nginx") | Out-Null
    Start-Sleep -Seconds 3
}

Write-Host "`n[2/4] Seed pilot cohort..."
if ((Invoke-DockerCompose -ComposeFiles $composeProd -ComposeArgs @(
        "exec", "-T", "api", "python", "scripts/seed_patient_realm.py"
    )) -ne 0) {
    throw "Pilot cohort seed failed"
}

Write-Host "`n[3/4] Pilot cohort integration tests (prod profile)..."
Install-LocalTestDeps
$env:PHASE2B_TEST_API_KEY = $prodApiKey
Invoke-LocalPytest -PytestArgs @(
    "tests/integration/test_pilot_cohort.py",
    "-v",
    "-k", "test_pilot_patient_scores or test_hemochromatosis"
)
if ($LASTEXITCODE -ne 0) { throw "Pilot cohort tests failed (exit $LASTEXITCODE)" }
Remove-Item Env:PHASE2B_TEST_API_KEY -ErrorAction SilentlyContinue

Write-Host "`n[4/4] Restoring dev profile..."
Invoke-DockerCompose -ComposeFiles @("docker-compose.yml") -ComposeArgs @("up", "-d", "--force-recreate", "api") | Out-Null
Start-Sleep -Seconds 15

Write-Host "`n=== Phase 2b Pilot Gate PASSED ===" -ForegroundColor Green
Write-Host "Complete clinical review checklist in examples/pilot/README.md."
