"""
Core pipeline components:
  - CandidateGenerator: DRS threshold + guideline trigger → candidate list
  - DoseOptimizer: RDA × risk × bioavailability × UL cap → Dose
  - ConfidenceCompositor: C = 0.40·E + 0.15·D + 0.15·S + 0.10·P + 0.10·M + 0.10·Bayes
"""
from __future__ import annotations

import logging
import math
from typing import Optional

from src.knowledge.graph_client import GraphClient, GuidelineRecommendation
from src.shared.models import (
    Candidate, Demographics, Dose, DRS, EvidenceGrade,
    NutrientMeta, PatientProfile,
)

logger = logging.getLogger(__name__)

# Pregnancy-specific dosing overrides (ACOG/WHO)
_PREGNANCY_DOSES: dict[str, tuple[float, str, str]] = {
    "folate":    (800.0,  "mcg",  "once_daily"),
    "iron":      (27.0,   "mg",   "once_daily"),
    "iodine":    (220.0,  "mcg",  "once_daily"),
    "choline":   (450.0,  "mg",   "once_daily"),
    "omega3_dha": (200.0, "mg",   "once_daily"),
    "vitamin_d3": (600.0, "IU",   "once_daily"),
}


class CandidateGenerator:
    """
    Produces the initial candidate list from DRS scores + guideline triggers.
    Applies two passes:
      1. Score threshold (DRS ≥ 0.35)
      2. Guideline trigger (CPG mandates supplement regardless of DRS)
    Then collapses ≥3 B-vitamins into a B-complex.
    """

    def __init__(self, graph_client: GraphClient, drs_threshold: float = 0.35):
        self._kg = graph_client
        self._threshold = drs_threshold

    async def generate(
        self, drs_scores: dict[str, DRS], patient: PatientProfile
    ) -> list[Candidate]:
        candidates: list[Candidate] = []
        import asyncio
        nutrient_ids = list(drs_scores.keys())
        meta_results = await asyncio.gather(
            *[self._kg.get_nutrient_meta(nid) for nid in nutrient_ids]
        )
        metas = dict(zip(nutrient_ids, meta_results))

        for nutrient_id, drs in drs_scores.items():
            meta = metas.get(nutrient_id)
            if not meta:
                continue

            guideline = await self._kg.get_guideline(nutrient_id, patient.demographics)
            qualifies_by_drs = drs.p_deficient >= self._threshold
            qualifies_by_guideline = guideline is not None

            if not (qualifies_by_drs or qualifies_by_guideline):
                continue

            candidates.append(Candidate(
                nutrient_id=nutrient_id,
                drs=drs,
                guideline_triggered=qualifies_by_guideline,
            ))

        return self._collapse_b_vitamins(candidates)

    def _collapse_b_vitamins(self, candidates: list[Candidate]) -> list[Candidate]:
        """
        If ≥3 separate B-vitamins are indicated, replace with a single B-complex candidate.
        Avoids the absurd output of recommending B1, B2, B3, B6, B9, B12 individually.
        """
        b_vitamins = {
            "vitamin_b1", "vitamin_b2", "vitamin_b3",
            "vitamin_b5", "vitamin_b6", "vitamin_b7",
            "vitamin_b9_folate", "vitamin_b12",
        }
        b_candidates = [c for c in candidates if c.nutrient_id in b_vitamins]
        if len(b_candidates) < 3:
            return candidates

        non_b = [c for c in candidates if c.nutrient_id not in b_vitamins]
        # Create a synthetic B-complex candidate using the highest DRS among B vitamins
        top_b = max(b_candidates, key=lambda c: c.drs.p_deficient)
        complex_candidate = Candidate(
            nutrient_id="b_complex",
            drs=top_b.drs,
            guideline_triggered=any(c.guideline_triggered for c in b_candidates),
        )
        return non_b + [complex_candidate]


class DoseOptimizer:
    """
    Computes the recommended dose for a candidate.

    Decision hierarchy (highest priority first):
      1. Pregnancy/lactation guideline override
      2. KG guideline dose (CPG-specified)
      3. DRS-adjusted RDA (1× / 1.5× / 2× based on severity)
      4. Bioavailability correction
      5. BMI adjustment (fat-soluble vitamins in obesity)
      6. UL cap at 70% (safety layer will re-verify)
    """

    def __init__(self, graph_client: GraphClient):
        self._kg = graph_client

    async def optimize(
        self,
        candidate: Candidate,
        patient: PatientProfile,
        guideline: Optional[GuidelineRecommendation] = None,
    ) -> Dose:
        meta = await self._kg.get_nutrient_meta(candidate.nutrient_id)
        if not meta:
            return Dose(amount=0, unit="mg", frequency="once_daily")

        demo = patient.demographics

        # 1. Pregnancy override
        if demo.pregnancy_status and candidate.nutrient_id in _PREGNANCY_DOSES:
            amount, unit, freq = _PREGNANCY_DOSES[candidate.nutrient_id]
            return Dose(
                amount=amount, unit=unit, frequency=freq,
                with_food=True, duration="until_delivery_plus_3mo",
                ul_pct_used=round((amount / meta.ul) * 100, 1) if meta.ul else 0.0,
            )

        # 2. Guideline dose
        if guideline and guideline.dose:
            base = guideline.dose
            unit = guideline.dose_unit or meta.dose_unit
        else:
            # 3. DRS-adjusted RDA
            p = candidate.drs.p_deficient
            if p > 0.90 or candidate.drs.lab_dominated:
                multiplier = 2.0   # therapeutic replacement
            elif p > 0.70:
                multiplier = 1.5   # moderate insufficiency
            else:
                multiplier = 1.0   # preventive
            base = meta.rda * multiplier
            unit = meta.dose_unit

        # 4. Bioavailability correction
        base = base / max(meta.bioavailability_factor, 0.1)

        # 5. BMI adjustment for fat-soluble vitamins
        bmi_adjusted = {"vitamin_d3", "vitamin_e", "vitamin_a", "vitamin_k2"}
        if candidate.nutrient_id in bmi_adjusted and demo.bmi and demo.bmi >= 30:
            base *= 1.5

        # 6. Cap at 70% of UL
        ul_cap = meta.ul * 0.7
        cap_applied = base > ul_cap
        final_amount = min(base, ul_cap)
        final_amount = _round_to_clinical_unit(final_amount, unit)

        return Dose(
            amount=final_amount,
            unit=unit,
            frequency=_schedule(candidate.nutrient_id, final_amount, meta),
            with_food=_take_with_food(candidate.nutrient_id),
            duration="ongoing",
            ul_pct_used=round((final_amount / meta.ul) * 100, 1) if meta.ul else 0.0,
            cap_applied=cap_applied,
        )


