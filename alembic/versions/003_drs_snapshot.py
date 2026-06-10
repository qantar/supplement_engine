"""Add drs_snapshot to recommendation_sessions for longitudinal personalization."""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003_drs_snapshot"
down_revision: Union[str, None] = "002_phase2_ingest"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE recommendation_sessions "
        "ADD COLUMN IF NOT EXISTS drs_snapshot JSONB"
    )


def downgrade() -> None:
    op.drop_column("recommendation_sessions", "drs_snapshot")
