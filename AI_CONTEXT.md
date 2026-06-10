# Supplement Recommendation Engine — Full AI Context Document

> **Purpose of this file:** Give any AI assistant complete project context to continue development without re-explaining decisions already made. Read this before writing any code, asking any questions, or making any architectural suggestions.
>
> **Human master reference:** [`ENGINE_MASTER_REFERENCE.md`](ENGINE_MASTER_REFERENCE.md) — setup, operations, API catalog, user stories, validation gates, and roadmap.  
> **Diagrams (browser):** [`ENGINE_DIAGRAMS.html`](ENGINE_DIAGRAMS.html) — Mermaid flowcharts if your Markdown preview does not render them.

---

## 1. What This System Is

A **production-grade personalized supplement recommendation engine** — a hybrid symbolic-statistical clinical decision support system (CDSS-adjacent) that maps a patient's full profile into evidence-ranked nutraceutical recommendations with a deterministic safety gate.

**Regulatory positioning:** Wellness/lifestyle advisory by default. Architecturally structured for promotion to SFDA SaMD (Saudi Food and Drug Authority), FDA SaMD Class I/II, or EU MDR without re-architecture. Primary deployment region: Kingdom of Saudi Arabia (KSA).

**Not a chatbot. Not a RAG system.** This is a clinical scoring pipeline with:
- Bayesian log-odds accumulation for deficiency risk
- A Neo4j knowledge graph for clinical evidence (nutrients, conditions, drugs, LR-weighted edges)
- A deterministic safety gate (no ML) for contraindication enforcement
- PostgreSQL for patient PHI, recommendations, audit trail
- Full explainability trace from scoring contributors to rendered rationale

---

## 2. Definitive Architecture Decisions (Non-Negotiable)

These were debated and resolved. Do not re-open them.

### Two databases. Always.

| Database | Owns | Why |
|---|---|---|
| **Neo4j** | Clinical knowledge graph — nutrients, conditions, drugs, evidence, LR-weighted edges, guidelines, demographic priors | Multi-hop graph traversal, relationship-weighted reasoning, future genomics/pathway integration |
| **PostgreSQL** | Patient PHI, recommendations, sessions, audit log, feedback, model versions | ACID, row-level security, column encryption, regulatory audit, PITR, HIPAA/GDPR/PDPL compliance |

Neo4j and Postgres are linked by string keys (`icd10_code`, `rxnorm_cui`, `nutrient_id`, `loinc`) through the application layer only. No direct DB-to-DB connection ever.

### Domain models are frozen dataclasses. Always.

```python
@dataclass(frozen=True)
class PatientProfile: ...
```

Never dicts, never raw DataFrames, never ORM objects passed to business logic. The domain models in `src/shared/models.py` are the single typed contract between every service. ORM objects (`src/db/orm_models.py`) exist only inside repository methods.

### All Cypher stays in `GraphClient`. All SQL stays in repositories.

The pipeline, safety engine, and scoring logic never write a query. They call typed methods that return typed domain objects.

### The safety engine is deterministic. No ML. Ever.

`SafetyEngine` is pure functions over typed inputs. Certifiable. Auditable. ML can suggest dose adjustments constrained to ±30% of the rules output (Phase 3) but never overrides hard blocks or UL.

### Patient bulk load is external. This repo reads Postgres only.

| Path | Owner | Engine behavior |
|---|---|---|
| **Bulk backfill** into `patients` / child tables | Separate feeder project | Engine does not run ETL, dbt, or warehouse joins |
| **Realtime deltas** (labs, meds, conditions) | This API (`/v1/patients/...`) | Writes same tables; optional Kafka events |
| **Scoring** | `POST /v1/recommendations { patient_id }` | `PatientRepository.get_for_scoring()` only |

Contract for table columns and read rules: `etl/PATIENT_REALM_CONTRACT.md`. The `etl/` dbt folder is mock/dev reference only.

---

## 3. Current Codebase State

### File Map

