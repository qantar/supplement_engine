"""Read-time profile validation before scoring."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from src.shared.models import (
    Condition, LabResult, Medication, PatientProfile,
)

logger = logging.getLogger(__name__)

_ICD10_PATTERN = re.compile(r"^[A-Z][0-9][0-9A-Z](\.[0-9A-Z]{1,4})?$")
_RXNORM_PATTERN = re.compile(r"^[0-9]+$")
_LOINC_PATTERN = re.compile(r"^[0-9]+(-[0-9])?$")


@dataclass(frozen=True)
class ValidationResult:
    profile: PatientProfile
    warnings: tuple[str, ...] = field(default_factory=tuple)
    excluded_conditions: int = 0
    excluded_medications: int = 0
    excluded_labs: int = 0


class ProfileValidator:
    """Apply read-time controls: vocab checks and required demographics."""

    def validate(self, profile: PatientProfile) -> ValidationResult:
        warnings: list[str] = []
        demo = profile.demographics

        if not demo.region_code or demo.region_code == "UNKNOWN":
            warnings.append("region_code missing; using UNKNOWN")
        if demo.age <= 0 and demo.bmi is None:
            warnings.append("age and bmi both missing; scoring may be imprecise")

        valid_conditions: list[Condition] = []
        excluded_c = 0
        for c in profile.conditions:
            if not _ICD10_PATTERN.match(c.icd10_code.upper()):
                excluded_c += 1
                warnings.append(f"excluded condition with invalid ICD-10: {c.icd10_code}")
                continue
            valid_conditions.append(c)

        valid_meds: list[Medication] = []
        excluded_m = 0
        for m in profile.medications:
            if not _RXNORM_PATTERN.match(m.rxnorm_cui):
                excluded_m += 1
                warnings.append(f"excluded medication with invalid RxNorm: {m.rxnorm_cui}")
                continue
            valid_meds.append(m)

        valid_labs: list[LabResult] = []
        excluded_l = 0
        for lab in profile.labs:
            if not _LOINC_PATTERN.match(lab.loinc):
                excluded_l += 1
                warnings.append(f"excluded lab with invalid LOINC: {lab.loinc}")
                continue
            valid_labs.append(lab)

        cleaned = PatientProfile(
            patient_id=profile.patient_id,
            demographics=demo,
            conditions=tuple(valid_conditions),
            medications=tuple(valid_meds),
            labs=tuple(valid_labs),
            lifestyle=profile.lifestyle,
            preferences=profile.preferences,
        )

        if warnings:
            for w in warnings:
                logger.info("ProfileValidator: patient=%s %s", profile.patient_id, w)

        return ValidationResult(
            profile=cleaned,
            warnings=tuple(warnings),
            excluded_conditions=excluded_c,
            excluded_medications=excluded_m,
            excluded_labs=excluded_l,
        )
