# Patient realm contract

The recommendation engine **reads** normalized patient state from Postgres at score time. It does **not** connect to upstream warehouses, run bulk ETL, or detect when bulk loads occur.

## Architecture boundary

| Responsibility | Owner |
|----------------|--------|
| Bulk backfill / nightly refresh into patient tables | **External feeder project** (your other repo) |
| Realtime deltas (labs, meds, conditions) | **This engine** — `POST /v1/patients/{id}/…` |
| Scoring | **This engine** — `POST /v1/recommendations { patient_id }` |
| Clinical knowledge graph | **This engine** — Neo4j (batch seed, not patient data) |

The engine treats Postgres as the source of truth. Rows may arrive from your feeder, from API deltas, or from local seed scripts — the score path is identical.

## Tables (Postgres `public`)

| Table | Purpose |
|-------|---------|
| `patients` | Demographics row per `patient_id` (UUID PK) |
| `patient_conditions` | ICD-10 conditions; active if `resolved_date` IS NULL |
| `patient_medications` | RxNorm meds; active if `stop_date` IS NULL |
| `patient_labs` | LOINC lab results (append-only history) |

Optional audit columns on child rows: `source`, `source_system`, `ingest_batch_id` (for your feeder's traceability — not read by scoring logic except `source` enum).

Schema: `src/db/orm_models.py`, migrations in `alembic/versions/`.

## Read-time assembly (`get_for_scoring`)

When scoring, `PatientRepository.get_for_scoring()` loads ORM rows and applies:

1. **Conditions** — only rows with `resolved_date` NULL  
2. **Medications** — only rows with `stop_date` NULL  
3. **Labs** — **latest row per LOINC** by `collected_at`  
4. **Validation** — `ProfileValidator` drops invalid ICD-10 / RxNorm / LOINC with warnings  

Your feeder should write history-compatible rows (append labs; use stop/resolved dates for inactive meds/conditions).

## Production score path

```http
POST /v1/recommendations
X-API-Key: <key>
{ "patient_id": "<uuid>", "options": { "max_recommendations": 6 } }
```

No patient payload on the score path when `ALLOW_INLINE_PATIENT=0`. The engine does not write patient data during scoring.

## Realtime delta APIs (this engine)

| Method | Path | Behavior |
|--------|------|----------|
| POST | `/v1/patients/{id}/labs` | Append one lab row |
| POST | `/v1/patients/{id}/medications/sync` | Replace active med list |
| POST | `/v1/patients/{id}/conditions/sync` | Upsert active conditions |

Kafka `patient.events` is emitted on delta writes when `KAFKA_ENABLED=1`.

## External feeder requirements

1. **Stable UUID** — assign `patient_id` once; use the same value for scoring.  
2. **Vocab** — valid ICD-10, numeric RxNorm CUIs, LOINC codes (same rules as `ProfileValidator`).  
3. **Demographics** — map to `patients` columns (`dob_year` or age-derived fields, `sex`, `region_code`, `bmi`, pregnancy flags, etc.).  
4. **Do not** require this engine to call your warehouse — write directly to these tables (or via your DB user).  
5. **Optional** — log batches in `ingest_batches` for your ops; engine ignores it for scoring.

## Local dev / pilot (not production bulk)

This repo includes **seed-only** helpers when no external feeder is running:

```bash
python scripts/seed_patient_realm.py
# or: docker compose exec api python scripts/seed_patient_realm.py
```

Fixtures: `examples/pilot/`, registry: `src/intake/pilot_cohort.py`.

### Pilot cohort (stable patient_id values)

| patient_id | Fixture | Clinical intent |
|------------|---------|-----------------|
| `f47ac10b-58cc-4372-a567-0e02b2c3d479` | `patient_t2dm_riyadh.json` | T2DM + veiled/indoor + low vitamin D |
| `a10bc10b-58cc-4372-a567-0e02b2c3d480` | `ckd_stage3.json` | CKD stage 3 + T2DM + ACE inhibitor |
| `b20bc10b-58cc-4372-a567-0e02b2c3d481` | `hemochromatosis.json` | Hemochromatosis — iron must be blocked |
| `c30bc10b-58cc-4372-a567-0e02b2c3d482` | `pregnancy.json` | Pregnancy — folate/iron guideline doses |
| `d40bc10b-58cc-4372-a567-0e02b2c3d483` | `celiac.json` | Celiac — malabsorption risk nutrients |
| `e50bc10b-58cc-4372-a567-0e02b2c3d484` | `vegan_b12.json` | Vegan + low B12 lab |
Gate: `.\scripts\validate_phase2b_pilot_gate.ps1`

Full pilot matrix (16 patients): `examples/pilot/README.md`.
