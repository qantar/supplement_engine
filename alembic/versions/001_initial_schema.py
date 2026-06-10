"""Initial schema — mirrors postgres_init.sql and orm_models.py.

Revision ID: 001_initial
Revises:
Create Date: 2026-06-05

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if "patients" in inspector.get_table_names():
        _seed_model_version()
        return

    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm"')

    op.create_table(
        "patients",
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("hashed_mrn", sa.Text()),
        sa.Column("dob_year", sa.Integer()),
        sa.Column("sex", sa.String(10)),
        sa.Column("region_code", sa.String(20)),
        sa.Column("pregnancy_status", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("lactation_status", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("bmi", sa.Numeric(5, 2)),
        sa.Column("indoor_occupation", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("veiled_dress", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("consent_version", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint("sex IN ('M', 'F', 'OTHER')", name="ck_patients_sex"),
    )

    op.create_table(
        "patient_conditions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("patients.patient_id", ondelete="CASCADE"), nullable=False),
        sa.Column("icd10_code", sa.Text(), nullable=False),
        sa.Column("snomed_id", sa.BigInteger()),
        sa.Column("onset_date", sa.DateTime(timezone=True)),
        sa.Column("resolved_date", sa.DateTime(timezone=True)),
        sa.Column("source", sa.String(20), nullable=False, server_default="self"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint("source IN ('self', 'ehr', 'clinician')", name="ck_condition_source"),
    )
    op.create_index("idx_conditions_patient", "patient_conditions", ["patient_id"])
    op.create_index("idx_conditions_icd10", "patient_conditions", ["icd10_code"])

    op.create_table(
        "patient_medications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("patients.patient_id", ondelete="CASCADE"), nullable=False),
        sa.Column("rxnorm_cui", sa.Text(), nullable=False),
        sa.Column("name", sa.Text()),
        sa.Column("dose_mg", sa.Numeric(10, 3)),
        sa.Column("frequency", sa.Text()),
        sa.Column("months_on", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("start_date", sa.DateTime(timezone=True)),
        sa.Column("stop_date", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_medications_patient", "patient_medications", ["patient_id"])
    op.create_index("idx_medications_rxnorm", "patient_medications", ["rxnorm_cui"])

    op.create_table(
        "patient_labs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("patients.patient_id", ondelete="CASCADE"), nullable=False),
        sa.Column("loinc", sa.Text(), nullable=False),
        sa.Column("value_num", sa.Numeric(12, 4)),
        sa.Column("unit", sa.Text()),
        sa.Column("collected_at", sa.DateTime(timezone=True)),
        sa.Column("reference_low", sa.Numeric(12, 4)),
        sa.Column("reference_high", sa.Numeric(12, 4)),
        sa.Column("flagged", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_labs_patient", "patient_labs", ["patient_id"])
    op.create_index("idx_labs_loinc", "patient_labs", ["loinc"])

    op.create_table(
        "recommendation_sessions",
        sa.Column("session_id", sa.Text(), primary_key=True),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("patients.patient_id"), nullable=False),
        sa.Column("model_version", sa.Text(), nullable=False),
        sa.Column("evidence_snapshot_id", sa.Text(), nullable=False),
        sa.Column("requires_clinician", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("clinician_handoff", sa.Text()),
        sa.Column("next_review_weeks", sa.Integer(), nullable=False, server_default="12"),
        sa.Column("suppressed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("suppressed_detail", postgresql.JSONB()),
        sa.Column("execution_ms", sa.Integer()),
        sa.Column("served_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_sessions_patient", "recommendation_sessions", ["patient_id"])

    op.create_table(
        "recommendations",
        sa.Column("rec_id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("patients.patient_id"), nullable=False),
        sa.Column("session_id", sa.Text(),
                  sa.ForeignKey("recommendation_sessions.session_id"), nullable=False),
        sa.Column("nutrient_id", sa.Text(), nullable=False),
        sa.Column("nutrient_name", sa.Text()),
        sa.Column("form", sa.Text()),
        sa.Column("dose_amount", sa.Numeric(10, 3)),
        sa.Column("dose_unit", sa.Text()),
        sa.Column("dose_frequency", sa.Text()),
        sa.Column("dose_with_food", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("dose_ul_pct_used", sa.Numeric(5, 2)),
        sa.Column("dose_cap_applied", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("confidence_score", sa.Numeric(5, 4)),
        sa.Column("evidence_grade", sa.String(1)),
        sa.Column("requires_clinician", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("rationale_why", sa.Text()),
        sa.Column("rationale_evidence", sa.Text()),
        sa.Column("rationale_safety", sa.Text()),
        sa.Column("model_version", sa.Text(), nullable=False),
        sa.Column("evidence_snapshot_id", sa.Text(), nullable=False),
        sa.Column("rank", sa.Integer()),
        sa.Column("served_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint("evidence_grade IN ('A','B','C','D')", name="ck_rec_grade"),
    )
    op.create_index("idx_recs_patient", "recommendations", ["patient_id"])
    op.create_index("idx_recs_session", "recommendations", ["session_id"])

    op.execute("""
        CREATE OR REPLACE RULE no_update_recommendations AS
            ON UPDATE TO recommendations DO INSTEAD NOTHING
    """)

    op.create_table(
        "recommendation_warnings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("rec_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("recommendations.rec_id", ondelete="CASCADE"), nullable=False),
        sa.Column("severity", sa.Text()),
        sa.Column("with_agent", sa.Text()),
        sa.Column("action", sa.Text()),
        sa.Column("mechanism", sa.Text()),
    )

    op.create_table(
        "rec_feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("rec_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("recommendations.rec_id"), nullable=False),
        sa.Column("session_id", sa.Text()),
        sa.Column("source", sa.String(20), nullable=False, server_default="user"),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint("source IN ('user', 'clinician')", name="ck_feedback_source"),
        sa.CheckConstraint(
            "action IN ('accepted','rejected','modified','adverse_event')",
            name="ck_feedback_action",
        ),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("session_id", sa.Text()),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True)),
        sa.Column("model_version", sa.Text()),
        sa.Column("evidence_snapshot_id", sa.Text()),
        sa.Column("input_hash", sa.Text(), nullable=False),
        sa.Column("output_summary", postgresql.JSONB()),
        sa.Column("suppressed_count", sa.Integer()),
        sa.Column("requires_clinician", sa.Boolean()),
        sa.Column("execution_ms", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_audit_session", "audit_log", ["session_id"])

    op.execute("""
        CREATE OR REPLACE RULE no_delete_audit AS ON DELETE TO audit_log DO INSTEAD NOTHING
    """)
    op.execute("""
        CREATE OR REPLACE RULE no_update_audit AS ON UPDATE TO audit_log DO INSTEAD NOTHING
    """)

    op.create_table(
        "evidence_snapshots",
        sa.Column("snapshot_id", sa.Text(), primary_key=True),
        sa.Column("kg_commit_sha", sa.Text()),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("contents", postgresql.JSONB()),
    )

    op.create_table(
        "model_versions",
        sa.Column("version", sa.Text(), primary_key=True),
        sa.Column("training_date", sa.DateTime(timezone=True)),
        sa.Column("performance_metrics", postgresql.JSONB()),
        sa.Column("status", sa.String(20), nullable=False, server_default="shadow"),
        sa.Column("promoted_at", sa.DateTime(timezone=True)),
        sa.Column("retired_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('shadow','active','retired')", name="ck_model_status"),
    )

    _seed_model_version()


def _seed_model_version() -> None:
    op.execute("""
        INSERT INTO model_versions (version, training_date, status, performance_metrics)
        VALUES (
            'rec-engine-1.0.0',
            NOW(),
            'active',
            '{"note": "Phase 1 — Bayesian DRS + deterministic safety gate, rules-only"}'::jsonb
        )
        ON CONFLICT (version) DO NOTHING
    """)


def downgrade() -> None:
    op.drop_table("model_versions")
    op.drop_table("evidence_snapshots")
    op.execute("DROP RULE IF EXISTS no_update_audit ON audit_log")
    op.execute("DROP RULE IF EXISTS no_delete_audit ON audit_log")
    op.drop_table("audit_log")
    op.drop_table("rec_feedback")
    op.drop_table("recommendation_warnings")
    op.execute("DROP RULE IF EXISTS no_update_recommendations ON recommendations")
    op.drop_table("recommendations")
    op.drop_table("recommendation_sessions")
    op.drop_table("patient_labs")
    op.drop_table("patient_medications")
    op.drop_table("patient_conditions")
    op.drop_table("patients")
