"""
FastAPI application — all HTTP endpoints.

Changes from v1:
- PostgreSQL fully wired: PatientRepository, RecommendationRepository,
  AuditRepository, FeedbackRepository all injected via Depends
- DB init/close in lifespan alongside Neo4j
- Session persistence after every recommendation run
- Audit log written for every request (input_hash + execution_ms)
- /v1/sessions/{id} and /v1/patients/{id}/history endpoints added
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.middleware.api_key import ApiKeyMiddleware
from src.db.engine import (
    check_postgres_health, close_db, get_session as get_db_session,
    get_session_dep, init_db,
)
from src.db.repositories import (
    AuditRepository, EvidenceSnapshotRepository, FeedbackRepository,
    ModelVersionRepository, PatientRepository, RecommendationRepository,
)
from src.intake.validator import ProfileValidator
from src.knowledge.graph_client import GraphClient
from src.personalization.engine import PersonalizationEngine
from src.pipelines.kafka_producer import KafkaEventProducer
from src.pipelines.recommendation_pipeline import RecommendationPipeline
from src.shared.models import (
    Condition, ConditionSource, Demographics, FeedbackAction,
    LabResult, Lifestyle, Medication, PatientPreferences, PatientProfile, Sex,
)

logger = logging.getLogger(__name__)


# ── App state ──────────────────────────────────────────────────────────────

class AppState:
    graph_client: GraphClient
    pipeline: RecommendationPipeline
    kafka_producer: KafkaEventProducer
    model_version: str = "rec-engine-1.0.0"

app_state = AppState()


async def _load_active_model_version() -> str:
    async with get_db_session() as session:
        repo = ModelVersionRepository(session)
        active = await repo.get_active()
        return active or "rec-engine-1.0.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──
    neo4j_uri  = os.getenv("NEO4J_URI",      "bolt://neo4j:7687")
    neo4j_user = os.getenv("NEO4J_USER",     "neo4j")
    neo4j_pass = os.getenv("NEO4J_PASSWORD", "supplement_engine_dev")
    redis_url  = os.getenv("REDIS_URL")

    # Neo4j (+ optional Redis cache)
    app_state.graph_client = GraphClient(
        neo4j_uri, neo4j_user, neo4j_pass, redis_url=redis_url,
    )
    neo4j_ok = await app_state.graph_client.health_check()
    if not neo4j_ok:
        logger.warning("Neo4j not reachable at startup")

    # Postgres — single shared pool
    init_db(dsn=os.getenv("POSTGRES_DSN"))
    logger.info("Postgres connection pool initialised")

    app_state.model_version = await _load_active_model_version()
    personalization_enabled = os.getenv(
        "PERSONALIZATION_ENABLED", "0"
    ).lower() in ("1", "true", "yes")
    personalization = PersonalizationEngine() if personalization_enabled else None
    app_state.pipeline = RecommendationPipeline(
        graph_client=app_state.graph_client,
        max_recommendations=int(os.getenv("MAX_RECOMMENDATIONS", "8")),
        drs_threshold=float(os.getenv("DRS_THRESHOLD", "0.35")),
        min_confidence=float(os.getenv("MIN_CONFIDENCE", "0.40")),
        model_version=app_state.model_version,
        personalization=personalization,
        personalization_enabled=personalization_enabled,
    )
    app_state.kafka_producer = KafkaEventProducer()
    await app_state.kafka_producer.start()
    logger.info(
        "Supplement Recommendation Engine ready (model=%s, kafka=%s, personalization=%s)",
        app_state.model_version,
        os.getenv("KAFKA_ENABLED", "0"),
        personalization_enabled,
    )
    yield

    # ── Shutdown ──
    await app_state.kafka_producer.stop()
    await app_state.graph_client.close()
    await close_db()
    logger.info("Connections closed")


app = FastAPI(
    title="Supplement Recommendation Engine",
    version="1.0.0",
    description="Evidence-based personalized nutraceutical recommendations",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(ApiKeyMiddleware)


async def _emit_patient_event(
    event_type: str,
    patient_id: uuid.UUID,
    extra: Optional[dict[str, Any]] = None,
) -> None:
    await app_state.kafka_producer.send_patient_event(event_type, patient_id, extra)


# ── Request / Response Schemas ─────────────────────────────────────────────

class DemographicsIn(BaseModel):
    age: int = Field(..., ge=0, le=120)
    sex: str = Field(..., pattern="^(M|F|OTHER)$")
    region_code: str
    ethnicity: Optional[str] = None
    pregnancy_status: bool = False
    lactation_status: bool = False
    bmi: Optional[float] = Field(None, ge=10.0, le=80.0)
    fitzpatrick_skin_type: Optional[int] = Field(None, ge=1, le=6)
    indoor_occupation: bool = False
    veiled_dress: bool = False

class ConditionIn(BaseModel):
    code: str
    system: str = "ICD-10"
    onset_date: Optional[date] = None
    source: str = "self"

class MedicationIn(BaseModel):
    rxnorm: str
    name: str
    dose_mg: Optional[float] = None
    frequency: Optional[str] = None
    months_on: int = Field(default=0, ge=0)

class LabIn(BaseModel):
    loinc: str
    value: float
    unit: str
    date: Optional[datetime] = None
    reference_low: Optional[float] = None
    reference_high: Optional[float] = None

class LifestyleIn(BaseModel):
    diet_pattern: str = "omnivore"
    alcohol_units_wk: float = 0.0
    smoking: bool = False
    sun_exposure_hrs_wk: float = 5.0
    activity_level: str = "moderate"
    sleep_hrs: float = 7.0

class PreferencesIn(BaseModel):
    vegan: bool = False
    halal: bool = True
    kosher: bool = False
    budget_tier: str = "standard"

class PatientIn(BaseModel):
    patient_id: Optional[str] = None          # omit → engine generates new UUID
    demographics: DemographicsIn
    conditions: list[ConditionIn] = []
    medications: list[MedicationIn] = []
    labs: list[LabIn] = []
    lifestyle: LifestyleIn = LifestyleIn()
    preferences: PreferencesIn = PreferencesIn()

class RecommendationRequest(BaseModel):
    patient_id: Optional[str] = None
    patient: Optional[PatientIn] = None
    options: dict[str, Any] = {}


class LabDeltaIn(BaseModel):
    loinc: str
    value: float
    unit: str
    collected_at: Optional[datetime] = None
    reference_low: Optional[float] = None
    reference_high: Optional[float] = None
    flagged: bool = False


class MedicationSyncIn(BaseModel):
    rxnorm: str
    name: str
    dose_mg: Optional[float] = None
    frequency: Optional[str] = None
    months_on: int = Field(default=0, ge=0)


class MedicationsSyncRequest(BaseModel):
    medications: list[MedicationSyncIn]


class ConditionSyncIn(BaseModel):
    code: str
    system: str = "ICD-10"
    onset_date: Optional[date] = None
    source: str = "ehr"


class ConditionsSyncRequest(BaseModel):
    conditions: list[ConditionSyncIn]

class FeedbackRequest(BaseModel):
    rec_id: str
    session_id: str
    source: str = Field(default="user", pattern="^(user|clinician)$")
    action: str = Field(..., pattern="^(accepted|rejected|modified|adverse_event)$")
    notes: Optional[str] = None


# ── Middleware ─────────────────────────────────────────────────────────────

def _hash_patient_id(value: str | uuid.UUID) -> str:
    return hashlib.sha256(str(value).encode()).hexdigest()[:16]


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    t0 = time.monotonic()
    response = await call_next(request)
    execution_ms = int((time.monotonic() - t0) * 1000)

    log_payload: dict[str, Any] = {
        "event": "http_request",
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
        "execution_ms": execution_ms,
    }
    patient_hash = getattr(request.state, "patient_id_hash", None)
    if patient_hash:
        log_payload["patient_id_hash"] = patient_hash
    session_id = getattr(request.state, "session_id", None)
    if session_id:
        log_payload["session_id"] = session_id
    logger.info(json.dumps(log_payload))

    response.headers["X-Request-ID"] = request_id
    return response


# ── Endpoints ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["ops"])
async def health():
    neo4j_ok = await app_state.graph_client.health_check()
    postgres_ok = await check_postgres_health()
    all_ok = neo4j_ok and postgres_ok
    return {
        "status": "ok" if all_ok else "degraded",
        "neo4j": neo4j_ok,
        "postgres": postgres_ok,
    }


@app.get("/health/live", tags=["ops"])
async def health_live():
    """Liveness probe — API process is running."""
    return {"status": "alive"}


@app.get("/health/ready", tags=["ops"])
async def health_ready():
    """Readiness probe — dependencies available for scoring."""
    neo4j_ok = await app_state.graph_client.health_check()
    postgres_ok = await check_postgres_health()
    body = {
        "status": "ready" if (neo4j_ok and postgres_ok) else "not_ready",
        "neo4j": neo4j_ok,
        "postgres": postgres_ok,
    }
    if neo4j_ok and postgres_ok:
        return body
    return JSONResponse(status_code=503, content=body)


@app.post("/v1/recommendations", tags=["recommendations"])
async def create_recommendations(
    request: RecommendationRequest,
    raw_request: Request,
    session: AsyncSession = Depends(get_session_dep),
):
    """
    Production: pass patient_id only (data pre-loaded in Postgres).
    Dev: set ALLOW_INLINE_PATIENT=1 and pass patient object (Phase 1 compat).
    Does not write patient data on the score path when using patient_id.
    """
    t0 = time.monotonic()
    allow_inline = os.getenv("ALLOW_INLINE_PATIENT", "1").lower() in ("1", "true", "yes")
    patient_repo = PatientRepository(session)
    validator = ProfileValidator()

    try:
        if request.patient_id:
            try:
                pid = uuid.UUID(request.patient_id)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid patient_id")
            profile = await patient_repo.get_for_scoring(pid)
            if profile is None:
                raise HTTPException(status_code=404, detail="Patient not found")
        elif request.patient and allow_inline:
            profile = _schema_to_domain(request.patient)
            await patient_repo.upsert(profile)
        elif request.patient and not allow_inline:
            raise HTTPException(
                status_code=400,
                detail="Inline patient payload disabled; use patient_id or set ALLOW_INLINE_PATIENT=1",
            )
        else:
            raise HTTPException(
                status_code=422,
                detail="Provide patient_id (production) or patient (dev with ALLOW_INLINE_PATIENT=1)",
            )

        validation = validator.validate(profile)
        patient = validation.profile
        raw_request.state.patient_id_hash = _hash_patient_id(patient.patient_id)
        raw_json = (await raw_request.body()).decode()

        rec_repo = RecommendationRepository(session)
        audit_repo = AuditRepository(session)
        snapshot_repo = EvidenceSnapshotRepository(session)

        session_obj = await app_state.pipeline.evaluate(
            patient,
            include_low_confidence=request.options.get("include_low_confidence", False),
            nutrient_ids=request.options.get("nutrient_ids"),
            rec_repo=rec_repo,
        )

        execution_ms = int((time.monotonic() - t0) * 1000)

        if session_obj.evidence_snapshot:
            snap = session_obj.evidence_snapshot
            await snapshot_repo.save(
                snapshot_id=snap.snapshot_id,
                kg_commit_sha=snap.kg_version,
                contents=snap.contents,
            )
        await rec_repo.save_session(session_obj)
        await audit_repo.log_session(session_obj, raw_json, execution_ms)
        await app_state.kafka_producer.send_recommendation_served(
            session_id=session_obj.session_id,
            patient_id=session_obj.patient_id,
            model_version=session_obj.model_version,
            nutrient_ids=[r.nutrient_id for r in session_obj.recommendations],
            requires_clinician=session_obj.requires_clinician,
            served_at=session_obj.served_at,
        )

        response = _session_to_response(session_obj, execution_ms)
        raw_request.state.session_id = session_obj.session_id
        if validation.warnings:
            response["profile_warnings"] = list(validation.warnings)
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Pipeline failed for request %s", request)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/patients/{patient_id}/labs", status_code=201, tags=["patients"])
async def append_patient_lab(
    patient_id: str,
    body: LabDeltaIn,
    session: AsyncSession = Depends(get_session_dep),
):
    """Append a single lab result row (delta ingest)."""
    try:
        pid = uuid.UUID(patient_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid patient_id")

    repo = PatientRepository(session)
    if not await repo.exists(pid):
        raise HTTPException(status_code=404, detail="Patient not found")

    lab = LabResult(
        loinc=body.loinc,
        value_num=body.value,
        unit=body.unit,
        collected_at=body.collected_at or datetime.now(timezone.utc),
        reference_low=body.reference_low,
        reference_high=body.reference_high,
        flagged=body.flagged,
    )
    row_id = await repo.append_lab(pid, lab, source=ConditionSource.EHR)
    await _emit_patient_event("lab_appended", pid, {"loinc": body.loinc})
    return {"status": "created", "lab_row_id": str(row_id)}


@app.post("/v1/patients/{patient_id}/medications/sync", status_code=200, tags=["patients"])
async def sync_patient_medications(
    patient_id: str,
    body: MedicationsSyncRequest,
    session: AsyncSession = Depends(get_session_dep),
):
    """Replace active medication list for a patient."""
    try:
        pid = uuid.UUID(patient_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid patient_id")

    repo = PatientRepository(session)
    if not await repo.exists(pid):
        raise HTTPException(status_code=404, detail="Patient not found")

    meds = tuple(
        Medication(
            rxnorm_cui=m.rxnorm,
            name=m.name,
            dose_mg=m.dose_mg,
            frequency=m.frequency,
            months_on=m.months_on,
        )
        for m in body.medications
    )
    await repo.sync_medications(pid, meds, source=ConditionSource.EHR)
    await _emit_patient_event("medications_synced", pid, {"count": len(meds)})
    return {"status": "synced", "count": len(meds)}


@app.post("/v1/patients/{patient_id}/conditions/sync", status_code=200, tags=["patients"])
async def sync_patient_conditions(
    patient_id: str,
    body: ConditionsSyncRequest,
    session: AsyncSession = Depends(get_session_dep),
):
    """Upsert active conditions for a patient."""
    try:
        pid = uuid.UUID(patient_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid patient_id")

    repo = PatientRepository(session)
    if not await repo.exists(pid):
        raise HTTPException(status_code=404, detail="Patient not found")

    conditions = tuple(
        Condition(
            icd10_code=c.code,
            onset_date=c.onset_date,
            source=ConditionSource(c.source),
        )
        for c in body.conditions
    )
    await repo.sync_conditions(pid, conditions, source=ConditionSource.EHR)
    await _emit_patient_event("conditions_synced", pid, {"count": len(conditions)})
    return {"status": "synced", "count": len(conditions)}


@app.get("/v1/sessions/{session_id}", tags=["recommendations"])
async def get_recommendation_session(
    session_id: str,
    session: AsyncSession = Depends(get_session_dep),
):
    """Retrieve a previously served session — for clinician re-display."""
    repo = RecommendationRepository(session)
    meta = await repo.get_session(session_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Session not found")
    recs = await repo.get_session_recommendations(session_id)
    return {**meta, "recommendations": recs}


@app.get("/v1/patients/{patient_id}/history", tags=["patients"])
async def patient_history(
    patient_id: str,
    limit: int = 10,
    session: AsyncSession = Depends(get_session_dep),
):
    """Return the last N recommendation sessions for a patient."""
    try:
        pid = uuid.UUID(patient_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid patient_id")
    repo = RecommendationRepository(session)
    return await repo.get_patient_history(pid, limit=limit)


@app.post("/v1/feedback", status_code=202, tags=["feedback"])
async def submit_feedback(
    body: FeedbackRequest,
    session: AsyncSession = Depends(get_session_dep),
):
    """Clinician override / adverse event — feeds nightly retraining."""
    try:
        rec_id = uuid.UUID(body.rec_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid rec_id")

    repo = FeedbackRepository(session)
    feedback_id = await repo.save(
        rec_id=rec_id,
        session_id=body.session_id,
        source=body.source,
        action=FeedbackAction(body.action),
        notes=body.notes,
    )
    return {"status": "accepted", "feedback_id": str(feedback_id)}


@app.get("/v1/audit/{session_id}", tags=["audit"])
async def get_audit(
    session_id: str,
    session: AsyncSession = Depends(get_session_dep),
):
    """Return the audit record for a session — for regulatory review."""
    repo = AuditRepository(session)
    record = await repo.get_by_session(session_id)
    if not record:
        raise HTTPException(status_code=404, detail="Audit record not found")
    return record


@app.get("/v1/evidence/{snapshot_id}", tags=["audit"])
async def get_evidence_snapshot(
    snapshot_id: str,
    session: AsyncSession = Depends(get_session_dep),
):
    """Return a captured KG evidence snapshot — for regulatory reproducibility."""
    repo = EvidenceSnapshotRepository(session)
    record = await repo.get(snapshot_id)
    if not record:
        raise HTTPException(status_code=404, detail="Evidence snapshot not found")
    return record


@app.get("/v1/safety/check", tags=["safety"])
async def safety_check(nutrient_id: str, rxnorm_cui: str):
    """Standalone drug-nutrient interaction check — no DB write."""
    edges = await app_state.graph_client.get_interaction_edges(rxnorm_cui, nutrient_id)
    return {
        "nutrient_id": nutrient_id,
        "rxnorm_cui": rxnorm_cui,
        "interactions": [
            {"severity": e.severity.value if e.severity else "unknown",
             "mechanism": e.mechanism, "lr": e.lr}
            for e in edges
        ],
    }


@app.get("/v1/nutrients/{nutrient_id}", tags=["knowledge"])
async def get_nutrient(nutrient_id: str):
    """Nutrient metadata from Neo4j KG."""
    meta = await app_state.graph_client.get_nutrient_meta(nutrient_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Nutrient '{nutrient_id}' not found")
    return {
        "nutrient_id": meta.nutrient_id, "name": meta.name, "form": meta.form,
        "rda": meta.rda, "ul": meta.ul, "dose_unit": meta.dose_unit,
        "bioavailability_factor": meta.bioavailability_factor,
        "loinc_codes": list(meta.loinc_codes),
    }


# ── Schema → Domain ────────────────────────────────────────────────────────

def _schema_to_domain(p: PatientIn) -> PatientProfile:
    d = p.demographics
    return PatientProfile(
        patient_id=uuid.UUID(p.patient_id) if p.patient_id else uuid.uuid4(),
        demographics=Demographics(
            age=d.age, sex=Sex(d.sex), region_code=d.region_code,
            ethnicity=d.ethnicity, pregnancy_status=d.pregnancy_status,
            lactation_status=d.lactation_status, bmi=d.bmi,
            fitzpatrick_skin_type=d.fitzpatrick_skin_type,
            indoor_occupation=d.indoor_occupation, veiled_dress=d.veiled_dress,
        ),
        conditions=tuple(
            Condition(icd10_code=c.code, onset_date=c.onset_date,
                      source=ConditionSource(c.source))
            for c in p.conditions
        ),
        medications=tuple(
            Medication(rxnorm_cui=m.rxnorm, name=m.name, dose_mg=m.dose_mg,
                       frequency=m.frequency, months_on=m.months_on)
            for m in p.medications
        ),
        labs=tuple(
            LabResult(loinc=l.loinc, value_num=l.value, unit=l.unit,
                      collected_at=l.date or datetime.now(),
                      reference_low=l.reference_low, reference_high=l.reference_high)
            for l in p.labs
        ),
        lifestyle=Lifestyle(
            diet_pattern=p.lifestyle.diet_pattern,
            alcohol_units_wk=p.lifestyle.alcohol_units_wk,
            smoking=p.lifestyle.smoking,
            sun_exposure_hrs_wk=p.lifestyle.sun_exposure_hrs_wk,
            activity_level=p.lifestyle.activity_level,
            sleep_hrs=p.lifestyle.sleep_hrs,
        ),
        preferences=PatientPreferences(
            vegan=p.preferences.vegan, halal=p.preferences.halal,
            kosher=p.preferences.kosher, budget_tier=p.preferences.budget_tier,
        ),
    )


def _session_to_response(session_obj, execution_ms: int) -> dict:
    return {
        "session_id": session_obj.session_id,
        "model_version": session_obj.model_version,
        "evidence_snapshot_id": session_obj.evidence_snapshot_id,
        "requires_clinician": session_obj.requires_clinician,
        "clinician_handoff": session_obj.clinician_handoff,
        "next_review_in_weeks": session_obj.next_review_weeks,
        "execution_ms": execution_ms,
        "served_at": session_obj.served_at.isoformat(),
        "recommendations": [
            {
                "rank": r.rank,
                "rec_id": str(r.rec_id),
                "supplement": {"nutrient_id": r.nutrient_id,
                               "name": r.nutrient_name, "form": r.form},
                "dose": {
                    "amount": r.dose.amount if r.dose else None,
                    "unit": r.dose.unit if r.dose else None,
                    "frequency": r.dose.frequency if r.dose else None,
                    "with_food": r.dose.with_food if r.dose else None,
                    "ul_pct_used": r.dose.ul_pct_used if r.dose else None,
                    "cap_applied": r.dose.cap_applied if r.dose else None,
                },
                "confidence_score": r.confidence_score,
                "evidence_grade": r.evidence_grade.value,
                "requires_clinician": r.requires_clinician,
                "rationale": {"why": r.rationale_why,
                              "evidence": r.rationale_evidence,
                              "safety": r.rationale_safety},
                "warnings": [
                    {"severity": w.severity.value,
                     "with_agent": w.with_agent, "action": w.action}
                    for w in r.warnings
                ],
            }
            for r in session_obj.recommendations
        ],
        "suppressed": session_obj.suppressed,
        "disclaimer": "Wellness guidance only. Not a substitute for medical care.",
    }