```
supplement_engine/
├── src/
│   ├── shared/
│   │   └── models.py              ← Domain models (frozen dataclasses). 234 lines.
│   │                                Single source of truth for all typed contracts.
│   ├── knowledge/
│   │   └── graph_client.py        ← Neo4j async interface. 323 lines.
│   │                                ALL Cypher lives here. Returns typed domain objects.
│   │                                Methods: get_baseline_prevalence, get_condition_edges,
│   │                                get_depletion_edges, get_interaction_edges,
│   │                                get_antagonist_pairs, get_contraindications,
│   │                                get_guideline, get_nutrient_meta, get_all_nutrient_ids
│   ├── core/
│   │   ├── deficiency_risk_scorer.py  ← Bayesian DRS engine. 296 lines.
│   │   │                               Log-odds accumulation in 7 stages.
│   │   │                               asyncio.gather for concurrent per-nutrient scoring.
│   │   │                               Lab override: 80% weight collapses prior.
│   │   └── candidate_generator.py     ← Three classes. 269 lines.
│   │                                   CandidateGenerator: DRS threshold + guideline trigger
│   │                                   DoseOptimizer: RDA × risk × bio × UL cap
│   │                                   ConfidenceCompositor: C = 0.40·E + 0.15·D + 0.15·S + 0.10·P + 0.10·M + 0.10·Bayes
│   ├── safety/
│   │   └── safety_engine.py       ← Deterministic safety gate. 336 lines.
│   │                                Runs AFTER recommender. Order: drug-nutrient →
│   │                                disease CI → nutrient-nutrient → UL → escalation.
│   │                                Returns FilterResult with surviving/blocked/escalate.
│   ├── explain/
│   │   └── explain_service.py     ← Three-layer rationale. 282 lines.
│   │                                why / evidence / safety — slot-fill from DRS trace.
│   │                                Phase 2: optional Claude API polish with fact validation.
│   ├── db/
│   │   ├── engine.py              ← Async SQLAlchemy engine + session factory. 98 lines.
│   │   │                           init_db() at startup, get_session_dep() per request.
│   │   │                           NullPool for testing, persistent pool for production.
│   │   ├── orm_models.py          ← SQLAlchemy 2.0 ORM models. 259 lines.
│   │   │                           Mirrors postgres_init.sql exactly.
│   │   │                           Never imported by business logic — only by repositories.
│   │   └── repositories.py        ← All Postgres reads/writes. 550 lines.
│   │                               PatientRepository, RecommendationRepository,
│   │                               FeedbackRepository, AuditRepository,
│   │                               EvidenceSnapshotRepository, ModelVersionRepository.
│   │                               Each takes/returns domain objects, never ORM objects.
│   ├── pipelines/
│   │   └── recommendation_pipeline.py  ← End-to-end orchestrator. 206 lines.
│   │                                    Stateless — safe for concurrent requests.
│   │                                    7 stages: DRS → candidates → dose → safety →
│   │                                    confidence → explain → assemble.
│   │                                    Does NOT persist — app.py repositories handle that.
│   └── api/
│       └── app.py                 ← FastAPI application. 415 lines.
│                                   Lifespan: Neo4j + Postgres init/close.
│                                   Per-request: upsert patient → save session → audit log.
│                                   Endpoints: POST /v1/recommendations,
│                                   GET /v1/sessions/{id},
│                                   GET /v1/patients/{id}/history,
│                                   POST /v1/feedback,
│                                   GET /v1/audit/{session_id},
│                                   GET /v1/safety/check,
│                                   GET /v1/nutrients/{id},
│                                   GET /health
├── scripts/
│   ├── neo4j_seed.cypher          ← KG schema + clinical data. 284 lines.
│   │                               Nutrients, conditions, medications seeded.
│   │                               Edges: INCREASES_DEMAND_FOR, CAUSES_MALABSORPTION_OF,
│   │                               DEPLETES, INTERACTS_WITH, ANTAGONIZES, SYNERGIZES_WITH,
│   │                               HAS_BASELINE_RISK, RECOMMENDS.
│   │                               KSA-specific demographic priors seeded.
│   └── postgres_init.sql          ← Full schema. 212 lines.
│                                   Tables: patients, patient_conditions, patient_medications,
│                                   patient_labs, recommendation_sessions, recommendations,
│                                   recommendation_warnings, rec_feedback, audit_log,
│                                   evidence_snapshots, model_versions.
│                                   Immutability rules: recommendations + audit_log
│                                   have DB-level UPDATE/DELETE prevention.
├── tests/unit/test_core.py        ← 18 unit tests. 297 lines.
│                                   All Neo4j calls mocked (AsyncMock).
│                                   Tests: math helpers, DRS scoring, safety engine,
│                                   confidence compositor.
├── infra/
│   ├── docker/Dockerfile.api      ← Multi-stage build. Non-root user. 4 uvicorn workers.
│   └── nginx/nginx.conf           ← Rate limiting (100 req/min), security headers, upstream.
└── docker-compose.yml             ← Full stack: API + Neo4j + PostgreSQL + Redis +
                                    Kafka + Nginx + Airflow. Health checks on all services.
```

