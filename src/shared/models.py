"""
Domain models — immutable dataclasses as the single source of truth.
Every service speaks this language. No dict-passing, no stringly-typed chaos.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional
from uuid import UUID


# ── Enums ──────────────────────────────────────────────────────────────────

class Sex(str, Enum):
    M = "M"
    F = "F"
    OTHER = "OTHER"

class ConditionSource(str, Enum):
    SELF = "self"
    EHR = "ehr"
    CLINICIAN = "clinician"
    WAREHOUSE = "warehouse"

class WarningSeverity(str, Enum):
    CONTRAINDICATED = "contraindicated"
    MAJOR = "major"
    MODERATE = "moderate"
    MINOR = "minor"

class FeedbackAction(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    MODIFIED = "modified"
    ADVERSE_EVENT = "adverse_event"

class EvidenceGrade(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


# ── Patient domain ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Demographics:
    age: int
    sex: Sex
    region_code: str                       # ISO 3166-2  e.g. SA-01
    ethnicity: Optional[str] = None
    pregnancy_status: bool = False
    lactation_status: bool = False
    bmi: Optional[float] = None
    fitzpatrick_skin_type: Optional[int] = None
    indoor_occupation: bool = False
    veiled_dress: bool = False             # KSA-specific prior modifier

@dataclass(frozen=True)
class Condition:
    icd10_code: str
    snomed_id: Optional[int] = None
    onset_date: Optional[date] = None
    source: ConditionSource = ConditionSource.SELF

@dataclass(frozen=True)
class Medication:
    rxnorm_cui: str
    name: str
    dose_mg: Optional[float] = None
    frequency: Optional[str] = None
    months_on: int = 0                     # drives duration_factor in DRS

@dataclass(frozen=True)
class LabResult:
    loinc: str
    value_num: float
    unit: str
    collected_at: datetime
    reference_low: Optional[float] = None
    reference_high: Optional[float] = None
    flagged: bool = False

@dataclass(frozen=True)
class Lifestyle:
    diet_pattern: str = "omnivore"
    alcohol_units_wk: float = 0.0
    smoking: bool = False
    sun_exposure_hrs_wk: float = 5.0
    activity_level: str = "moderate"
    sleep_hrs: float = 7.0

@dataclass(frozen=True)
class PatientPreferences:
    vegan: bool = False
    halal: bool = True
    kosher: bool = False
    budget_tier: str = "standard"

@dataclass(frozen=True)
class PatientProfile:
    patient_id: UUID
    demographics: Demographics
    conditions: tuple[Condition, ...] = field(default_factory=tuple)
    medications: tuple[Medication, ...] = field(default_factory=tuple)
    labs: tuple[LabResult, ...] = field(default_factory=tuple)
    lifestyle: Lifestyle = field(default_factory=Lifestyle)
    preferences: PatientPreferences = field(default_factory=PatientPreferences)

    def lab_for(self, loinc: str) -> Optional[LabResult]:
        matches = [l for l in self.labs if l.loinc == loinc]
        return max(matches, key=lambda l: l.collected_at) if matches else None

    def has_condition(self, icd10_prefix: str) -> bool:
        return any(c.icd10_code.startswith(icd10_prefix) for c in self.conditions)

    def has_medication(self, rxnorm_cui: str) -> bool:
        return any(m.rxnorm_cui == rxnorm_cui for m in self.medications)


# ── Scoring domain ─────────────────────────────────────────────────────────

@dataclass
class ContributorFactor:
    label: str
    lr: float
    log_lr: float
    source: str      # "condition:E11.9" | "medication:6809" | "lab:1989-3"

@dataclass
class DRS:
    """Deficiency Risk Score — posterior P(deficient | patient) in [0,1]."""
    nutrient_id: str
    p_deficient: float
    baseline: float
    logit_posterior: float
    contributors: list[ContributorFactor] = field(default_factory=list)
    lab_dominated: bool = False


# ── Recommendation domain ──────────────────────────────────────────────────

@dataclass(frozen=True)
class Dose:
    amount: float
    unit: str
    frequency: str
    with_food: bool = True
    duration: str = "ongoing"
    ul_pct_used: float = 0.0
    cap_applied: bool = False

@dataclass
class InteractionWarning:
    severity: WarningSeverity
    with_agent: str
    action: str
    mechanism: Optional[str] = None

@dataclass
class Candidate:
    nutrient_id: str
    drs: DRS
    dose: Optional[Dose] = None
    confidence_score: float = 0.0
    evidence_grade: EvidenceGrade = EvidenceGrade.D
    warnings: list[InteractionWarning] = field(default_factory=list)
    blocked: bool = False
    block_reason: Optional[str] = None
    guideline_triggered: bool = False
    rank_score: float = 0.0

@dataclass(frozen=True)
class RecommendationOutput:
    rec_id: UUID
    session_id: str
    patient_id: UUID
    nutrient_id: str
    nutrient_name: str
    form: str
    dose: Dose
    rank: int
    confidence_score: float
    evidence_grade: EvidenceGrade
    warnings: tuple[InteractionWarning, ...]
    requires_clinician: bool
    rationale_why: str
    rationale_evidence: str
    rationale_safety: str
    model_version: str
    evidence_snapshot_id: str
    served_at: datetime

@dataclass
class RecommendationSession:
    session_id: str
    patient_id: UUID
    model_version: str
    evidence_snapshot_id: str
    recommendations: list[RecommendationOutput]
    suppressed: list[dict]
    requires_clinician: bool
    clinician_handoff: Optional[str]
    next_review_weeks: int
    served_at: datetime
    evidence_snapshot: Optional["EvidenceSnapshot"] = None
    drs_snapshot: Optional[dict[str, float]] = None


@dataclass(frozen=True)
class EvidenceSnapshot:
    """KG state captured at recommendation serve time."""
    snapshot_id: str
    kg_version: str
    contents: dict


# ── Knowledge graph domain ─────────────────────────────────────────────────

@dataclass(frozen=True)
class KGEdge:
    rel_type: str
    source_id: str
    target_id: str
    lr: float
    lr_ci_lower: float
    lr_ci_upper: float
    mechanism: Optional[str] = None
    onset_months: Optional[int] = None
    severity: Optional[WarningSeverity] = None
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)
    grade_weight: float = 0.5

@dataclass(frozen=True)
class NutrientMeta:
    nutrient_id: str
    name: str
    form: str
    rda: float
    ear: float
    ul: float
    dose_unit: str
    bioavailability_factor: float = 1.0
    loinc_codes: tuple[str, ...] = field(default_factory=tuple)
