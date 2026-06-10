"""Phase 2a unit tests: ProfileValidator and read-time controls."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from src.db.repositories import _apply_read_controls
from src.intake.identity import compute_hashed_mrn, MOCK_SOURCE_SYSTEM, T2DM_RIYADH_SOURCE_KEY
from src.intake.validator import ProfileValidator
from src.shared.models import (
    Condition, ConditionSource, Demographics, LabResult, Medication,
    PatientProfile, Sex,
)


def _profile(**kwargs) -> PatientProfile:
    defaults = dict(
        patient_id=uuid.uuid4(),
        demographics=Demographics(age=52, sex=Sex.F, region_code="SA-01", bmi=31.0),
        conditions=(),
        medications=(),
        labs=(),
    )
    defaults.update(kwargs)
    return PatientProfile(**defaults)


def test_compute_hashed_mrn_stable():
    h1 = compute_hashed_mrn(MOCK_SOURCE_SYSTEM, T2DM_RIYADH_SOURCE_KEY)
    h2 = compute_hashed_mrn(MOCK_SOURCE_SYSTEM, T2DM_RIYADH_SOURCE_KEY)
    assert h1 == h2
    assert len(h1) == 64


def test_validator_excludes_invalid_icd10():
    profile = _profile(
        conditions=(
            Condition(icd10_code="E11.9", source=ConditionSource.EHR),
            Condition(icd10_code="BAD", source=ConditionSource.EHR),
        ),
    )
    result = ProfileValidator().validate(profile)
    assert len(result.profile.conditions) == 1
    assert result.profile.conditions[0].icd10_code == "E11.9"
    assert result.excluded_conditions == 1


def test_validator_excludes_invalid_rxnorm_and_loinc():
    profile = _profile(
        medications=(Medication(rxnorm_cui="6809", name="Metformin"),),
        labs=(
            LabResult(loinc="1989-3", value_num=18, unit="ng/mL", collected_at=datetime.now(timezone.utc)),
            LabResult(loinc="INVALID", value_num=1, unit="x", collected_at=datetime.now(timezone.utc)),
        ),
    )
    result = ProfileValidator().validate(profile)
    assert len(result.profile.medications) == 1
    assert len(result.profile.labs) == 1
    assert result.excluded_labs == 1


def test_read_controls_keeps_latest_lab_per_loinc():
    t1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    t2 = datetime(2026, 2, 1, tzinfo=timezone.utc)
    profile = _profile(
        labs=(
            LabResult(loinc="1989-3", value_num=18, unit="ng/mL", collected_at=t1),
            LabResult(loinc="1989-3", value_num=12, unit="ng/mL", collected_at=t2),
        ),
    )
    controlled = _apply_read_controls(profile)
    assert len(controlled.labs) == 1
    assert controlled.labs[0].value_num == 12