### What Is 100% Done

- Domain model layer (`shared/models.py`) — all enums, frozen dataclasses, domain objects
- Neo4j knowledge graph client — all Cypher queries, typed returns, async
- Bayesian DRS scorer — full 7-stage log-odds accumulation with concurrent scoring
- Candidate generator, dose optimizer, confidence compositor
- Safety engine — 4-tier drug interaction, disease CI, UL enforcement, escalation
- Explain service — three-layer template rationale (why/evidence/safety)
- Recommendation pipeline — 7-stage stateless orchestrator
- Database layer — engine, ORM models, all 6 repositories
- FastAPI app — full wiring, all endpoints, Postgres persistence on every request
- Neo4j seed — 30+ nutrients, 16 conditions, 20+ medications, KGMetadata v1.1.0, YAML registry
- Postgres schema — all tables, indexes, immutability rules + Alembic migrations
- Docker stack — all 7 services with health checks; entrypoint runs `alembic upgrade head`
- Redis caching wired into GraphClient (nutrient/baseline/guideline TTL keys)
- Evidence snapshots — real KG version + stats hash, persisted to `evidence_snapshots`
- Alembic — initial migration in `alembic/versions/001_initial_schema.py`
- Integration tests — 6 e2e scenarios in `tests/integration/` (require running stack)
- 27 unit tests with mocked KG
- Example patient payload — `examples/patient_t2dm_riyadh.json`
- Phase 1 gate script — `scripts/validate_phase1_gate.ps1`

### What Is Stubbed / Incomplete

| Item | Location | Status |
|---|---|---|
| Airflow DAGs (evidence/retraining) | `src/pipelines/dags/` | Placeholder only — not required for core scoring |
| FHIR lab parser | Not built | `POST /v1/labs/parse` — only if LIS integration is next |
| LLM explain polish | `explain_service.py:llm_polish()` | Method exists, Anthropic client not injected |
| Analytics mart | BRD optional | `fact_recommendations` from Postgres audit — not warehouse |

### Phase 1 Exit Criteria (code complete — run gate to sign off)

Run `scripts/validate_phase1_gate.ps1` (requires Docker Desktop):

- [x] Alembic + Docker entrypoint configured
- [x] Redis cache active with graceful fallback
- [x] Evidence snapshots persisted via `EvidenceSnapshotRepository`
- [x] Active `model_version` loaded from DB
- [x] Integration test suite (6 scenarios) written
- [x] Neo4j seed v1.1.0 with 8+ condition edge sets
- [x] `/health` probes Neo4j + Postgres
- [x] 27 unit tests covering all pipeline stages
- [ ] `docker compose up` + integration tests pass on your machine (run gate script)

---

## 4. Scoring Algorithm — Full Detail

### Deficiency Risk Score (DRS)

The posterior probability of clinically relevant nutrient insufficiency:

```
logit(P_deficient) = logit(baseline_prevalence)
                   + log(geo_modifier)          # KSA: Vit D ×2.2, iodine ×0.8
                   + log(bmi_modifier)          # fat-soluble vitamins, BMI ≥ 30: ×1.5
                   + Σ log(lifestyle_LR_i)      # indoor, vegan, sun exposure, etc.
                   + Σ log(condition_edge.lr)   # INCREASES_DEMAND_FOR, MALABSORPTION
                   + Σ log(drug_edge.lr × duration_factor)  # DEPLETES × months_on/onset_months
                   [if lab present]:
                   = logit_p × 0.2 + log(lab_LR) × 0.8  # lab dominates
```

`P_deficient = sigmoid(logit_P_deficient)` ∈ [0, 1]

Duration factor: `min(1.0, months_on / onset_months)` — new prescription gets near-zero depletion LR

Lab LR: below reference_low → LR up to 10.0; above reference_high → LR 0.1; flagged → LR 8.0

### Confidence Score

```
C = 0.40·E + 0.15·D + 0.15·S + 0.10·P + 0.10·M + 0.10·Bayes

E = evidence weight from GRADE tier (A=0.95, B=0.75, C=0.55, D=0.20)
D = directness (KSA/Gulf patient + KSA cohort data → 0.85, other → 0.60)
S = consistency (unique source types in contributors, capped at 1.0)
P = precision (lab-dominated → 0.8, otherwise → 0.4)
M = mechanism plausibility (depletion/malabsorption mechanism known → 0.8)
Bayes = individual evidence (lab-dominated → 1.0, else min(p_deficient, 0.9))
```