class ConfidenceCompositor:
    """
    C = 0.40·E + 0.15·D + 0.15·S + 0.10·P + 0.10·M + 0.10·Bayes

    E = evidence weight (GRADE tier)
    D = directness (population match to study population)
    S = consistency across evidence pieces
    P = precision (1 / CI width, normalized)
    M = mechanism plausibility
    Bayes = individual evidence (lab dominated = 1.0, otherwise from DRS)
    """

    def compute(self, candidate: Candidate, patient: PatientProfile) -> float:
        drs = candidate.drs

        # E — evidence weight from the top supporting edge
        e = _evidence_weight_from_grade(candidate.evidence_grade)

        # D — directness: does the study population match the patient?
        d = _directness(patient.demographics)

        # S — consistency (proxy: more contributors from different sources = more consistent)
        unique_sources = len({c.source.split(":")[0] for c in drs.contributors})
        s = min(1.0, unique_sources * 0.2)

        # P — precision (proxy: lab-dominated = high precision)
        p = 0.8 if drs.lab_dominated else 0.4

        # M — mechanism plausibility (proxy: if we have a mechanism string in KG)
        mechanism_contributors = [c for c in drs.contributors if "depletes" in c.label.lower()
                                   or "malabsorption" in c.label.lower()]
        m = 0.8 if mechanism_contributors else 0.5

        # Bayes — individual evidence
        bayes = 1.0 if drs.lab_dominated else min(drs.p_deficient, 0.9)

        c = (0.40 * e + 0.15 * d + 0.15 * s + 0.10 * p + 0.10 * m + 0.10 * bayes)
        return round(min(1.0, max(0.0, c)), 3)

    def grade(self, confidence: float) -> EvidenceGrade:
        if confidence >= 0.80:  return EvidenceGrade.A
        if confidence >= 0.60:  return EvidenceGrade.B
        if confidence >= 0.40:  return EvidenceGrade.C
        return EvidenceGrade.D

    def rank_score(self, candidate: Candidate) -> float:
        """Rank = P_deficient × Confidence × I_safety (0 if blocked)."""
        if candidate.blocked:
            return 0.0
        return candidate.drs.p_deficient * candidate.confidence_score


# ── Helpers ────────────────────────────────────────────────────────────────

def _evidence_weight_from_grade(grade: EvidenceGrade) -> float:
    return {
        EvidenceGrade.A: 0.95,
        EvidenceGrade.B: 0.75,
        EvidenceGrade.C: 0.55,
        EvidenceGrade.D: 0.20,
    }.get(grade, 0.20)

def _directness(demo: Demographics) -> float:
    """Saudi/Gulf patients have dedicated cohort data → higher directness."""
    if demo.region_code.startswith("SA") or demo.region_code.startswith("AE"):
        return 0.85
    return 0.60

def _round_to_clinical_unit(amount: float, unit: str) -> float:
    """Round to nearest clinically sensible increment; never round a positive dose to zero."""
    if amount <= 0:
        return 0.0

    if unit == "mcg":
        if amount < 25:
            inc = 1
        elif amount < 100:
            inc = 5
        elif amount < 500:
            inc = 25
        else:
            inc = 50
    elif unit == "IU":
        inc = 100 if amount < 200 else 200
    elif unit == "mg":
        inc = 1 if amount < 5 else 5
    elif unit == "g":
        inc = 0.5
    else:
        inc = 1

    rounded = round(round(amount / inc) * inc, 1)
    if rounded <= 0:
        return float(inc)
    return rounded

def _schedule(nutrient_id: str, amount: float, meta: NutrientMeta) -> str:
    """Split dosing for high-amount nutrients with poor single-dose absorption."""
    split_nutrients = {"calcium", "vitamin_c", "magnesium"}
    if nutrient_id in split_nutrients and amount > 500:
        return "twice_daily"
    return "once_daily"

def _take_with_food(nutrient_id: str) -> bool:
    empty_stomach_ok = {"iron", "vitamin_c"}
    return nutrient_id not in empty_stomach_ok
