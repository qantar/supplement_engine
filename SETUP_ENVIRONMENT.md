# Setup Environment — Supplement Recommendation Engine

> **Full master reference:** [`ENGINE_MASTER_REFERENCE.md`](ENGINE_MASTER_REFERENCE.md) — product deliverable, APIs, Docker/DB interaction, user stories, gates, and next phases.  
> **Flowcharts:** [`ENGINE_DIAGRAMS.html`](ENGINE_DIAGRAMS.html) — open in a browser (Cursor/VS Code Markdown preview does not render Mermaid by default).

Guide for running the app locally on **Windows** with Docker Desktop.

---

## Start here (Docker is running, no images yet)

You do **not** need to download images manually. The first `docker compose up` command **pulls** images from the internet and **builds** the API image. This can take **10–20 minutes** the first time (depends on your connection).

Open **PowerShell** (built-in Windows PowerShell is fine — you do **not** need `pwsh`).

### Step 1 — Go to the project folder

```powershell
cd C:\Users\tawakal\Documents\learn\practical\D-Framework\personalised-nutritionist\supplement_engine
```

### Step 2 — Confirm Docker works

```powershell
docker info
```

If this errors, open **Docker Desktop** from the Start menu and wait until it says **Running**, then try again.

### Step 3 — Create config file (once)

```powershell
Copy-Item .env.example .env
```

Defaults are fine for local dev — no edits required.

### Step 4 — Pull images, build API, start the app

**Minimum stack** (recommended first time — API + databases + proxy only):

```powershell
docker compose up -d --build api neo4j postgres redis nginx
```

What happens on first run:

| Action | What gets downloaded/built |
|--------|----------------------------|
| **Pull** | `neo4j:5.20-community`, `postgres:16-alpine`, `redis:7-alpine`, `nginx:1.25-alpine` |
| **Build** | `supplement_engine-api` from `infra/docker/Dockerfile.api` (installs Python deps, runs migrations on start) |

Wait **2–3 minutes**, then check:

```powershell
docker compose ps
```

You want these **healthy** or **running**:

- `supplement_api`
- `supplement_neo4j`
- `supplement_postgres`
- `supplement_redis`
- `supplement_nginx`

If `supplement_api` is still `starting`, wait another minute (Neo4j can take ~60s on first boot).

### Step 5 — Health check

```powershell
Invoke-RestMethod http://localhost:8000/health | ConvertTo-Json
```

Expected:

```json
{ "status": "ok", "neo4j": true, "postgres": true }
```

If `neo4j` is `false`, wait 60 seconds and run again:

```powershell
Start-Sleep -Seconds 60
Invoke-RestMethod http://localhost:8000/health | ConvertTo-Json
```

### Step 6 — Seed the knowledge graph (required once)

Neo4j starts empty. Load clinical data (nutrients, conditions, drug edges):

```powershell
docker compose exec neo4j cypher-shell -u neo4j -p supplement_engine_dev -f /var/lib/neo4j/import/seed.cypher
```

Last line should include something like `"Seed complete"`.

### Step 7 — Run your first recommendation

```powershell
curl.exe -X POST http://localhost/v1/recommendations -H "Content-Type: application/json" -d "@examples/patient_t2dm_riyadh.json"
```

Or open in browser:

- **Swagger UI:** http://localhost/docs
- **Neo4j Browser:** http://localhost:7474 (login: `neo4j` / `supplement_engine_dev`)

**You are done.** The app is running on Docker.

---

## Optional — start Kafka & Airflow (not needed for recommendations)

Only if you want the full compose file:

```powershell
docker compose up -d
```

Adds Zookeeper, Kafka, and Airflow (extra images, slower first pull). **Not required** for Phase 1 API usage.

---

## Optional — run Phase 1 validation script

Requires **Python 3.12** on your PC (for integration tests only — the app itself runs in Docker).

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install httpx pytest pytest-asyncio
```

Then (with Docker still running):

```powershell
.\scripts\validate_phase1_gate.ps1
```

If script execution is blocked:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\validate_phase1_gate.ps1
```

This rebuilds, seeds Neo4j, and runs 6 integration tests.

---

## Daily commands

```powershell
# Start (after reboot)
cd C:\Users\tawakal\Documents\learn\practical\D-Framework\personalised-nutritionist\supplement_engine
docker compose up -d api neo4j postgres redis nginx

# Stop
docker compose down

# View API logs
docker compose logs -f api

# List images you have
docker images

# List running containers
docker compose ps
```

---

## What runs where

| Service | URL | Purpose |
|---------|-----|---------|
| API (direct) | http://localhost:8000 | FastAPI + `/health`, `/docs` |
| API (via Nginx) | http://localhost | Same API on port 80 |
| Neo4j Browser | http://localhost:7474 | Knowledge graph UI |
| Postgres | localhost:5432 | DB (user `supplement`, password `devpassword`) |
| Redis | localhost:6379 | Cache |

---

## Prerequisites (install once)

Skip any step you already have.

| # | Software | Required for | Install |
|---|----------|--------------|---------|
| 1 | **Docker Desktop** | Running the app | https://www.docker.com/products/docker-desktop/ |
| 2 | **WSL 2** | Docker on Windows | Admin PowerShell: `wsl --install` then reboot |
| 3 | **Python 3.12** | Integration tests only | https://www.python.org/downloads/ — tick **Add to PATH** |
| 4 | **Git** | Optional | https://git-scm.com/download/win |

**Not required:** PowerShell 7 (`pwsh`), local Postgres/Neo4j/Redis installs.

### Verify installs

```powershell
docker --version
docker compose version
docker info
python --version   # only if running tests locally
```

### Docker Desktop settings (recommended)

- **Settings → Resources → Memory:** 6 GB minimum
- **Settings → Resources → CPUs:** 4 minimum