Grade bins: A ≥ 0.80, B ≥ 0.60, C ≥ 0.40, D < 0.40

### Rank Score

```
Rank = P_deficient × Confidence × I_safety
I_safety ∈ {0, 1}  — hard block kills the candidate entirely
```

### Dose Optimization Priority

1. Pregnancy/lactation guideline override (ACOG/WHO hardcoded)
2. KG guideline dose (CPG-specified, from Neo4j)
3. DRS-adjusted RDA: P > 0.90 → ×2.0, P > 0.70 → ×1.5, else ×1.0
4. Bioavailability correction: ÷ bioavailability_factor
5. BMI adjustment: fat-soluble vitamins + BMI ≥ 30 → ×1.5
6. UL cap: min(dose, 0.70 × UL). Hard block if dose > UL.

---

## 5. Data Model Boundaries

### Neo4j Owns (clinical knowledge — semi-static)

- `Nutrient` nodes: nutrient_id, name, form, rda, ear, ul, dose_unit, bioavailability_factor, loinc_codes
- `Condition` nodes: icd10_code, snomed_id, name
- `Medication` nodes: rxnorm_cui, atc_code, name
- `Evidence` nodes: doi_pmid, study_type, n, effect_size, grade_weight, year
- `Guideline` nodes: issuing_body, version, strength
- `Demographic` nodes: bucket_id, region_code, sex, age_group
- All relationships with LR weights, mechanisms, onset_months, severity

### PostgreSQL Owns (patient data — dynamic, PHI, audited)

- `patients` — demographic snapshot (no raw DOB, hashed MRN)
- `patient_conditions` — ICD-10 codes per patient
- `patient_medications` — RxNorm per patient + months_on
- `patient_labs` — LOINC values per patient
- `recommendation_sessions` — one per pipeline run
- `recommendations` — immutable, one per nutrient per session
- `recommendation_warnings` — interaction warnings per recommendation
- `rec_feedback` — clinician/user feedback → retraining signal
- `audit_log` — append-only, SHA-256 input hash, 7-year retention
- `evidence_snapshots` — KG state captured at serve time
- `model_versions` — shadow/active/retired lifecycle

### The Join Pattern

```python
# Patient profile loaded from Postgres (patient_conditions.icd10_code = "E11.9")
#                                    ↓ application layer only
# Neo4j: MATCH (c:Condition {icd10_code: "E11.9"})-[r:INCREASES_DEMAND_FOR]->(n:Nutrient)
# No foreign key constraint. icd10_code is the shared vocabulary key.
```

---

## 6. Key Implementation Patterns

Always follow these. They are established throughout the codebase.

### Pattern 1: Repositories for all DB access

```python
# ✅ Correct
async with get_session() as session:
    repo = PatientRepository(session)
    await repo.upsert(patient)

# ❌ Never do this
session.execute(text("INSERT INTO patients ..."))
```

### Pattern 2: GraphClient for all KG access

```python
# ✅ Correct
edges = await self._kg.get_condition_edges("E11.9", "vitamin_d3")

# ❌ Never do this
async with driver.session() as s:
    result = await s.run("MATCH ...")
```

### Pattern 3: Concurrent async with asyncio.gather

```python
# ✅ Correct — scores all nutrients concurrently
tasks = [self.score(patient, nid) for nid in nutrient_ids]
results = await asyncio.gather(*tasks, return_exceptions=True)

# ❌ Never sequential in an async context
for nid in nutrient_ids:
    result = await self.score(patient, nid)
```

### Pattern 4: Frozen dataclasses, never mutate

```python
# ✅ Correct — use dataclasses.replace for "mutations"
from dataclasses import replace
new_dose = replace(candidate.dose, amount=2800, cap_applied=True)

# ❌ Never
candidate.dose.amount = 2800  # frozen=True will raise FrozenInstanceError
```

### Pattern 5: Domain models in, domain models out

```python
# ✅ Correct
def compute(self, candidate: Candidate, patient: PatientProfile) -> float: ...

# ❌ Never
def compute(self, candidate: dict, patient: dict) -> dict: ...
```

---

## 7. Docker Stack

