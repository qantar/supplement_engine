#!/usr/bin/env pwsh
# Phase 1 gate validation — run with Docker Desktop started.
# Usage: .\scripts\validate_phase1_gate.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

Write-Host "=== Phase 1 Gate Validation ===" -ForegroundColor Cyan

Write-Host "`n[1/4] Building and starting stack..."
docker compose build api
docker compose up -d
Start-Sleep -Seconds 30
docker compose ps

Write-Host "`n[2/4] Health check..."
$health = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 10
$health | ConvertTo-Json
if (-not ($health.neo4j -and $health.postgres)) {
    throw "Health check failed — neo4j or postgres not healthy"
}

Write-Host "`n[3/4] Seeding Neo4j (KG v1.1.0)..."
docker compose exec neo4j cypher-shell -u neo4j -p supplement_engine_dev `
    -f /var/lib/neo4j/import/seed.cypher

Write-Host "`n[4/4] Running integration tests..."
pip install -q httpx asyncpg
pytest tests/integration/ -v -m integration

Write-Host "`n=== Phase 1 gate PASSED ===" -ForegroundColor Green
