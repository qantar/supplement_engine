"""
Unit tests for core scoring logic.
No Neo4j needed — all graph calls are mocked.
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.candidate_generator import CandidateGenerator, ConfidenceCompositor, DoseOptimizer
from src.explain.explain_service import ExplainService, _format_ul_pct
from src.core.deficiency_risk_scorer import DeficiencyRiskScorer, _logit, _sigmoid, _duration_factor, _lab_likelihood_ratio
from src.safety.safety_engine import SafetyEngine, _format_dose_amount
from src.shared.models import (
    Candidate, Condition, ConditionSource, Demographics, Dose, DRS,
    EvidenceGrade, KGEdge, LabResult, Lifestyle, Medication,
    NutrientMeta, PatientPreferences, PatientProfile, Sex, WarningSeverity,
    ContributorFactor,
)


# ── Fixtures ────────────────────────────────────────────────────────────────

def make_patient(
    age=52, sex=Sex.F, region="SA-01", bmi=29.7,
    indoor=True, veiled=True, conditions=(), medications=(), labs=(),
) -> PatientProfile:
    return PatientProfile(
        patient_id=uuid.uuid4(),
        demographics=Demographics(
            age=age, sex=sex, region_code=region, bmi=bmi,
            indoor_occupation=indoor, veiled_dress=veiled,
        ),
        conditions=tuple(conditions),
        medications=tuple(medications),
        labs=tuple(labs),
        lifestyle=Lifestyle(sun_exposure_hrs_wk=2.0),
        preferences=PatientPreferences(),
    )

def make_kg(
    baseline=0.30,
    condition_edges=None,
    depletion_edges=None,
    interaction_edges=None,
    antagonist_pairs=None,
    nutrient_meta=None,
) -> MagicMock:
    kg = MagicMock()
    kg.get_baseline_prevalence = AsyncMock(return_value=baseline)
    kg.get_condition_edges = AsyncMock(return_value=condition_edges or [])
    kg.get_depletion_edges = AsyncMock(return_value=depletion_edges or [])
    kg.get_interaction_edges = AsyncMock(return_value=interaction_edges or [])
    kg.get_antagonist_pairs = AsyncMock(return_value=antagonist_pairs or [])
    kg.get_all_nutrient_ids = AsyncMock(return_value=["vitamin_d3"])
    kg.get_guideline = AsyncMock(return_value=None)
    kg.get_contraindications = AsyncMock(return_value=[])
    kg.get_nutrient_meta = AsyncMock(return_value=nutrient_meta or NutrientMeta(
        nutrient_id="vitamin_d3", name="Vitamin D3", form="cholecalciferol",
        rda=600, ear=400, ul=4000, dose_unit="IU",
        bioavailability_factor=1.0, loinc_codes=("1989-3",),
    ))
    return kg


# ── Math helpers ────────────────────────────────────────────────────────────

def test_logit_sigmoid_are_inverses():
    for p in [0.1, 0.3, 0.5, 0.7, 0.9]:
        assert abs(_sigmoid(_logit(p)) - p) < 1e-10

def test_duration_factor_new_prescription():
    assert _duration_factor(0, 12) == 0.0

def test_duration_factor_full_duration():
    assert _duration_factor(12, 12) == 1.0

def test_duration_factor_partial():
    factor = _duration_factor(6, 12)
    assert 0.0 < factor < 1.0
    assert abs(factor - 0.5) < 0.01

def test_duration_factor_no_onset():
    assert _duration_factor(6, None) == 1.0

def test_lab_lr_below_reference():
    lab = LabResult(loinc="1989-3", value_num=10, unit="ng/mL",
                    collected_at=datetime.now(timezone.utc),
                    reference_low=30, reference_high=80)
    lr = _lab_likelihood_ratio(lab)
    assert lr > 5.0  # severely low → high deficiency LR

def test_lab_lr_above_reference():
    lab = LabResult(loinc="1989-3", value_num=90, unit="ng/mL",
                    collected_at=datetime.now(timezone.utc),
                    reference_low=30, reference_high=80)
    lr = _lab_likelihood_ratio(lab)
    assert lr < 0.5  # sufficient → low deficiency LR

def test_lab_lr_within_range():
    lab = LabResult(loinc="1989-3", value_num=50, unit="ng/mL",
                    collected_at=datetime.now(timezone.utc),
                    reference_low=30, reference_high=80)
    lr = _lab_likelihood_ratio(lab)
    assert lr == 1.0


# ── DRS scoring ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_drs_baseline_only():
    """No conditions, no meds, no labs → posterior ≈ baseline."""
    patient = make_patient(conditions=(), medications=(), labs=())
    kg = make_kg(baseline=0.30)
    scorer = DeficiencyRiskScorer(kg)
    drs = await scorer.score(patient, "vitamin_d3")
    # With geo and lifestyle mods for KSA indoor, will be higher than 0.30
    assert drs.p_deficient > 0.30
    assert 0 < drs.p_deficient < 1.0

@pytest.mark.asyncio
async def test_drs_condition_raises_probability():
    patient = make_patient(
        conditions=[Condition(icd10_code="E11.9")],
        medications=(), labs=(),
    )
    kg = make_kg(
        baseline=0.30,
        condition_edges=[
            KGEdge(rel_type="INCREASES_DEMAND_FOR",
                   source_id="E11.9", target_id="vitamin_d3",
                   lr=1.6, lr_ci_lower=1.3, lr_ci_upper=2.1,
                   grade_weight=0.90)
        ],
    )
    scorer = DeficiencyRiskScorer(kg)
    drs = await scorer.score(patient, "vitamin_d3")
    assert drs.p_deficient > 0.35
    assert any("E11.9" in c.source for c in drs.contributors)

@pytest.mark.asyncio
async def test_drs_lab_dominates():
    """A clearly low lab should dominate the prior."""
    lab = LabResult(loinc="1989-3", value_num=8, unit="ng/mL",
                    collected_at=datetime.now(timezone.utc),
                    reference_low=30, reference_high=80)
    patient = make_patient(labs=[lab])
    kg = make_kg(baseline=0.30)
    scorer = DeficiencyRiskScorer(kg)
    drs = await scorer.score(patient, "vitamin_d3")
    assert drs.p_deficient > 0.85   # very deficient
    assert drs.lab_dominated is True

@pytest.mark.asyncio
async def test_drs_duration_factor_new_med():
    """New prescription (0 months) should contribute less to DRS."""
    patient_new = make_patient(
        medications=[Medication(rxnorm_cui="6809", name="Metformin", months_on=0)]
    )
    patient_chronic = make_patient(
        medications=[Medication(rxnorm_cui="6809", name="Metformin", months_on=24)]
    )
    depletion_edge = [KGEdge(
        rel_type="DEPLETES", source_id="6809", target_id="vitamin_b12",
        lr=2.4, lr_ci_lower=1.8, lr_ci_upper=3.1,
        onset_months=12, grade_weight=0.90,
    )]
    kg_new = make_kg(baseline=0.20, depletion_edges=depletion_edge)
    kg_chronic = make_kg(baseline=0.20, depletion_edges=depletion_edge)

    scorer_new = DeficiencyRiskScorer(kg_new)
    scorer_chronic = DeficiencyRiskScorer(kg_chronic)

    drs_new = await scorer_new.score(patient_new, "vitamin_b12")
    drs_chronic = await scorer_chronic.score(patient_chronic, "vitamin_b12")

    assert drs_chronic.p_deficient > drs_new.p_deficient


# ── Safety engine ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_safety_ul_enforcement():
    """Dose above 70% UL should be capped."""
    from src.core.deficiency_risk_scorer import _logit
    drs = MagicMock()
    drs.p_deficient = 0.75
    drs.contributors = []
    drs.lab_dominated = False

    candidate = Candidate(
        nutrient_id="vitamin_d3",
        drs=drs,
        dose=Dose(amount=3500, unit="IU", frequency="once_daily",
                  ul_pct_used=87.5, cap_applied=False),
    )
    patient = make_patient()
    kg = make_kg()
    safety = SafetyEngine(kg)
    result = await safety.run([candidate], patient)
    # 70% of 4000 IU UL = 2800 IU
    surviving = result.surviving
    assert len(surviving) == 1
    assert surviving[0].dose.amount <= 2800
    assert surviving[0].dose.cap_applied is True
    cap_warnings = [
        w for w in surviving[0].warnings if w.with_agent == "Upper Limit"
    ]
    assert cap_warnings
    assert "999999" not in cap_warnings[0].action

@pytest.mark.asyncio
async def test_safety_ul_cap_message_formats_magnesium_float():
    """70% UL cap should not leak float artifacts in the warning message."""
    drs = MagicMock()
    drs.p_deficient = 0.75
    drs.contributors = []
    drs.lab_dominated = False

    candidate = Candidate(
        nutrient_id="magnesium",
        drs=drs,
        dose=Dose(amount=300, unit="mg", frequency="once_daily"),
    )
    kg = make_kg()
    safety = SafetyEngine(kg)
    result = await safety.run([candidate], make_patient())
    surviving = result.surviving
    assert len(surviving) == 1
    assert surviving[0].dose.amount == 245
    cap_warnings = [
        w for w in surviving[0].warnings if w.with_agent == "Upper Limit"
    ]
    assert cap_warnings[0].action == "Dose capped at 70% of UL (245 mg)"


def test_format_ul_pct_small_values():
    assert _format_ul_pct(0.1) == "0.1"
    assert _format_ul_pct(45.0) == "45"
    assert _format_ul_pct(70.0) == "70"


def test_format_dose_amount_strips_float_artifacts():
    assert _format_dose_amount(245.0) == "245"
    assert _format_dose_amount(0.7 * 350) == "245"


@pytest.mark.asyncio
async def test_safety_hemochromatosis_blocks_iron():
    """Iron must be blocked for hemochromatosis patients."""
    drs = MagicMock()
    drs.p_deficient = 0.60
    drs.contributors = []
    drs.lab_dominated = False

    candidate = Candidate(
        nutrient_id="iron", drs=drs,
        dose=Dose(amount=18, unit="mg", frequency="once_daily"),
    )
    patient = make_patient(
        conditions=[Condition(icd10_code="E83.110")]
    )
    kg = make_kg()
    safety = SafetyEngine(kg)
    result = await safety.run([candidate], patient)
    assert len(result.surviving) == 0
    assert len(result.blocked) == 1
    assert "hemochromatosis" in result.blocked[0]["reason"].lower() or \
           "Hemochromatosis" in result.blocked[0]["reason"]

@pytest.mark.asyncio
async def test_safety_pregnancy_escalation():
    """Pregnant patient should trigger escalation."""
    drs = MagicMock()
    drs.p_deficient = 0.60
    drs.contributors = []
    drs.lab_dominated = False

    candidate = Candidate(
        nutrient_id="vitamin_a", drs=drs,
        dose=Dose(amount=3500, unit="mcg_RAE", frequency="once_daily"),
    )
    patient = make_patient(conditions=())
    patient = PatientProfile(
        patient_id=uuid.uuid4(),
        demographics=Demographics(
            age=29, sex=Sex.F, region_code="SA-01", bmi=24.0,
            pregnancy_status=True,
        ),
        conditions=(),
        medications=(),
        labs=(),
    )
    kg = make_kg()
    safety = SafetyEngine(kg)
    result = await safety.run([candidate], patient)
    # High-dose vitamin A should be blocked in pregnancy
    assert len(result.blocked) > 0 or result.escalate is True


# ── Confidence compositor ────────────────────────────────────────────────────

def test_confidence_high_grade_lab_dominated():
    drs = MagicMock()
    drs.p_deficient = 0.92
    drs.lab_dominated = True
    drs.contributors = [
        MagicMock(source="condition:E11.9", label="T2DM", lr=1.6, log_lr=math.log(1.6)),
        MagicMock(source="medication:6809", label="Metformin depletes", lr=2.4, log_lr=math.log(2.4)),
        MagicMock(source="lab:1989-3", label="Lab 8 ng/mL", lr=8.0, log_lr=math.log(8.0)),
    ]
    candidate = Candidate(nutrient_id="vitamin_d3", drs=drs, evidence_grade=EvidenceGrade.A)
    patient = make_patient()
    compositor = ConfidenceCompositor()
    score = compositor.compute(candidate, patient)
    assert score >= 0.75  # high evidence + lab dominated = high confidence

def test_confidence_grade_bins():
    compositor = ConfidenceCompositor()
    assert compositor.grade(0.85) == EvidenceGrade.A
    assert compositor.grade(0.70) == EvidenceGrade.B
    assert compositor.grade(0.50) == EvidenceGrade.C
    assert compositor.grade(0.30) == EvidenceGrade.D

def test_rank_score_blocked_is_zero():
    drs = MagicMock()
    drs.p_deficient = 0.90
    candidate = Candidate(
        nutrient_id="iron", drs=drs,
        confidence_score=0.85,
        blocked=True,
    )
    compositor = ConfidenceCompositor()
    assert compositor.rank_score(candidate) == 0.0


# ── CandidateGenerator ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_candidate_generator_threshold():
    drs_scores = {
        "vitamin_d3": DRS("vitamin_d3", 0.50, 0.30, 0.0, [], False),
        "zinc": DRS("zinc", 0.20, 0.15, 0.0, [], False),
    }
    kg = make_kg()
    gen = CandidateGenerator(kg, drs_threshold=0.35)
    candidates = await gen.generate(drs_scores, make_patient())
    ids = {c.nutrient_id for c in candidates}
    assert "vitamin_d3" in ids
    assert "zinc" not in ids


@pytest.mark.asyncio
async def test_candidate_generator_b_complex_collapse():
    b_ids = ["vitamin_b1", "vitamin_b2", "vitamin_b3", "vitamin_b12"]
    drs_scores = {
        nid: DRS(nid, 0.60, 0.30, 0.0, [], False) for nid in b_ids
    }
    kg = make_kg()
    kg.get_nutrient_meta = AsyncMock(side_effect=lambda nid: NutrientMeta(
        nutrient_id=nid, name=nid, form="form",
        rda=1, ear=1, ul=100, dose_unit="mg",
    ))
    gen = CandidateGenerator(kg, drs_threshold=0.35)
    candidates = await gen.generate(drs_scores, make_patient())
    assert len(candidates) == 1
    assert candidates[0].nutrient_id == "b_complex"


# ── DoseOptimizer ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dose_optimizer_lab_dominated_doubles_rda():
    drs = DRS("vitamin_d3", 0.92, 0.30, 0.0, [], lab_dominated=True)
    candidate = Candidate(nutrient_id="vitamin_d3", drs=drs)
    kg = make_kg()
    optimizer = DoseOptimizer(kg)
    dose = await optimizer.optimize(candidate, make_patient(bmi=25))
    # RDA 600 × 2.0 / bio 1.0 = 1200, capped at 70% UL (2800)
    assert dose.amount >= 1000
    assert dose.unit == "IU"


@pytest.mark.asyncio
async def test_dose_optimizer_pregnancy_override():
    drs = DRS("folate", 0.50, 0.30, 0.0, [], False)
    candidate = Candidate(nutrient_id="folate", drs=drs)
    kg = make_kg(nutrient_meta=NutrientMeta(
        nutrient_id="folate", name="Folate", form="L-methylfolate",
        rda=400, ear=320, ul=1000, dose_unit="mcg",
    ))
    patient = PatientProfile(
        patient_id=uuid.uuid4(),
        demographics=Demographics(
            age=29, sex=Sex.F, region_code="SA-01", pregnancy_status=True,
        ),
        conditions=(), medications=(), labs=(),
    )
    optimizer = DoseOptimizer(kg)
    dose = await optimizer.optimize(candidate, patient)
    assert dose.amount == 800
    assert dose.unit == "mcg"


@pytest.mark.asyncio
async def test_dose_optimizer_b12_moderate_deficiency_not_zero():
    """B12 at ~77% deficiency: RDA×1.5/bio ≈ 6 mcg — must not round to 0."""
    drs = DRS("vitamin_b12", 0.77, 0.20, 0.0, [], False)
    candidate = Candidate(nutrient_id="vitamin_b12", drs=drs)
    kg = make_kg(nutrient_meta=NutrientMeta(
        nutrient_id="vitamin_b12", name="Vitamin B12", form="methylcobalamin",
        rda=2.4, ear=2.0, ul=9999, dose_unit="mcg", bioavailability_factor=0.6,
    ))
    optimizer = DoseOptimizer(kg)
    dose = await optimizer.optimize(candidate, make_patient())
    assert dose.amount > 0
    assert dose.unit == "mcg"
    assert dose.amount >= 4  # at least ~RDA after bio correction


# ── ExplainService ───────────────────────────────────────────────────────────

def test_explain_service_three_layers():
    drs = DRS(
        "vitamin_d3", 0.85, 0.30, 0.0,
        [ContributorFactor("Low 25(OH)D", 8.0, math.log(8.0), "lab:1989-3")],
        lab_dominated=True,
    )
    candidate = Candidate(
        nutrient_id="vitamin_d3", drs=drs,
        dose=Dose(amount=2000, unit="IU", frequency="once_daily"),
        confidence_score=0.82, evidence_grade=EvidenceGrade.A,
    )
    patient = make_patient(labs=[
        LabResult(loinc="1989-3", value_num=18, unit="ng/mL",
                  collected_at=datetime.now(timezone.utc),
                  reference_low=30, reference_high=80),
    ])
    explained = ExplainService().explain(candidate, patient)
    assert explained.nutrient_name == "Vitamin D3"
    assert len(explained.why) > 20
    assert len(explained.evidence) > 20
    assert len(explained.safety) > 10


def test_explain_safety_shows_fractional_ul_pct():
    drs = MagicMock()
    drs.p_deficient = 0.77
    drs.contributors = []
    drs.lab_dominated = False

    candidate = Candidate(
        nutrient_id="vitamin_b12",
        drs=drs,
        dose=Dose(
            amount=6,
            unit="mcg",
            frequency="once_daily",
            ul_pct_used=0.1,
        ),
        confidence_score=0.46,
        evidence_grade=EvidenceGrade.C,
    )
    explained = ExplainService().explain(candidate, make_patient())
    assert "0.1% of the established upper safety limit" in explained.safety
    assert "0% of the established upper safety limit" not in explained.safety


# ── Additional safety cases ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_safety_contraindicated_drug_blocks():
    drs = MagicMock()
    drs.p_deficient = 0.70
    drs.contributors = []
    drs.lab_dominated = False

    candidate = Candidate(
        nutrient_id="vitamin_k2", drs=drs,
        dose=Dose(amount=100, unit="mcg", frequency="once_daily"),
    )
    patient = make_patient(
        medications=[Medication(rxnorm_cui="1091643", name="Warfarin", months_on=12)]
    )
    kg = make_kg(interaction_edges=[
        KGEdge(
            rel_type="INTERACTS_WITH", source_id="1091643", target_id="vitamin_k2",
            lr=1.0, lr_ci_lower=1.0, lr_ci_upper=1.0,
            severity=WarningSeverity.CONTRAINDICATED,
            mechanism="Vitamin K reverses warfarin",
        ),
    ])
    safety = SafetyEngine(kg)
    result = await safety.run([candidate], patient)
    assert len(result.surviving) == 0
    assert len(result.blocked) == 1


@pytest.mark.asyncio
async def test_safety_antagonist_timing_warning():
    drs = MagicMock()
    drs.p_deficient = 0.70
    drs.contributors = []
    drs.lab_dominated = False

    calcium = Candidate(
        nutrient_id="calcium", drs=drs,
        dose=Dose(amount=500, unit="mg", frequency="once_daily"),
    )
    iron = Candidate(
        nutrient_id="iron", drs=drs,
        dose=Dose(amount=18, unit="mg", frequency="once_daily"),
    )
    kg = make_kg(antagonist_pairs=[
        ("calcium", "iron", "Separate calcium and iron supplements by ≥2 hours"),
    ])
    safety = SafetyEngine(kg)
    result = await safety.run([calcium, iron], make_patient())
    assert len(result.surviving) == 2
    warning_actions = [w.action for c in result.surviving for w in c.warnings]
    assert any("Separate" in a for a in warning_actions)