```yaml
Services:
  api      → localhost:8000  FastAPI application (4 uvicorn workers)
  nginx    → localhost:80    Reverse proxy (rate limit: 100 req/min)
  neo4j    → localhost:7474  Neo4j Browser UI
             localhost:7687  Bolt protocol
  postgres → localhost:5432  PostgreSQL 16
  redis    → localhost:6379  Cache (wired in docker-compose, not yet in code)
  kafka    → localhost:9092  Event streaming (wired in docker-compose, not yet in code)
  airflow  → localhost:8080  Pipeline orchestration (dags directory empty)
```

### Start command

```bash
docker compose up -d
# Seed Neo4j (first time only, after ~60s startup)
docker compose exec neo4j cypher-shell -u neo4j -p supplement_engine_dev \
  -f /var/lib/neo4j/import/seed.cypher
```

---

## 8. Environment Variables

```bash
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=supplement_engine_dev
POSTGRES_DSN=postgresql+asyncpg://supplement:devpassword@postgres:5432/supplement_db
REDIS_URL=redis://redis:6379/0
MAX_RECOMMENDATIONS=8
DRS_THRESHOLD=0.35
MIN_CONFIDENCE=0.40
ENVIRONMENT=development
LOG_LEVEL=INFO
# ANTHROPIC_API_KEY=sk-ant-...  (Phase 2 — LLM explain polish)
```

---

## 9. API Contract

### POST /v1/recommendations

```json
{
  "patient": {
    "patient_id": "optional-uuid-string",
    "demographics": {
      "age": 52, "sex": "F", "region_code": "SA-01",
      "bmi": 31.0, "indoor_occupation": true, "veiled_dress": true,
      "pregnancy_status": false, "lactation_status": false,
      "fitzpatrick_skin_type": 5
    },
    "conditions": [
      {"code": "E11.9", "system": "ICD-10", "source": "ehr"},
      {"code": "K21.0", "system": "ICD-10", "source": "clinician"}
    ],
    "medications": [
      {"rxnorm": "6809",  "name": "Metformin",  "months_on": 18, "dose_mg": 1000},
      {"rxnorm": "41493", "name": "Omeprazole", "months_on": 24}
    ],
    "labs": [
      {"loinc": "1989-3", "value": 18, "unit": "ng/mL",
       "reference_low": 30, "reference_high": 80}
    ],
    "lifestyle": {
      "diet_pattern": "omnivore", "sun_exposure_hrs_wk": 1.5,
      "alcohol_units_wk": 0, "smoking": false, "activity_level": "moderate"
    },
    "preferences": {"halal": true, "vegan": false, "budget_tier": "standard"}
  },
  "options": {
    "max_recommendations": 6,
    "include_low_confidence": false,
    "nutrient_ids": null
  }
}
```

Response includes: `session_id`, `model_version`, `evidence_snapshot_id`,
`requires_clinician`, `clinician_handoff`, `next_review_in_weeks`, `execution_ms`,
`recommendations[]` (rank, rec_id, supplement, dose, confidence_score, evidence_grade,
rationale.why/evidence/safety, warnings[]), `suppressed[]`, `disclaimer`.

### Other endpoints

- `GET /v1/sessions/{session_id}` — retrieve served session with all recommendations
- `GET /v1/patients/{patient_id}/history?limit=10` — last N sessions for a patient
- `POST /v1/feedback` — clinician override / adverse event (feeds retraining)
- `GET /v1/audit/{session_id}` — audit record with input_hash
- `GET /v1/evidence/{snapshot_id}` — KG evidence snapshot captured at serve time
- `GET /v1/safety/check?nutrient_id=X&rxnorm_cui=Y` — standalone interaction check
- `GET /v1/nutrients/{nutrient_id}` — nutrient metadata from KG
- `GET /health` — aggregate dependency health
- `GET /health/live` — liveness probe (process up; always 200)
- `GET /health/ready` — readiness probe (200 when Neo4j + Postgres healthy; 503 otherwise)

---

## 10. What To Build Next — Prioritized Backlog

### Priority 1 — Complete the core (must before any production traffic)

#### 1a. Wire Redis caching into GraphClient ✅ (M2)

`GraphClient` caches read-heavy, near-static KG lookups. Interaction and safety edges are **not** cached.

| Method | Cached? | Redis key pattern | TTL |
|--------|---------|-------------------|-----|
| `get_nutrient_meta` | Yes | `nutrient:{id}` | 1h |
| `get_baseline_prevalence` | Yes | `baseline:{nutrient}:{bucket}` | 24h |
| `get_guideline` | Yes | `guideline:{nutrient}:{population}` | 24h |
| `get_condition_edges` | No | — | — |
| `get_depletion_edges` | No | — | — |
| `get_interaction_edges` | No | — | — |
| `get_antagonist_pairs` | No | — | — |
| `get_contraindications` | No | — | — |
| `get_kg_version` / `get_kg_stats` | No | — | — |

