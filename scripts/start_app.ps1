# Start the supplement engine on Docker (minimum stack).
# Prerequisites: Docker Desktop running.
# Usage: .\scripts\start_app.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

Write-Host "Checking Docker..." -ForegroundColor Cyan
docker info | Out-Null

if (-not (Test-Path ".env")) {
    Write-Host "Creating .env from .env.example..."
    Copy-Item .env.example .env
}

Write-Host "Pulling images and building API (first run may take 10-20 min)..." -ForegroundColor Cyan
docker compose up -d --build api neo4j postgres redis nginx

Write-Host "Waiting for services (90s)..." -ForegroundColor Cyan
Start-Sleep -Seconds 90

Write-Host "`nContainer status:" -ForegroundColor Cyan
docker compose ps

Write-Host "`nHealth check:" -ForegroundColor Cyan
try {
    $health = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 15
    $health | ConvertTo-Json
    if (-not ($health.neo4j -and $health.postgres)) {
        Write-Host "Services still starting — wait 60s and run: Invoke-RestMethod http://localhost:8000/health" -ForegroundColor Yellow
    }
} catch {
    Write-Host "API not ready yet — check: docker compose logs api" -ForegroundColor Yellow
}

Write-Host "`nSeeding Neo4j knowledge graph..." -ForegroundColor Cyan
docker compose exec neo4j cypher-shell -u neo4j -p supplement_engine_dev `
    -f /var/lib/neo4j/import/seed.cypher

Write-Host "`n=== App ready ===" -ForegroundColor Green
Write-Host "  Swagger:  http://localhost/docs"
Write-Host "  Health:   http://localhost:8000/health"
Write-Host "  Neo4j:    http://localhost:7474  (neo4j / supplement_engine_dev)"
Write-Host "`nTest:"
Write-Host '  curl.exe -X POST http://localhost/v1/recommendations -H "Content-Type: application/json" -d "@examples/patient_t2dm_riyadh.json"'
