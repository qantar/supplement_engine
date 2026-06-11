# 🧬 Supplement Recommendation Engine

Production-grade Bayesian clinical decision support engine that maps patient demographics, ICD-10 conditions, medications, labs, and lifestyle into evidence-ranked nutraceutical recommendations with a deterministic safety gate.

**Master reference (setup, APIs, Docker, databases, user stories, gates):** [`ENGINE_MASTER_REFERENCE.md`](ENGINE_MASTER_REFERENCE.md)  
**Architecture diagrams (open in browser):** [`ENGINE_DIAGRAMS.html`](ENGINE_DIAGRAMS.html)

---

## Architecture

```
POST /v1/recommendations { patient_id }
         │
         ▼
┌─────────────────────┐
│ PatientRepository   │  Load from Postgres + read-time controls (latest lab/LOINC)
│ ProfileValidator    │  ICD-10 / RxNorm / LOINC checks
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│ DeficiencyRiskScorer│  Bayesian log-odds accumulation per nutrient (concurrent)
│                     │  logit(P) = logit(baseline) + Σ log(LR_i)
│  Sources:           │
│  • Population prior │  Neo4j: HAS_BASELINE_RISK edges (KSA: Vit D 65%)
│  • Geographic mods  │  Hardcoded: KSA Vit D ×2.2, iodine ×0.8
│  • BMI adjustment   │  Fat-soluble vitamins: ×1.5 if BMI ≥ 30
│  • Conditions       │  Neo4j: INCREASES_DEMAND_FOR + CAUSES_MALABSORPTION_OF
│  • Medications      │  Neo4j: DEPLETES × duration_factor(months_on/onset_months)
│  • Lab override     │  80% weight — measured value dominates prior
└────────┬────────────┘
         │  dict[nutrient_id → DRS]
         ▼
┌─────────────────────┐
│ CandidateGenerator  │  DRS ≥ 0.35 threshold OR guideline trigger
│                     │  Collapses ≥3 B-vitamins → B-complex
└────────┬────────────┘
         │  List[Candidate]
         ▼
┌─────────────────────┐
│   DoseOptimizer     │  Priority: pregnancy override → guideline → DRS-adjusted RDA
│                     │  → bioavailability correction → BMI adj → 70% UL cap
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│    SafetyEngine     │  DETERMINISTIC — no ML
│  1. Drug-nutrient   │  Neo4j: INTERACTS_WITH (4-tier: CI/major/moderate/minor)
│  2. Disease CI      │  Static rules: hemochromatosis+Fe, CKD4+K, pregnancy+A
│  3. Nutrient-nutri  │  Neo4j: ANTAGONIZES pairs → timing warnings
│  4. UL enforcement  │  Hard cap: never > UL; soft cap at 70%
│  5. Escalation      │  10 triggers → requires_clinician = true
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│ ConfidenceCompositor│  C = 0.40·E + 0.15·D + 0.15·S + 0.10·P + 0.10·M + 0.10·B
│                     │  Rank = P_deficient × Confidence × I_safety
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│   ExplainService    │  Template slot-fill from DRS contributor trace
│                     │  why / evidence / safety — three-layer rationale
└────────┬────────────┘
         │
         ▼
   RecommendationSession (ranked + suppressed + clinician_flag + audit)
```

---

## Quick Start

> **First time setup?** With Docker Desktop installed, one command starts everything:

```powershell
cd supplement_engine
python scripts/run_app.py up --open
# or: .\scripts\start_app.ps1 -Open
```

Or manually: `docker compose up -d --build api neo4j postgres redis nginx` then seed Neo4j (see setup doc).

```powershell
# Clinician console (with backend stack running)
docker compose up --build frontend api neo4j postgres redis
# console → http://localhost:3000
```

```powershell
# After stack is up — test a recommendation
curl.exe -X POST http://localhost/v1/recommendations -H "Content-Type: application/json" -d "@examples/patient_t2dm_riyadh.json"

# Swagger UI
start http://localhost/docs
```

---

## Example Request