Unit tests: `tests/unit/test_graph_cache.py` (cache hit skips Neo4j).

#### 1b. Real evidence snapshot in pipeline ✅ (M2)

`_snapshot_evidence()` stores `kg_version`, KG stats, and a SHA-256 `content_hash` of the sorted snapshot JSON in `evidence_snapshots.contents`. Audit responses expose `kg_commit_sha` from the live KG metadata node (or Neo4j component version fallback).

#### 1c. Alembic migrations

`alembic/versions/` is empty. `postgres_init.sql` manages schema now but isn't viable for production schema evolution. Generate initial migration:

```bash
alembic init alembic
# Edit alembic.ini: sqlalchemy.url = postgresql+asyncpg://...
# Edit alembic/env.py: import Base from src.db.orm_models; target_metadata = Base.metadata
alembic revision --autogenerate -m "initial_schema"
alembic upgrade head
```

All future schema changes must be Alembic migrations, not edits to `postgres_init.sql`.

#### 1d. Integration tests

`tests/integration/` is empty. Build against real Docker services:

```python
# tests/integration/test_pipeline.py
# pytest with --neo4j-uri, --postgres-dsn flags
# Test: full recommendation session end-to-end
# Test: safety blocks (hemochromatosis + iron)
# Test: Postgres persistence (session saved, retrievable)
# Test: audit log written with correct input_hash
```

#### 1e. Expand Neo4j seed

Current seed: 10 nutrients, 13 conditions, 10 medications — sufficient for dev only.
Production needs: 80+ nutrients, 200+ ICD-10 conditions, 300+ medications.
Build a YAML registry (`scripts/knowledge_registry/`) and a compile script that generates Cypher from YAML — human-readable, version-controlled clinical data.

---

### Priority 2 — Personalization Engine ✅ (2c-M2, flag-gated)

Shipped: `src/personalization/engine.py` — loads prior `drs_snapshot` from last session, blends in Stage 1b. Enable with `PERSONALIZATION_ENABLED=1`.

---

### Priority 3 — Kafka event streaming ✅ (2c-M1)

Shipped: `src/pipelines/kafka_producer.py` — `patient.events` on delta APIs, `recommendation.served` after score. Enable with `KAFKA_ENABLED=1`. No consumers in this repo yet.

---

### Priority 4 — Airflow DAGs (`src/pipelines/dags/`)

Three DAGs to build:

**`dag_evidence_ingestion.py`** (weekly):
- PubMed E-utilities API → fetch new RCTs/meta-analyses matching nutrient/condition pairs
- NLP extraction of PICO + effect size (use Claude API for extraction)
- Write to curator queue table in Postgres
- On curator approval → generate Cypher → commit to Neo4j
- Capture new KG commit SHA as evidence_snapshot

**`dag_nightly_retraining.py`** (nightly):
- Pull `rec_feedback` records since last run (accepted/rejected/adverse_event)
- Join with `recommendations` for ground truth
- Pull post-recommendation lab results from `patient_labs` (outcome signal)
- Retrain Bayesian priors per demographic bucket (PyMC)
- Write updated priors back to Neo4j `HAS_BASELINE_RISK` edge weights
- Shadow deploy → A/B test → promote via `ModelVersionRepository.promote()`

**`dag_drift_detection.py`** (weekly):
- Compute PSI (Population Stability Index) on input distributions
- Compute recommendation rate change per nutrient (% shift week-over-week)
- Alert if PSI > 0.2 or recommendation rate shift > 15%
- Write drift metrics to Postgres `model_versions.performance_metrics` JSONB

---

### Priority 5 — FHIR lab parser (`POST /v1/labs/parse`)

```python
@app.post("/v1/labs/parse", tags=["labs"])
async def parse_labs(body: LabParseRequest):
    """
    Accept: HL7v2 ORU message OR FHIR Observation bundle
    Return: list[LabResult] (domain model)
    """
```

Build `src/pipelines/lab_parser.py`:
- FHIR R4 Observation → `LabResult` mapping
- HL7v2 OBX segment → `LabResult` mapping
- LOINC normalization (handle synonyms, unit conversion)
- OCR path (Phase 2): base64 image → extract lab table via Claude API vision

---

### Priority 6 — OLAP Analytics Layer

Build a star schema mart for population health analytics:

