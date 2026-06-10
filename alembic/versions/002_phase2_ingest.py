"""Phase 2a: ingest audit columns, warehouse source, ingest_batches.

Revision ID: 002_phase2_ingest
Revises: 001_initial
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002_phase2_ingest"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _drop_source_check_constraints() -> None:
    """Drop source CHECK whether from Alembic 001 or postgres_init inline constraint."""
    op.execute("ALTER TABLE patient_conditions DROP CONSTRAINT IF EXISTS ck_condition_source")
    op.execute(
        "ALTER TABLE patient_conditions DROP CONSTRAINT IF EXISTS patient_conditions_source_check"
    )


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS landing")

    _drop_source_check_constraints()
    op.create_check_constraint(
        "ck_condition_source",
        "patient_conditions",
        "source IN ('self', 'ehr', 'clinician', 'warehouse')",
    )

    for table in ("patient_conditions", "patient_medications", "patient_labs"):
        op.execute(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS ingest_batch_id TEXT"
        )
        op.execute(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS source_system TEXT"
        )
        op.execute(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS ingested_at "
            f"TIMESTAMPTZ DEFAULT NOW()"
        )

    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_patients_hashed_mrn
        ON patients (hashed_mrn)
        WHERE hashed_mrn IS NOT NULL
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ingest_batches (
            batch_id TEXT PRIMARY KEY,
            source_system TEXT NOT NULL,
            row_counts JSONB,
            dbt_run_id TEXT,
            completed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ingest_batches")
    op.execute("DROP INDEX IF EXISTS idx_patients_hashed_mrn")

    for table in ("patient_labs", "patient_medications", "patient_conditions"):
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS ingested_at")
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS source_system")
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS ingest_batch_id")

    op.drop_constraint("ck_condition_source", "patient_conditions", type_="check")
    op.create_check_constraint(
        "ck_condition_source",
        "patient_conditions",
        "source IN ('self', 'ehr', 'clinician')",
    )
    op.execute("DROP SCHEMA IF EXISTS landing CASCADE")
