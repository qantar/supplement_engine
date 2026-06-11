# Start the Supplement Engine — delegates to the unified orchestrator.
# Usage:
#   .\scripts\start_app.ps1
#   .\scripts\start_app.ps1 -Open
#   .\scripts\start_app.ps1 -Command seed -All
#   .\scripts\start_app.ps1 -Command status
#   .\scripts\start_app.ps1 -BackendOnly

param(
    [ValidateSet("up", "down", "seed", "status", "smoke", "restart")]
    [string]$Command = "up",
    [switch]$Open,
    [switch]$Prod,
    [switch]$BackendOnly,
    [switch]$FrontendOnly,
    [switch]$NoSeed,
    [switch]$NoBuild,
    [switch]$NoSmoke,
    [switch]$All,
    [switch]$Neo4j,
    [switch]$Patients,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

$python = $null
foreach ($candidate in @("python", "py", "python3")) {
    if (Get-Command $candidate -ErrorAction SilentlyContinue) {
        $python = $candidate
        break
    }
}

if (-not $python) {
    Write-Host "Python not found. Install Python 3.10+." -ForegroundColor Red
    exit 1
}

$args = @("$PSScriptRoot\run_app.py", $Command)
if ($Open) { $args += "--open" }
if ($Prod) { $args += "--prod" }
if ($BackendOnly) { $args += "--backend-only" }
if ($FrontendOnly) { $args += "--frontend-only" }
if ($NoSeed) { $args += "--no-seed" }
if ($NoBuild) { $args += "--no-build" }
if ($NoSmoke) { $args += "--no-smoke" }
if ($All) { $args += "--all" }
if ($Neo4j) { $args += "--neo4j" }
if ($Patients) { $args += "--patients" }
if ($Force) { $args += "--force" }

& $python @args
exit $LASTEXITCODE
