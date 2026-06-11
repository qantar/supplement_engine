#!/usr/bin/env python3
"""Load pilot cohort fixtures into Postgres patient realm (dbt dev fallback)."""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.db.engine import get_session, init_db  # noqa: E402
from src.db.repositories import PatientRepository  # noqa: E402
from src.intake.identity import MOCK_SOURCE_SYSTEM  # noqa: E402
from src.intake.pilot_cohort import (  # noqa: E402
    PILOT_COHORT,
    fixture_to_profile,
    hashed_mrn,
)
from src.shared.models import ConditionSource  # noqa: E402


async def _seed_patient(repo: PatientRepository, session, meta, batch_id: str) -> None:
    from src.db.orm_models import PatientORM

    profile = fixture_to_profile(meta)
    existing = await session.get(PatientORM, meta.patient_id)
    if existing is None:
        session.add(PatientORM(
            patient_id=meta.patient_id,
            hashed_mrn=hashed_mrn(meta),
            dob_year=datetime.now(timezone.utc).year - profile.demographics.age,
            sex=profile.demographics.sex.value,
            region_code=profile.demographics.region_code,
            pregnancy_status=profile.demographics.pregnancy_status,
            lactation_status=profile.demographics.lactation_status,
            bmi=profile.demographics.bmi,
            indoor_occupation=profile.demographics.indoor_occupation,
            veiled_dress=profile.demographics.veiled_dress,
        ))
        await session.flush()

    await repo.sync_conditions(
        profile.patient_id,
        profile.conditions,
        source=ConditionSource.WAREHOUSE,
        source_system=MOCK_SOURCE_SYSTEM,
        ingest_batch_id=batch_id,
    )
    await repo.sync_medications(
        profile.patient_id,
        profile.medications,
        source=ConditionSource.WAREHOUSE,
        source_system=MOCK_SOURCE_SYSTEM,
        ingest_batch_id=batch_id,
    )
    for lab in profile.labs:
        await repo.append_lab(
            profile.patient_id,
            lab,
            source=ConditionSource.WAREHOUSE,
            source_system=MOCK_SOURCE_SYSTEM,
            ingest_batch_id=batch_id,
        )


async def main() -> None:
    init_db()
    batch_id = f"seed-{datetime.now(timezone.utc).strftime('%Y%m%d')}"

    async with get_session() as session:
        repo = PatientRepository(session)
        for meta in PILOT_COHORT:
            await _seed_patient(repo, session, meta, batch_id)
        await repo.log_ingest_batch(
            batch_id,
            MOCK_SOURCE_SYSTEM,
            row_counts={"patients": len(PILOT_COHORT)},
            dbt_run_id="seed_script",
        )

    print(f"Seeded {len(PILOT_COHORT)} pilot patients:")
    for meta in PILOT_COHORT:
        print(f"  {meta.source_key:14}  {meta.patient_id}  {meta.clinical_intent}")


if __name__ == "__main__":
    asyncio.run(main())