---

## Environment variables (`.env`)

```powershell
Copy-Item .env.example .env
```

| Variable | Default | Notes |
|----------|---------|-------|
| `NEO4J_PASSWORD` | `supplement_engine_dev` | Must match seed/cypher-shell |
| `POSTGRES_PASSWORD` | `devpassword` | Postgres container |

---

## Troubleshooting

### `docker info` fails / `dockerDesktopLinuxEngine` not found

Start **Docker Desktop** from the Start menu. Wait until the tray icon shows **Running**.

### First `docker compose up` is very slow

Normal. Docker is downloading several GB of images. Watch progress:

```powershell
docker compose pull neo4j postgres redis nginx
docker compose build api
docker compose up -d api neo4j postgres redis nginx
```

### Health check: `neo4j: false`

```powershell
docker compose logs neo4j
Start-Sleep -Seconds 60
Invoke-RestMethod http://localhost:8000/health
```

### Port already in use

| Port | Service | Fix |
|------|---------|-----|
| 8000 | API | Stop other app using 8000 |
| 80 | Nginx | Stop IIS or other web server |
| 5432 | Postgres | Stop local PostgreSQL Windows service |

### Neo4j seed fails

Test connection:

```powershell
docker compose exec neo4j cypher-shell -u neo4j -p supplement_engine_dev "RETURN 1"
```

### Recommendations return empty or errors

You probably skipped **Step 6 (seed)**. Re-run the seed command.

### Reset everything (fresh DB + Neo4j)

```powershell
docker compose down -v
docker compose up -d --build api neo4j postgres redis nginx
# wait 2 min, then seed Neo4j again (Step 6)
```

### `pip install -r requirements.txt` fails on Windows (`uvloop`)

Expected on Windows. The app runs **inside Docker** — you don't need full requirements on the host unless running tests. Minimum for tests:

```powershell
pip install httpx pytest pytest-asyncio
```

---

## Production pilot profile (Phase 2b)

Dev stack (default):

```powershell
docker compose up -d api neo4j postgres redis nginx
```

Production pilot overlay (`ALLOW_INLINE_PATIENT=0`, `REQUIRE_API_KEY=1`):

```powershell
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build api nginx
```

After rebuilding the API image, reload nginx so upstream DNS picks up the new container:

```powershell
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec nginx nginx -s reload
```

### API key header

All `/v1/*` routes require `X-API-Key` in prod. Default pilot key (change before real deployment):

```powershell
$headers = @{ "X-API-Key" = "pilot-dev-key-change-me"; "Content-Type" = "application/json" }
$body = @{ patient_id = "f47ac10b-58cc-4372-a567-0e02b2c3d479"; options = @{ max_recommendations = 6 } } | ConvertTo-Json
Invoke-RestMethod -Uri http://localhost/v1/recommendations -Method Post -Headers $headers -Body $body
```

Health probes (`/health/live`, `/health/ready`) and `/docs` are exempt from API key auth.

### Readiness for orchestrators

| Endpoint | Use |
|----------|-----|
| `GET /health/live` | Liveness — process running |
| `GET /health/ready` | Readiness — Neo4j + Postgres up (503 if not) |

### Audit retention

Recommendation audit rows are append-only. See `scripts/postgres_init.sql` for the 7-year retention policy on audit tables.

### Validate prod gate

```powershell
.\scripts\validate_phase2b_prod_gate.ps1
```

Restores dev profile automatically after M1+M2 checks.

### Pilot cohort gate

Seed all 7 clinical personas and score via prod profile:

```powershell
.\scripts\validate_phase2b_pilot_gate.ps1
```

### Clinical review checklist (manual)

Before demo or external pilot, review each seed patient:

| Check | Pass criteria |
|-------|----------------|
| Recommendations clinically plausible | Top 3 recs match condition/lab profile |
| Safety blocks | Hemochromatosis patient has **no iron** in recs or suppressed with reason |
| `requires_clinician` | Escalation fires when expected (polypharmacy / high-risk combos) |
| Rationale | Each rec has non-empty `why` / `evidence` / `safety` |
| Audit trail | `GET /v1/audit/{session_id}` returns `input_hash`; evidence snapshot has `content_hash` |
| No PHI in logs | API logs show `patient_id_hash` only, never raw UUID in clear text as MRN |

### Phase 2c gates (Kafka + personalization)

```powershell
# Kafka producers (KAFKA_ENABLED=1 in prod overlay)
.\scripts\validate_phase2c_m1_gate.ps1

# PersonalizationEngine (set PERSONALIZATION_ENABLED=1 for gate run)
.\scripts\validate_phase2c_m2_gate.ps1
```

| Variable | Default | Purpose |
|----------|---------|---------|
| `KAFKA_ENABLED` | `0` dev / `1` prod overlay | Emit `patient.events` + `recommendation.served` |
| `PERSONALIZATION_ENABLED` | `0` | Blend prior session `drs_snapshot` into DRS (Stage 1b) |

### External bulk feeder (production data)

Bulk patient backfill is **not implemented in this repo**. Your separate project writes directly to Postgres tables documented in `etl/PATIENT_REALM_CONTRACT.md`. This engine:

- Does **not** run warehouse ETL or dbt in production  
- Does **not** need to know when a bulk load happened  
- Scores any patient whose rows exist when you call `POST /v1/recommendations { patient_id }`

Use `scripts/seed_patient_realm.py` only for local pilot when the external feeder is not running.

---

## Technology versions

```
Python (API container)  3.12
FastAPI                 0.111.0
Neo4j                   5.20-community
PostgreSQL              16-alpine
Redis                   7-alpine
Nginx                   1.25-alpine
```

See `requirements.txt` and `docker-compose.yml` for full pinned versions.