```sql
-- fact_recommendations (populated by Airflow nightly from recommendations table)
CREATE TABLE analytics.fact_recommendations (
    rec_id               UUID,
    served_date          DATE,
    nutrient_id          TEXT,
    icd10_codes          TEXT[],    -- denormalized from patient_conditions
    region_code          TEXT,
    age_bucket           TEXT,      -- '30_49', '50_64', etc.
    sex                  TEXT,
    bmi_bucket           TEXT,      -- 'normal', 'overweight', 'obese'
    confidence_score     FLOAT,
    evidence_grade       TEXT,
    p_deficient          FLOAT,     -- stored from DRS at serve time
    requires_clinician   BOOL,
    feedback_action      TEXT,      -- joined from rec_feedback
    model_version        TEXT
);

-- Dimensions: dim_nutrient, dim_condition, dim_region, dim_date
-- Metrics: deficiency_rate by region/condition, recommendation_volume by model_version,
--          clinician_override_rate, adverse_event_rate
```

No patient_id in the mart — de-identified aggregate only. Feeds:
- Public health prevalence maps (Power BI / Grafana)
- Payer HEOR module (cost per QALY)
- Model drift detection input

---

### Priority 7 — Phase 2 ML (PyMC Bayesian + LightGBM dose-response)

**Bayesian prior update (PyMC):**
```python
import pymc as pm

with pm.Model() as model:
    # Hierarchical model: population hyperpriors → individual posterior
    mu = pm.Beta("mu", alpha=2, beta=5)           # population mean deficiency rate
    kappa = pm.HalfNormal("kappa", sigma=10)       # concentration
    theta = pm.Beta("theta", alpha=mu*kappa, beta=(1-mu)*kappa)  # individual
    obs = pm.Bernoulli("obs", p=theta, observed=outcomes)
    trace = pm.sample(1000, tune=500, cores=2)
```

**LightGBM dose-response (Phase 3):**
- Features: demographics + conditions + medications + DRS + current_dose + form
- Target: post-treatment lab value (regression) + adverse_event flag (classification)
- Constraint: output must be within ±30% of rules-engine dose
- Never above UL. Never overrides hard contraindication.

---

### Priority 8 — SMART-on-FHIR EHR Integration (Phase 3)

- SMART launch sequence from EHR context
- FHIR Patient, Condition, MedicationRequest, Observation resources → PatientProfile
- OAuth2 PKCE flow
- `GET /v1/fhir/launch` → redirect to EHR authorization
- `GET /v1/fhir/callback` → exchange code → store token → redirect to recommendation UI

---

### Priority 9 — Clinician Dashboard API

Missing endpoints for the clinician-facing interface:

```
GET  /v1/clinician/queue          — patients flagged requires_clinician
POST /v1/clinician/override/{rec_id}  — structured override with reason code
GET  /v1/clinician/patient/{id}/timeline  — full recommendation history + outcomes
GET  /v1/clinician/population/summary   — aggregate deficiency prevalence for their patients
```

---

### Priority 10 — Genomics Integration (Phase 4)

PGx panel integration — modifies nutrient form selection and dose, never overrides phenotype:

| Gene | Variant | Effect on recommendation |
|---|---|---|
| MTHFR | C677T, A1298C | Prefer L-methylfolate over folic acid |
| VDR | FokI, BsmI | Adjust Vit D dose ±20% |
| HFE | C282Y, H63D | Block iron (hemochromatosis risk) |
| FUT2 | secretor status | Adjust B12 absorption factor |
| APOE | ε4 | Increase omega-3 dose |

Build `src/personalization/genomics_modifier.py`. Add `PatientProfile.genetics` field. Add `MTHFR_C677T`, `HFE_C282Y` etc. to Neo4j as nodes with edges to nutrients.

---

## 11. Clinical Knowledge To Add to Neo4j Seed

The current seed covers MVP. Production requires:

**Additional nutrients (add to `neo4j_seed.cypher`):**
choline, vitamin_c, copper, manganese, iodine, selenium, vitamin_a, vitamin_e, vitamin_k1,
thiamine (B1), riboflavin (B2), niacin (B3), pantothenic_acid (B5), biotin (B7),
phosphorus, chromium, molybdenum, lutein_zeaxanthin, alpha_lipoic_acid, berberine,
curcumin, probiotics, fiber, creatine, melatonin