```json
POST /v1/recommendations
{
  "patient": {
    "demographics": {
      "age": 52, "sex": "F", "region_code": "SA-01",
      "bmi": 31.0, "indoor_occupation": true, "veiled_dress": true,
      "pregnancy_status": false
    },
    "conditions": [
      {"code": "E11.9", "system": "ICD-10"},
      {"code": "K21.0", "system": "ICD-10"}
    ],
    "medications": [
      {"rxnorm": "6809",  "name": "Metformin",  "months_on": 18},
      {"rxnorm": "41493", "name": "Omeprazole", "months_on": 24}
    ],
    "labs": [
      {"loinc": "1989-3", "value": 18, "unit": "ng/mL",
       "reference_low": 30, "reference_high": 80}
    ],
    "lifestyle": {
      "diet_pattern": "omnivore",
      "sun_exposure_hrs_wk": 1.5,
      "indoor_occupation": true
    }
  },
  "options": {"max_recommendations": 6}
}
```

---

## Project Structure

```
supplement_engine/
├── src/
│   ├── api/app.py                        FastAPI endpoints + Pydantic schemas
│   ├── core/
│   │   ├── deficiency_risk_scorer.py     Bayesian DRS — the scoring heart
│   │   └── candidate_generator.py        Threshold + guideline → candidates
│   │                                     DoseOptimizer + ConfidenceCompositor
│   ├── safety/safety_engine.py           Deterministic safety gate (no ML)
│   ├── knowledge/graph_client.py         Neo4j async typed query interface
│   ├── explain/explain_service.py        Template rationale generator
│   ├── pipelines/recommendation_pipeline.py  End-to-end orchestrator
│   └── shared/models.py                  Frozen dataclass domain models
├── tests/unit/test_core.py               Pytest unit tests (mocked KG)
├── scripts/
│   ├── neo4j_seed.cypher                 KG schema + clinical data seed
│   └── postgres_init.sql                 Patient store + audit schema
├── infra/
│   ├── docker/Dockerfile.api             Multi-stage production image
│   └── nginx/nginx.conf                  Rate-limited reverse proxy
├── docker-compose.yml                    Full stack: API + Neo4j + PG + Redis + Kafka
└── requirements.txt
```

---

## Services (docker compose)

| Service   | Port | Purpose |
|-----------|------|---------|
| api       | 8000 | FastAPI — recommendation engine |
| frontend  | 3000 | Next.js clinician console ([`frontend/`](frontend/README.md)) |
| nginx     | 80   | Reverse proxy + rate limiting |
| neo4j     | 7474/7687 | Knowledge graph |
| postgres  | 5432 | Patient store + audit log |
| redis     | 6379 | KG query cache |
| kafka     | 9092 | Event streaming (patient.events → recommendation.served) |

---

## Testing

```bash
# Unit tests (no Docker needed)
pip install -r requirements.txt
pytest tests/unit/ -v --cov=src --cov-report=term-missing

# Integration tests (requires running stack: docker compose up -d + Neo4j seed)
# Or run the full gate: .\scripts\validate_phase1_gate.ps1
pytest tests/integration/ -v -m integration
```

---

## Phase Roadmap

| Phase | Timeline | Scope |
|-------|----------|-------|
| 0 | Wk 1–6 | KG seed + API skeleton + audit log |
| 1 (MVP) | Wk 7–14 | Full rules engine, 8 conditions, template explain |
| 2 | Mo 4–7 | Lab FHIR ingest, Bayesian individual update (PyMC), LLM explain polish |
| 3 | Mo 8–14 | SMART-on-FHIR, LightGBM dose-response, Arabic NLP |
| 4 | Mo 15–24 | SFDA SaMD submission, genomics PGx, payer HEOR module |

---

## Safety Guarantees

- **UL enforcement**: dose never exceeds UL; soft-capped at 70% by default
- **Drug interactions**: 4-tier (contraindicated → major → moderate → minor); contraindicated = blocked
- **Disease contraindications**: hemochromatosis + iron, CKD4+ + potassium, pregnancy + high-dose retinol → absolute blocks
- **ML constraints** (Phase 3): dose-response model constrained to ±30% of rules-engine output; never overrides hard blocks or UL
- **Audit trail**: append-only, evidence snapshot captured per session, 7-year retention
