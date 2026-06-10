#!/usr/bin/env pwsh
# Phase 2c-M2 gate — PersonalizationEngine + drs_snapshot
# Usage: .\scripts\validate_phase2c_m2_gate.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

$DefaultProdApiKey = "pilot-dev-key-change-me"
$composeProd = @("docker-compose.yml", "docker-compose.prod.yml")

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
    return $LASTEXITCODE
}

function Install-LocalTestDeps {
    $root = Get-ProjectRoot
    $venvPip = Join-Path $root ".venv\Scripts\pip.exe"
    $deps = @("httpx", "pytest", "pytest-asyncio", "neo4j", "sqlalchemy", "asyncpg")
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

Write-Host "=== Phase 2c-M2 Personalization Gate ===" -ForegroundColor Cyan

Write-Host "`n[1/3] Unit tests..."
Install-LocalTestDeps
Invoke-LocalPytest -PytestArgs @("tests/unit/test_personalization.py", "-v")
if ($LASTEXITCODE -ne 0) { throw "Personalization unit tests failed" }

Write-Host "`n[2/3] Prod profile with PERSONALIZATION_ENABLED=1..."
$env:PERSONALIZATION_ENABLED = "1"
Invoke-DockerCompose -ComposeFiles $composeProd -ComposeArgs @("up", "-d", "--force-recreate", "api", "nginx") | Out-Null
Start-Sleep -Seconds 25
if ((Invoke-DockerCompose -ComposeFiles $composeProd -ComposeArgs @("exec", "-T", "nginx", "nginx", "-s", "reload")) -ne 0) {
    Invoke-DockerCompose -ComposeFiles $composeProd -ComposeArgs @("restart", "nginx") | Out-Null
    Start-Sleep -Seconds 3
}
Invoke-DockerCompose -ComposeFiles $composeProd -ComposeArgs @(
    "exec", "-T", "api", "python", "scripts/seed_patient_realm.py"
) | Out-Null

Write-Host "`n[3/3] Integration: two sequential scores store drs_snapshot..."
$env:PHASE2B_TEST_API_KEY = $prodApiKey
$env:PERSONALIZATION_ENABLED = "1"
Invoke-LocalPytest -PytestArgs @(
    "tests/integration/test_pilot_cohort.py",
    "-v",
    "-k", "personalization_second_session"
)
if ($LASTEXITCODE -ne 0) { throw "Personalization integration test failed" }

Remove-Item Env:PHASE2B_TEST_API_KEY -ErrorAction SilentlyContinue
Remove-Item Env:PERSONALIZATION_ENABLED -ErrorAction SilentlyContinue
Invoke-DockerCompose -ComposeFiles @("docker-compose.yml") -ComposeArgs @("up", "-d", "--force-recreate", "api") | Out-Null

Write-Host "`n=== Phase 2c-M2 Gate PASSED ===" -ForegroundColor Green