**Additional high-priority condition edges:**
- Celiac (K90.0): iron, folate, B12, vitamin D, calcium, zinc (LR 2.0–3.5)
- IBD (K50/K51): iron, B12, vitamin D, zinc, magnesium
- Post-bariatric (Z98.84): vitamin D, B12, iron, thiamine, zinc, copper, ADEK vitamins
- MS (G35): high-dose vitamin D (monitored)
- AMD (H35.31): AREDS2 formula (lutein/zeaxanthin, zinc, copper, C, E)
- Hypothyroidism (E03): selenium + iodine (caution — dose-sensitive)
- Hypertension (I10): magnesium, potassium (carefully), CoQ10

**Additional drug edges:**
- ACE inhibitors / ARBs: potassium (↑K — avoid K supplements)
- K-sparing diuretics: potassium (absolute block)
- Tetracyclines / fluoroquinolones: Ca, Fe, Mg, Zn (chelation — time-separate ≥2h)
- Isoniazid: B6 (depletion — B6 25–50 mg/d required)
- Anticonvulsants (phenytoin, valproate): Vit D, folate, B12, Vit K
- Bisphosphonates: Ca, Fe (absorption — time-separate ≥30–60 min)
- Levodopa without carbidopa: B6 > 5mg/d → absolute block (reduces efficacy)

---

## 12. Coding Standards

When adding any new code to this project:

1. **All new domain concepts → `shared/models.py` first** as frozen dataclasses before any implementation
2. **All new Neo4j queries → `GraphClient` only** as typed async methods
3. **All new Postgres access → new Repository class** following the existing pattern
4. **All new business logic → pure functions or async methods** that take/return domain objects
5. **All new pipeline stages → inject as dependencies** into `RecommendationPipeline.__init__`
6. **All new endpoints → Pydantic schema in, domain model via `_schema_to_domain`, domain model to pipeline, dict response out**
7. **All new tests → mock the KG** (AsyncMock on GraphClient methods), test business logic in isolation
8. **Never import ORM models outside `src/db/`**
9. **Never import domain models inside `src/db/`** (except from `shared/models.py`)
10. **Never write raw SQL outside `src/db/repositories.py`**

---

## 13. Regulatory Checklist (For Any Future Feature)

Before adding any feature that touches recommendations:

- [ ] Does the safety engine run AFTER this feature? (It must always be the final gate)
- [ ] Is the output traceable to a specific evidence_snapshot_id?
- [ ] Is the input_hash captured in audit_log?
- [ ] Does the feature respect UL hard caps?
- [ ] Are all drug-nutrient interactions still checked?
- [ ] Does requires_clinician flag trigger correctly?
- [ ] Is the feature explainable via the three-layer rationale (why/evidence/safety)?
- [ ] Is PHI kept out of Neo4j?
- [ ] Does the new feature work with existing frozen dataclass domain models?

---

## 14. Phase Roadmap

| Phase | Timeline | Gate criteria |
|---|---|---|
| **0 — Foundations** ✅ | Wk 1–6 | KG schema + full DB layer + API + audit log |
| **1 — MVP** ✅ | Wk 7–14 | Redis cache + real KG snapshot + Alembic + integration tests + expanded seed + 8 conditions covered. Run `scripts/validate_phase1_gate.ps1` to sign off on your machine. |
| **2 — Personalization** | Mo 4–7 | Lab FHIR ingest + PersonalizationEngine + Kafka wired + Airflow DAGs + OLAP mart |
| **3 — Clinical Integration** | Mo 8–14 | SMART-on-FHIR + LightGBM dose-response + clinician dashboard API + Arabic NLP |
| **4 — Regulated Scale** | Mo 15–24 | SFDA SaMD submission + genomics PGx + payer HEOR + continuous learning loop |

---

## 15. Technology Versions (Pin These)

```
Python         3.12
FastAPI        0.111.0
SQLAlchemy     2.0.30 (async)
asyncpg        0.29.0
neo4j          5.20.0 (official async driver)
redis          5.0.4 (hiredis)
aiokafka       0.11.0
pydantic       2.7.1
alembic        1.13.1
uvicorn        0.30.1 + uvloop 0.19.0
PyMC           5.14.0 (Phase 2)
LightGBM       4.3.0 (Phase 3)
anthropic      0.28.0 (explain polish)
pytest         8.2.0
pytest-asyncio 0.23.7
Neo4j          5.20-community (Docker)
PostgreSQL     16-alpine (Docker)
Redis          7-alpine (Docker)
Kafka          Confluent 7.6.0 (Docker)
Airflow        2.9.1-python3.12 (Docker)
Nginx          1.25-alpine (Docker)
```
