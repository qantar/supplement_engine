"""Unit tests for PersonalizationEngine."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

from datetime import datetime, timezone

import pytest

from src.personalization.engine import PersonalizationEngine
from src.shared.models import DRS, LabResult


@pytest.mark.asyncio
async def test_load_longitudinal_priors_from_repo():
    engine = PersonalizationEngine()
    repo = AsyncMock()
    repo.get_last_drs_snapshot = AsyncMock(
        return_value={"vitamin_d3": 0.72, "iron": 0.15}
    )
    priors = await engine.load_longitudinal_priors(uuid.uuid4(), repo)
    assert priors["vitamin_d3"] == 0.72


def test_apply_longitudinal_priors_blends_scores():
    engine = PersonalizationEngine()
    drs_scores = {
        "vitamin_d3": DRS(
            nutrient_id="vitamin_d3",
            p_deficient=0.50,
            baseline=0.30,
            logit_posterior=0.0,
        )
    }
    updated = engine.apply_longitudinal_priors(
        drs_scores, {"vitamin_d3": 0.90}
    )
    assert updated["vitamin_d3"].p_deficient > 0.50


def test_bayesian_update_shifts_toward_low_lab():
    engine = PersonalizationEngine()
    lab = LabResult(
        loinc="1989-3",
        value_num=18,
        unit="ng/mL",
        collected_at=datetime.now(timezone.utc),
        reference_low=30,
        reference_high=80,
    )
    posterior = engine.bayesian_update(0.40, lab)
    assert posterior > 0.40
