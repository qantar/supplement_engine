"""
Repository layer — the only place SQL touches domain models.

Pattern: one repository class per aggregate root.
Each method takes/returns domain models (frozen dataclasses), never ORM objects.

This is the translator between the database world and the business logic world.
The pipeline, safety engine, and API never write SQL — they call repositories.

Repositories injected via FastAPI Depends — same session per request.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.orm_models import (
    AuditLogORM, EvidenceSnapshotORM, IngestBatchORM, ModelVersionORM,
    PatientConditionORM, PatientLabORM, PatientMedicationORM,
    PatientORM, RecFeedbackORM, RecommendationORM,
    RecommendationSessionORM, RecommendationWarningORM,
)
from src.shared.models import (
    Condition, ConditionSource, Demographics, EvidenceGrade,
    FeedbackAction, LabResult, Lifestyle, Medication, PatientPreferences,
    PatientProfile, RecommendationOutput, RecommendationSession, Sex,
)


# ── Patient Repository ─────────────────────────────────────────────────────

class PatientRepository:
    """
    Patient realm read/write for scoring and API deltas.

    Bulk backfill is out of scope for this service — an external project
    writes directly to the same Postgres tables. This repo only reads those
    rows at score time (get_for_scoring) and accepts realtime deltas via
    append/sync methods.
    """

    def __init__(self, session: AsyncSession):
        self._s = session

    async def get_for_scoring(self, patient_id: uuid.UUID) -> Optional[PatientProfile]:
        """Load profile with read-time controls (active meds, latest labs)."""
        profile = await self.get(patient_id)
        if profile is None:
            return None
        return _apply_read_controls(profile)

    async def upsert(self, profile: PatientProfile) -> uuid.UUID:
        """
        Dev/inline path only (ALLOW_INLINE_PATIENT=1). Production bulk load
        is performed by an external feeder into the same tables.
        """
        from datetime import date

        existing = await self._s.get(PatientORM, profile.patient_id)
        demo = profile.demographics
        dob_year = date.today().year - demo.age if demo.age > 0 else None

        if existing is None:
            orm = PatientORM(
                patient_id=profile.patient_id,
                dob_year=dob_year,
                sex=demo.sex.value,
                region_code=demo.region_code,
                pregnancy_status=demo.pregnancy_status,
                lactation_status=demo.lactation_status,
                bmi=demo.bmi,
                indoor_occupation=demo.indoor_occupation,
                veiled_dress=demo.veiled_dress,
            )
            self._s.add(orm)
            await self._s.flush()
        else:
            existing.dob_year = dob_year or existing.dob_year
            existing.sex = demo.sex.value
            existing.region_code = demo.region_code
            existing.pregnancy_status = demo.pregnancy_status
            existing.lactation_status = demo.lactation_status
            existing.bmi = demo.bmi
            existing.indoor_occupation = demo.indoor_occupation
            existing.veiled_dress = demo.veiled_dress
            existing.updated_at = datetime.now(timezone.utc)

        await self.sync_conditions(
            profile.patient_id, profile.conditions, source=ConditionSource.SELF,
        )
        await self.sync_medications(
            profile.patient_id, profile.medications, source=ConditionSource.SELF,
        )
        for lab in profile.labs:
            await self.append_lab(profile.patient_id, lab, source=ConditionSource.SELF)
        return profile.patient_id

    async def append_lab(
        self,
        patient_id: uuid.UUID,
        lab: LabResult,
        *,
        source: ConditionSource = ConditionSource.EHR,
        source_system: str | None = None,
        ingest_batch_id: str | None = None,
    ) -> uuid.UUID:
        """Append one lab row; skip duplicate (patient_id, loinc, collected_at)."""
        stmt = select(PatientLabORM).where(
            PatientLabORM.patient_id == patient_id,
            PatientLabORM.loinc == lab.loinc,
            PatientLabORM.collected_at == lab.collected_at,
        )
        result = await self._s.execute(stmt)
        if result.scalar_one_or_none():
            return patient_id

        row_id = uuid.uuid4()
        self._s.add(PatientLabORM(
            id=row_id,
            patient_id=patient_id,
            loinc=lab.loinc,
            value_num=lab.value_num,
            unit=lab.unit,
            collected_at=lab.collected_at,
            reference_low=lab.reference_low,
            reference_high=lab.reference_high,
            flagged=lab.flagged,
            source_system=source_system or source.value,
            ingest_batch_id=ingest_batch_id,
            ingested_at=datetime.now(timezone.utc),
        ))
        return row_id

    async def sync_medications(
        self,
        patient_id: uuid.UUID,
        medications: tuple[Medication, ...],
        *,
        source: ConditionSource = ConditionSource.EHR,
        source_system: str | None = None,
        ingest_batch_id: str | None = None,
    ) -> None:
        """Replace active medications (stop_date IS NULL) with incoming list."""
        if not await self.exists(patient_id):
            raise ValueError(f"patient not found: {patient_id}")

        now = datetime.now(timezone.utc)
        await self._s.execute(
            update(PatientMedicationORM)
            .where(
                PatientMedicationORM.patient_id == patient_id,
                PatientMedicationORM.stop_date.is_(None),
            )
            .values(stop_date=now)
        )

        for m in medications:
            self._s.add(PatientMedicationORM(
                patient_id=patient_id,
                rxnorm_cui=m.rxnorm_cui,
                name=m.name,
                dose_mg=m.dose_mg,
                frequency=m.frequency,
                months_on=m.months_on,
                start_date=now,
                source_system=source_system or source.value,
                ingest_batch_id=ingest_batch_id,
                ingested_at=now,
            ))

    async def sync_conditions(
        self,
        patient_id: uuid.UUID,
        conditions: tuple[Condition, ...],
        *,
        source: ConditionSource = ConditionSource.EHR,
        source_system: str | None = None,
        ingest_batch_id: str | None = None,
    ) -> None:
        """Upsert conditions by (patient_id, icd10_code); skip unresolved rows."""
        now = datetime.now(timezone.utc)
        for c in conditions:
            onset_dt = (
                datetime.combine(c.onset_date, datetime.min.time(), tzinfo=timezone.utc)
                if c.onset_date else None
            )
            stmt = select(PatientConditionORM).where(
                PatientConditionORM.patient_id == patient_id,
                PatientConditionORM.icd10_code == c.icd10_code,
                PatientConditionORM.resolved_date.is_(None),
            )
            result = await self._s.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                existing.source = c.source.value
                existing.onset_date = onset_dt
                existing.source_system = source_system or source.value
                existing.ingest_batch_id = ingest_batch_id
                existing.ingested_at = now
            else:
                self._s.add(PatientConditionORM(
                    patient_id=patient_id,
                    icd10_code=c.icd10_code,
                    snomed_id=c.snomed_id,
                    onset_date=onset_dt,
                    source=c.source.value,
                    source_system=source_system or source.value,
                    ingest_batch_id=ingest_batch_id,
                    ingested_at=now,
                ))

    async def log_ingest_batch(
        self,
        batch_id: str,
        source_system: str,
        row_counts: dict | None = None,
        dbt_run_id: str | None = None,
    ) -> None:
        existing = await self._s.get(IngestBatchORM, batch_id)
        if existing:
            return
        self._s.add(IngestBatchORM(
            batch_id=batch_id,
            source_system=source_system,
            row_counts=row_counts,
            dbt_run_id=dbt_run_id,
        ))

    async def get(self, patient_id: uuid.UUID) -> Optional[PatientProfile]:
        """Load raw patient profile (all child rows)."""
        stmt = (
            select(PatientORM)
            .where(PatientORM.patient_id == patient_id)
            .options(
                selectinload(PatientORM.conditions),
                selectinload(PatientORM.medications),
                selectinload(PatientORM.labs),
            )
        )
        result = await self._s.execute(stmt)
        orm = result.scalar_one_or_none()
        return _orm_to_profile(orm) if orm else None

    async def exists(self, patient_id: uuid.UUID) -> bool:
        result = await self._s.get(PatientORM, patient_id)
        return result is not None


# ── Recommendation Repository ──────────────────────────────────────────────

class RecommendationRepository:
    """
    Writes recommendation sessions and reads history.
    All writes are append-only — recommendations are immutable once served.
    """

    def __init__(self, session: AsyncSession):
        self._s = session

    async def save_session(self, session_obj: RecommendationSession) -> None:
        """
        Persists a full recommendation session atomically:
        - One RecommendationSessionORM row
        - N RecommendationORM rows with their warnings
        """
        session_orm = RecommendationSessionORM(
            session_id=session_obj.session_id,
            patient_id=session_obj.patient_id,
            model_version=session_obj.model_version,
            evidence_snapshot_id=session_obj.evidence_snapshot_id,
            requires_clinician=session_obj.requires_clinician,
            clinician_handoff=session_obj.clinician_handoff,
            next_review_weeks=session_obj.next_review_weeks,
            suppressed_count=len(session_obj.suppressed),
            suppressed_detail=session_obj.suppressed or None,
            drs_snapshot=session_obj.drs_snapshot,
            served_at=session_obj.served_at,
        )
        self._s.add(session_orm)
        await self._s.flush()

        for rec in session_obj.recommendations:
            rec_orm = RecommendationORM(
                rec_id=rec.rec_id,
                patient_id=rec.patient_id,
                session_id=rec.session_id,
                nutrient_id=rec.nutrient_id,
                nutrient_name=rec.nutrient_name,
                form=rec.form,
                dose_amount=rec.dose.amount if rec.dose else None,
                dose_unit=rec.dose.unit if rec.dose else None,
                dose_frequency=rec.dose.frequency if rec.dose else None,
                dose_with_food=rec.dose.with_food if rec.dose else True,
                dose_ul_pct_used=rec.dose.ul_pct_used if rec.dose else None,
                dose_cap_applied=rec.dose.cap_applied if rec.dose else False,
                confidence_score=rec.confidence_score,
                evidence_grade=rec.evidence_grade.value,
                requires_clinician=rec.requires_clinician,
                rationale_why=rec.rationale_why,
                rationale_evidence=rec.rationale_evidence,
                rationale_safety=rec.rationale_safety,
                model_version=rec.model_version,
                evidence_snapshot_id=rec.evidence_snapshot_id,
                rank=rec.rank,
                served_at=rec.served_at,
            )
            self._s.add(rec_orm)

            for w in rec.warnings:
                self._s.add(RecommendationWarningORM(
                    rec_id=rec.rec_id,
                    severity=w.severity.value,
                    with_agent=w.with_agent,
                    action=w.action,
                    mechanism=w.mechanism,
                ))

    async def get_session(self, session_id: str) -> Optional[dict]:
        """Retrieve a previously served session for re-display or audit."""
        stmt = (
            select(RecommendationSessionORM)
            .where(RecommendationSessionORM.session_id == session_id)
        )
        result = await self._s.execute(stmt)
        orm = result.scalar_one_or_none()
        if not orm:
            return None
        return {
            "session_id": orm.session_id,
            "patient_id": str(orm.patient_id),
            "model_version": orm.model_version,
            "evidence_snapshot_id": orm.evidence_snapshot_id,
            "requires_clinician": orm.requires_clinician,
            "next_review_weeks": orm.next_review_weeks,
            "served_at": orm.served_at.isoformat(),
        }

    async def get_patient_history(
        self, patient_id: uuid.UUID, limit: int = 20
    ) -> list[dict]:
        """Return the last N sessions for a patient — for clinician dashboard."""
        stmt = (
            select(RecommendationSessionORM)
            .where(RecommendationSessionORM.patient_id == patient_id)
            .order_by(RecommendationSessionORM.served_at.desc())
            .limit(limit)
        )
        result = await self._s.execute(stmt)
        rows = result.scalars().all()
        return [
            {
                "session_id": r.session_id,
                "model_version": r.model_version,
                "requires_clinician": r.requires_clinician,
                "suppressed_count": r.suppressed_count,
                "next_review_weeks": r.next_review_weeks,
                "served_at": r.served_at.isoformat(),
            }
            for r in rows
        ]

    async def get_session_recommendations(self, session_id: str) -> list[dict]:
        """Return all recommendations for a session — for re-display."""
        stmt = (
            select(RecommendationORM)
            .where(RecommendationORM.session_id == session_id)
            .options(selectinload(RecommendationORM.warnings))
            .order_by(RecommendationORM.rank)
        )
        result = await self._s.execute(stmt)
        recs = result.scalars().all()
        return [_rec_orm_to_dict(r) for r in recs]

    async def get_last_drs_snapshot(
        self, patient_id: uuid.UUID
    ) -> Optional[dict[str, float]]:
        """Most recent DRS posterior snapshot for longitudinal personalization."""
        stmt = (
            select(RecommendationSessionORM.drs_snapshot)
            .where(RecommendationSessionORM.patient_id == patient_id)
            .where(RecommendationSessionORM.drs_snapshot.isnot(None))
            .order_by(RecommendationSessionORM.served_at.desc())
            .limit(1)
        )
        result = await self._s.execute(stmt)
        row = result.scalar_one_or_none()
        if not row:
            return None
        return {str(k): float(v) for k, v in row.items()}


# ── Feedback Repository ────────────────────────────────────────────────────

class FeedbackRepository:
    """
    Stores clinician overrides, adverse events, and acceptance signals.
    These feed the nightly retraining pipeline.
    """

    def __init__(self, session: AsyncSession):
        self._s = session

    async def save(
        self,
        rec_id: uuid.UUID,
        session_id: str,
        source: str,
        action: FeedbackAction,
        notes: Optional[str] = None,
    ) -> uuid.UUID:
        feedback_id = uuid.uuid4()
        self._s.add(RecFeedbackORM(
            id=feedback_id,
            rec_id=rec_id,
            session_id=session_id,
            source=source,
            action=action.value,
            notes=notes,
            created_at=datetime.now(timezone.utc),
        ))
        return feedback_id

    async def get_for_retraining(
        self, since: datetime, action_filter: Optional[list[str]] = None
    ) -> list[dict]:
        """
        Fetch feedback records for the ML retraining pipeline.
        Called nightly by the Airflow DAG.
        """
        stmt = select(RecFeedbackORM).where(RecFeedbackORM.created_at >= since)
        if action_filter:
            stmt = stmt.where(RecFeedbackORM.action.in_(action_filter))
        result = await self._s.execute(stmt)
        rows = result.scalars().all()
        return [
            {
                "feedback_id": str(r.id),
                "rec_id": str(r.rec_id),
                "source": r.source,
                "action": r.action,
                "notes": r.notes,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]


# ── Audit Repository ───────────────────────────────────────────────────────

class AuditRepository:
    """
    Append-only audit log. 7-year retention.
    DB-level rules prevent UPDATE/DELETE (see postgres_init.sql).
    """

    def __init__(self, session: AsyncSession):
        self._s = session

    async def log_session(
        self,
        session_obj: RecommendationSession,
        request_json: str,
        execution_ms: int,
    ) -> None:
        input_hash = hashlib.sha256(request_json.encode()).hexdigest()
        output_summary = {
            "nutrients": [r.nutrient_id for r in session_obj.recommendations],
            "confidence_scores": [r.confidence_score for r in session_obj.recommendations],
            "grades": [r.evidence_grade.value for r in session_obj.recommendations],
            "suppressed_count": len(session_obj.suppressed),
        }
        self._s.add(AuditLogORM(
            session_id=session_obj.session_id,
            patient_id=session_obj.patient_id,
            model_version=session_obj.model_version,
            evidence_snapshot_id=session_obj.evidence_snapshot_id,
            input_hash=input_hash,
            output_summary=output_summary,
            suppressed_count=len(session_obj.suppressed),
            requires_clinician=session_obj.requires_clinician,
            execution_ms=execution_ms,
            created_at=datetime.now(timezone.utc),
        ))

    async def get_by_session(self, session_id: str) -> Optional[dict]:
        stmt = select(AuditLogORM).where(AuditLogORM.session_id == session_id)
        result = await self._s.execute(stmt)
        row = result.scalar_one_or_none()
        if not row:
            return None
        return {
            "session_id": row.session_id,
            "patient_id": str(row.patient_id),
            "model_version": row.model_version,
            "evidence_snapshot_id": row.evidence_snapshot_id,
            "input_hash": row.input_hash,
            "output_summary": row.output_summary,
            "requires_clinician": row.requires_clinician,
            "execution_ms": row.execution_ms,
            "created_at": row.created_at.isoformat(),
        }


# ── Evidence Snapshot Repository ───────────────────────────────────────────

class EvidenceSnapshotRepository:
    """
    Captures Neo4j KG state per session for reproducibility.
    Regulators can replay any historical recommendation.
    """

    def __init__(self, session: AsyncSession):
        self._s = session

    async def save(self, snapshot_id: str, kg_commit_sha: str, contents: dict) -> None:
        existing = await self._s.get(EvidenceSnapshotORM, snapshot_id)
        if existing:
            return  # idempotent — same snapshot, don't overwrite
        self._s.add(EvidenceSnapshotORM(
            snapshot_id=snapshot_id,
            kg_commit_sha=kg_commit_sha,
            captured_at=datetime.now(timezone.utc),
            contents=contents,
        ))

    async def get(self, snapshot_id: str) -> Optional[dict]:
        row = await self._s.get(EvidenceSnapshotORM, snapshot_id)
        if not row:
            return None
        return {
            "snapshot_id": row.snapshot_id,
            "kg_commit_sha": row.kg_commit_sha,
            "captured_at": row.captured_at.isoformat(),
            "contents": row.contents,
        }


# ── Model Version Repository ───────────────────────────────────────────────

class ModelVersionRepository:
    def __init__(self, session: AsyncSession):
        self._s = session

    async def get_active(self) -> Optional[str]:
        stmt = select(ModelVersionORM).where(ModelVersionORM.status == "active")
        result = await self._s.execute(stmt)
        row = result.scalar_one_or_none()
        return row.version if row else None

    async def promote(self, version: str) -> None:
        """Shadow → active, retire the previous active version."""
        now = datetime.now(timezone.utc)
        await self._s.execute(
            update(ModelVersionORM)
            .where(ModelVersionORM.status == "active")
            .values(status="retired", retired_at=now)
        )
        await self._s.execute(
            update(ModelVersionORM)
            .where(ModelVersionORM.version == version)
            .values(status="active", promoted_at=now)
        )


# ── ORM ↔ Domain translators ───────────────────────────────────────────────

def _apply_read_controls(profile: PatientProfile) -> PatientProfile:
    """Latest lab per LOINC; active medications only; unresolved conditions."""
    from datetime import date

    active_meds = tuple(
        m for m in profile.medications
        # medications from ORM are already active-only in _orm_to_profile
    )

    latest_labs: dict[str, LabResult] = {}
    for lab in sorted(profile.labs, key=lambda l: l.collected_at):
        latest_labs[lab.loinc] = lab

    active_conditions = profile.conditions

    return PatientProfile(
        patient_id=profile.patient_id,
        demographics=profile.demographics,
        conditions=active_conditions,
        medications=active_meds,
        labs=tuple(latest_labs.values()),
        lifestyle=profile.lifestyle,
        preferences=profile.preferences,
    )


def _profile_to_orm(profile: PatientProfile) -> PatientORM:
    demo = profile.demographics
    orm = PatientORM(
        patient_id=profile.patient_id,
        dob_year=None,    # never store DOB — only age at intake
        sex=demo.sex.value,
        region_code=demo.region_code,
        pregnancy_status=demo.pregnancy_status,
        lactation_status=demo.lactation_status,
        bmi=demo.bmi,
        indoor_occupation=demo.indoor_occupation,
        veiled_dress=demo.veiled_dress,
    )
    orm.conditions  = _condition_orms(profile.patient_id, profile.conditions)
    orm.medications = _medication_orms(profile.patient_id, profile.medications)
    orm.labs        = _lab_orms(profile.patient_id, profile.labs)
    return orm


def _condition_orms(
    patient_id: uuid.UUID, conditions: tuple
) -> list[PatientConditionORM]:
    return [
        PatientConditionORM(
            patient_id=patient_id,
            icd10_code=c.icd10_code,
            snomed_id=c.snomed_id,
            onset_date=c.onset_date,
            source=c.source.value,
        )
        for c in conditions
    ]


def _medication_orms(
    patient_id: uuid.UUID, medications: tuple
) -> list[PatientMedicationORM]:
    return [
        PatientMedicationORM(
            patient_id=patient_id,
            rxnorm_cui=m.rxnorm_cui,
            name=m.name,
            dose_mg=m.dose_mg,
            frequency=m.frequency,
            months_on=m.months_on,
        )
        for m in medications
    ]


def _lab_orms(
    patient_id: uuid.UUID, labs: tuple
) -> list[PatientLabORM]:
    return [
        PatientLabORM(
            patient_id=patient_id,
            loinc=l.loinc,
            value_num=l.value_num,
            unit=l.unit,
            collected_at=l.collected_at,
            reference_low=l.reference_low,
            reference_high=l.reference_high,
            flagged=l.flagged,
        )
        for l in labs
    ]


def _orm_to_profile(orm: PatientORM) -> PatientProfile:
    from datetime import date

    age = 0
    if orm.dob_year:
        age = max(0, date.today().year - orm.dob_year)

    sun_hrs = 1.5 if orm.indoor_occupation else 5.0
    demo = Demographics(
        age=age,
        sex=Sex(orm.sex or "OTHER"),
        region_code=orm.region_code or "UNKNOWN",
        pregnancy_status=orm.pregnancy_status,
        lactation_status=orm.lactation_status,
        bmi=float(orm.bmi) if orm.bmi else None,
        indoor_occupation=orm.indoor_occupation,
        veiled_dress=orm.veiled_dress,
    )
    return PatientProfile(
        patient_id=orm.patient_id,
        demographics=demo,
        conditions=tuple(
            Condition(
                icd10_code=c.icd10_code,
                snomed_id=c.snomed_id,
                onset_date=c.onset_date.date() if c.onset_date else None,
                source=ConditionSource(c.source),
            )
            for c in orm.conditions
            if c.resolved_date is None
        ),
        medications=tuple(
            Medication(
                rxnorm_cui=m.rxnorm_cui,
                name=m.name or "",
                dose_mg=float(m.dose_mg) if m.dose_mg else None,
                frequency=m.frequency,
                months_on=m.months_on or 0,
            )
            for m in orm.medications
            if m.stop_date is None
        ),
        labs=tuple(
            LabResult(
                loinc=l.loinc,
                value_num=float(l.value_num) if l.value_num else 0.0,
                unit=l.unit or "",
                collected_at=l.collected_at or datetime.now(timezone.utc),
                reference_low=float(l.reference_low) if l.reference_low else None,
                reference_high=float(l.reference_high) if l.reference_high else None,
                flagged=l.flagged,
            )
            for l in orm.labs
        ),
        lifestyle=Lifestyle(
            sun_exposure_hrs_wk=sun_hrs,
            diet_pattern="omnivore",
        ),
        preferences=PatientPreferences(),
    )


def _rec_orm_to_dict(r: RecommendationORM) -> dict:
    return {
        "rec_id": str(r.rec_id),
        "nutrient_id": r.nutrient_id,
        "nutrient_name": r.nutrient_name,
        "form": r.form,
        "rank": r.rank,
        "dose": {
            "amount": float(r.dose_amount) if r.dose_amount else None,
            "unit": r.dose_unit,
            "frequency": r.dose_frequency,
            "with_food": r.dose_with_food,
            "ul_pct_used": float(r.dose_ul_pct_used) if r.dose_ul_pct_used else None,
            "cap_applied": r.dose_cap_applied,
        },
        "confidence_score": float(r.confidence_score) if r.confidence_score else None,
        "evidence_grade": r.evidence_grade,
        "requires_clinician": r.requires_clinician,
        "rationale": {
            "why": r.rationale_why,
            "evidence": r.rationale_evidence,
            "safety": r.rationale_safety,
        },
        "warnings": [
            {
                "severity": w.severity,
                "with_agent": w.with_agent,
                "action": w.action,
            }
            for w in r.warnings
        ],
        "served_at": r.served_at.isoformat(),
    }
