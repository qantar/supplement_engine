"""
SQLAlchemy ORM models.

These are the database representation layer — completely separate from the
domain models in shared/models.py.

The separation matters:
  - Domain models (frozen dataclasses) = what the business logic speaks
  - ORM models = what the database speaks
  - Repositories = the translators between them

No business logic here. No imports from src.core or src.safety.
Just columns, relationships, and constraints — mirroring postgres_init.sql exactly.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey,
    Integer, Numeric, String, Text, event,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


# ── Patients ───────────────────────────────────────────────────────────────

class PatientORM(Base):
    __tablename__ = "patients"

    patient_id:       Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hashed_mrn:       Mapped[str | None] = mapped_column(Text)
    dob_year:         Mapped[int | None] = mapped_column(Integer)
    sex:              Mapped[str | None] = mapped_column(String(10))
    region_code:      Mapped[str | None] = mapped_column(String(20))
    pregnancy_status: Mapped[bool]       = mapped_column(Boolean, default=False)
    lactation_status: Mapped[bool]       = mapped_column(Boolean, default=False)
    bmi:              Mapped[float | None] = mapped_column(Numeric(5, 2))
    indoor_occupation: Mapped[bool]      = mapped_column(Boolean, default=False)
    veiled_dress:     Mapped[bool]       = mapped_column(Boolean, default=False)
    consent_version:  Mapped[str | None] = mapped_column(Text)
    created_at:       Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at:       Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # relationships
    conditions:   Mapped[list[PatientConditionORM]]  = relationship(back_populates="patient", cascade="all, delete-orphan")
    medications:  Mapped[list[PatientMedicationORM]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    labs:         Mapped[list[PatientLabORM]]        = relationship(back_populates="patient", cascade="all, delete-orphan")
    recommendations: Mapped[list[RecommendationORM]] = relationship(back_populates="patient")


class PatientConditionORM(Base):
    __tablename__ = "patient_conditions"

    id:           Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id:   Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.patient_id", ondelete="CASCADE"), nullable=False)
    icd10_code:   Mapped[str]       = mapped_column(Text, nullable=False)
    snomed_id:    Mapped[int | None] = mapped_column(BigInteger)
    onset_date:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source:       Mapped[str]       = mapped_column(String(20), default="self")
    ingest_batch_id: Mapped[str | None] = mapped_column(Text)
    source_system:   Mapped[str | None] = mapped_column(Text)
    ingested_at:     Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at:   Mapped[datetime]  = mapped_column(DateTime(timezone=True), server_default=func.now())

    patient: Mapped[PatientORM] = relationship(back_populates="conditions")

    __table_args__ = (
        CheckConstraint(
            "source IN ('self','ehr','clinician','warehouse')",
            name="ck_condition_source",
        ),
    )


class PatientMedicationORM(Base):
    __tablename__ = "patient_medications"

    id:          Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id:  Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), ForeignKey("patients.patient_id", ondelete="CASCADE"), nullable=False)
    rxnorm_cui:  Mapped[str]        = mapped_column(Text, nullable=False)
    name:        Mapped[str | None] = mapped_column(Text)
    dose_mg:     Mapped[float | None] = mapped_column(Numeric(10, 3))
    frequency:   Mapped[str | None] = mapped_column(Text)
    months_on:   Mapped[int]        = mapped_column(Integer, default=0)
    start_date:  Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stop_date:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ingest_batch_id: Mapped[str | None] = mapped_column(Text)
    source_system:   Mapped[str | None] = mapped_column(Text)
    ingested_at:     Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at:  Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now())

    patient: Mapped[PatientORM] = relationship(back_populates="medications")


class PatientLabORM(Base):
    __tablename__ = "patient_labs"

    id:             Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id:     Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), ForeignKey("patients.patient_id", ondelete="CASCADE"), nullable=False)
    loinc:          Mapped[str]        = mapped_column(Text, nullable=False)
    value_num:      Mapped[float | None] = mapped_column(Numeric(12, 4))
    unit:           Mapped[str | None] = mapped_column(Text)
    collected_at:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reference_low:  Mapped[float | None] = mapped_column(Numeric(12, 4))
    reference_high: Mapped[float | None] = mapped_column(Numeric(12, 4))
    flagged:        Mapped[bool]       = mapped_column(Boolean, default=False)
    ingest_batch_id: Mapped[str | None] = mapped_column(Text)
    source_system:   Mapped[str | None] = mapped_column(Text)
    ingested_at:     Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at:     Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now())

    patient: Mapped[PatientORM] = relationship(back_populates="labs")


# ── Recommendations ────────────────────────────────────────────────────────

class RecommendationORM(Base):
    __tablename__ = "recommendations"

    rec_id:               Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id:           Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.patient_id"), nullable=False)
    session_id:           Mapped[str]       = mapped_column(Text, nullable=False)
    nutrient_id:          Mapped[str]       = mapped_column(Text, nullable=False)
    nutrient_name:        Mapped[str | None] = mapped_column(Text)
    form:                 Mapped[str | None] = mapped_column(Text)
    dose_amount:          Mapped[float | None] = mapped_column(Numeric(10, 3))
    dose_unit:            Mapped[str | None] = mapped_column(Text)
    dose_frequency:       Mapped[str | None] = mapped_column(Text)
    dose_with_food:       Mapped[bool]      = mapped_column(Boolean, default=True)
    dose_ul_pct_used:     Mapped[float | None] = mapped_column(Numeric(5, 2))
    dose_cap_applied:     Mapped[bool]      = mapped_column(Boolean, default=False)
    confidence_score:     Mapped[float | None] = mapped_column(Numeric(5, 4))
    evidence_grade:       Mapped[str | None] = mapped_column(String(1))
    requires_clinician:   Mapped[bool]      = mapped_column(Boolean, default=False)
    rationale_why:        Mapped[str | None] = mapped_column(Text)
    rationale_evidence:   Mapped[str | None] = mapped_column(Text)
    rationale_safety:     Mapped[str | None] = mapped_column(Text)
    model_version:        Mapped[str]       = mapped_column(Text, nullable=False)
    evidence_snapshot_id: Mapped[str]       = mapped_column(Text, nullable=False)
    rank:                 Mapped[int | None] = mapped_column(Integer)
    served_at:            Mapped[datetime]  = mapped_column(DateTime(timezone=True), server_default=func.now())

    patient:  Mapped[PatientORM] = relationship(back_populates="recommendations")
    warnings: Mapped[list[RecommendationWarningORM]] = relationship(back_populates="recommendation", cascade="all, delete-orphan")
    feedback: Mapped[list[RecFeedbackORM]] = relationship(back_populates="recommendation")

    __table_args__ = (
        CheckConstraint("evidence_grade IN ('A','B','C','D')", name="ck_rec_grade"),
    )


class RecommendationWarningORM(Base):
    __tablename__ = "recommendation_warnings"

    id:         Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rec_id:     Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("recommendations.rec_id", ondelete="CASCADE"), nullable=False)
    severity:   Mapped[str | None] = mapped_column(Text)
    with_agent: Mapped[str | None] = mapped_column(Text)
    action:     Mapped[str | None] = mapped_column(Text)
    mechanism:  Mapped[str | None] = mapped_column(Text)

    recommendation: Mapped[RecommendationORM] = relationship(back_populates="warnings")


# ── Sessions ───────────────────────────────────────────────────────────────

class RecommendationSessionORM(Base):
    """
    One row per pipeline evaluation — groups recommendations by session_id.
    Stores session-level metadata: suppressed count, escalation, execution time.
    """
    __tablename__ = "recommendation_sessions"

    session_id:           Mapped[str]       = mapped_column(Text, primary_key=True)
    patient_id:           Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.patient_id"), nullable=False)
    model_version:        Mapped[str]       = mapped_column(Text, nullable=False)
    evidence_snapshot_id: Mapped[str]       = mapped_column(Text, nullable=False)
    requires_clinician:   Mapped[bool]      = mapped_column(Boolean, default=False)
    clinician_handoff:    Mapped[str | None] = mapped_column(Text)
    next_review_weeks:    Mapped[int]       = mapped_column(Integer, default=12)
    suppressed_count:     Mapped[int]       = mapped_column(Integer, default=0)
    suppressed_detail:    Mapped[dict | None] = mapped_column(JSONB)   # [{nutrient_id, reason}]
    drs_snapshot:         Mapped[dict | None] = mapped_column(JSONB)
    execution_ms:         Mapped[int | None] = mapped_column(Integer)
    served_at:            Mapped[datetime]  = mapped_column(DateTime(timezone=True), server_default=func.now())


# ── Feedback / Outcomes ────────────────────────────────────────────────────

class RecFeedbackORM(Base):
    __tablename__ = "rec_feedback"

    id:         Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rec_id:     Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("recommendations.rec_id"), nullable=False)
    session_id: Mapped[str | None] = mapped_column(Text)
    source:     Mapped[str]       = mapped_column(String(20), default="user")
    action:     Mapped[str]       = mapped_column(String(30), nullable=False)
    notes:      Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime]  = mapped_column(DateTime(timezone=True), server_default=func.now())

    recommendation: Mapped[RecommendationORM] = relationship(back_populates="feedback")

    __table_args__ = (
        CheckConstraint("source IN ('user','clinician')", name="ck_feedback_source"),
        CheckConstraint(
            "action IN ('accepted','rejected','modified','adverse_event')",
            name="ck_feedback_action",
        ),
    )


# ── Audit log ──────────────────────────────────────────────────────────────

class AuditLogORM(Base):
    """
    Append-only. INSERT only — rules enforced at DB level in postgres_init.sql.
    7-year retention. Contains input_hash for full reproducibility.
    """
    __tablename__ = "audit_log"

    id:                   Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id:           Mapped[str | None] = mapped_column(Text)
    patient_id:           Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    model_version:        Mapped[str | None] = mapped_column(Text)
    evidence_snapshot_id: Mapped[str | None] = mapped_column(Text)
    input_hash:           Mapped[str | None] = mapped_column(Text)       # SHA-256 of request JSON
    output_summary:       Mapped[dict | None] = mapped_column(JSONB)     # nutrient_ids + scores
    suppressed_count:     Mapped[int | None] = mapped_column(Integer)
    requires_clinician:   Mapped[bool | None] = mapped_column(Boolean)
    execution_ms:         Mapped[int | None] = mapped_column(Integer)
    created_at:           Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now())


# ── Evidence snapshots ─────────────────────────────────────────────────────

class EvidenceSnapshotORM(Base):
    """
    Captures Neo4j KG state at the time a session was served.
    Enables full reproducibility for regulatory audit.
    """
    __tablename__ = "evidence_snapshots"

    snapshot_id:   Mapped[str]      = mapped_column(Text, primary_key=True)
    kg_commit_sha: Mapped[str | None] = mapped_column(Text)
    captured_at:   Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    contents:      Mapped[dict | None] = mapped_column(JSONB)


# ── Ingest batches ─────────────────────────────────────────────────────────

class IngestBatchORM(Base):
    __tablename__ = "ingest_batches"

    batch_id:      Mapped[str]      = mapped_column(Text, primary_key=True)
    source_system: Mapped[str]      = mapped_column(Text, nullable=False)
    row_counts:    Mapped[dict | None] = mapped_column(JSONB)
    dbt_run_id:    Mapped[str | None] = mapped_column(Text)
    completed_at:  Mapped[datetime]  = mapped_column(DateTime(timezone=True), server_default=func.now())


# ── Model versions ─────────────────────────────────────────────────────────

class ModelVersionORM(Base):
    __tablename__ = "model_versions"

    version:             Mapped[str]      = mapped_column(Text, primary_key=True)
    training_date:       Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    performance_metrics: Mapped[dict | None] = mapped_column(JSONB)
    status:              Mapped[str]      = mapped_column(String(20), default="shadow")
    promoted_at:         Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retired_at:          Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("status IN ('shadow','active','retired')", name="ck_model_status"),
    )
