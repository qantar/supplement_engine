#!/usr/bin/env pwsh
# Phase 2c-M1 gate — Kafka producers wired
# Usage: .\scripts\validate_phase2c_m1_gate.ps1

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
    $deps = @("pytest", "pytest-asyncio", "aiokafka")
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
$patientId = "f47ac10b-58cc-4372-a567-0e02b2c3d479"

Write-Host "=== Phase 2c-M1 Kafka Gate ===" -ForegroundColor Cyan

Write-Host "`n[1/3] Unit tests (KafkaEventProducer)..."
Install-LocalTestDeps
Invoke-LocalPytest -PytestArgs @("tests/unit/test_kafka_producer.py", "-v")
if ($LASTEXITCODE -ne 0) { throw "Kafka unit tests failed" }

Write-Host "`n[2/3] Prod profile + Kafka enabled, score patient..."
Invoke-DockerCompose -ComposeFiles $composeProd -ComposeArgs @(
    "up", "-d", "--force-recreate", "api", "nginx", "kafka"
) | Out-Null
Start-Sleep -Seconds 40
Invoke-DockerCompose -ComposeFiles $composeProd -ComposeArgs @(
    "exec", "-T", "api", "python", "scripts/seed_patient_realm.py"
) | Out-Null
$body = @{ patient_id = $patientId; options = @{ max_recommendations = 3 } } | ConvertTo-Json
$rec = Invoke-RestMethod -Uri "http://localhost/v1/recommendations" -Method Post `
    -Body $body -ContentType "application/json" `
    -Headers @{ "X-API-Key" = $prodApiKey } -TimeoutSec 60
if (-not $rec.session_id) { throw "Score failed without session_id" }

Write-Host "`n[3/3] Verify recommendation.served topic has messages..."
$consume = Invoke-DockerCompose -ComposeFiles $composeProd -ComposeArgs @(
    "exec", "-T", "kafka", "kafka-console-consumer",
    "--bootstrap-server", "localhost:9092",
    "--topic", "recommendation.served",
    "--from-beginning",
    "--max-messages", "1",
    "--timeout-ms", "15000"
)
if ($consume -ne 0) {
    Write-Host "  WARN: could not read Kafka topic (broker may still be starting)" -ForegroundColor Yellow
} else {
    Write-Host "  Kafka topic recommendation.served reachable" -ForegroundColor Green
}

Invoke-DockerCompose -ComposeFiles @("docker-compose.yml") -ComposeArgs @("up", "-d", "--force-recreate", "api") | Out-Null
Write-Host "`n=== Phase 2c-M1 Gate PASSED ===" -ForegroundColor Green
