"""
DeficiencyRiskScorer — Bayesian log-odds accumulation engine.

Think of it like a Naive Bayes classifier where each clinical factor
(condition, medication, lab, lifestyle) adds evidence in log-space.
The posterior is sigmoid(logit_baseline + Σ log(LR_i)).

Key design decisions:
- Log-space accumulation avoids float underflow at extreme priors
- Lab results dominate (weight 0.8) — a measured value beats priors
- Duration factor smooths drug depletion effects (new prescription ≠ full depletion)
- All contributors are traced for the explainability layer
"""
from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass, field
from typing import Optional

from src.knowledge.graph_client import GraphClient
from src.shared.models import (
    ContributorFactor, Demographics, DRS, LabResult,
    Lifestyle, Medication, PatientProfile,
)

logger = logging.getLogger(__name__)

# Geographic priors for KSA — inflated Vit D, adjusted iodine
_GEOGRAPHIC_MODIFIERS: dict[str, dict[str, float]] = {
    "vitamin_d3": {
        "SA": 2.2,    # veiled dress norm + indoor lifestyle + high latitude UV paradox
        "AE": 1.9,
        "KW": 1.9,
        "default": 1.0,
    },
    "iodine": {
        "SA": 0.8,    # mandatory salt iodization lowers deficiency risk
        "default": 1.0,
    },
}

# Lifestyle likelihood ratios
_LIFESTYLE_LR: dict[str, dict[str, float]] = {
    "vitamin_d3": {
        "indoor_occupation": 1.5,
        "sun_lt_2hrs": 1.4,
        "veiled_dress": 2.2,
    },
    "iron": {
        "vegan": 1.7,
        "vegetarian": 1.4,
        "endurance_athlete": 1.3,
        "heavy_menstruation": 2.0,
    },
    "vitamin_b12": {
        "vegan": 3.0,
        "vegetarian": 1.8,
    },
    "omega3_epa_dha": {
        "vegan": 2.5,
        "low_fish": 1.5,
    },
}

# BMI modifiers (adipose sequestration of fat-soluble vitamins)
_BMI_LR: dict[str, float] = {
    "vitamin_d3": 1.5,
    "vitamin_e": 1.3,
    "vitamin_a": 1.2,
    "vitamin_k2": 1.2,
}


class DeficiencyRiskScorer:
    """
    Computes P(nutrient deficient | patient) for every nutrient in the KG.

    Architecture: async, concurrent per-nutrient scoring via asyncio.gather.
    Each nutrient score is independent — perfect for concurrency.
    """

    def __init__(self, graph_client: GraphClient):
        self._kg = graph_client

    async def score_all(
        self, patient: PatientProfile, nutrient_ids: Optional[list[str]] = None
    ) -> dict[str, DRS]:
        """
        Score all nutrients concurrently.
        Returns {nutrient_id: DRS} — the input to CandidateGenerator.
        """
        if nutrient_ids is None:
            nutrient_ids = await self._kg.get_all_nutrient_ids()

        tasks = [self.score(patient, nid) for nid in nutrient_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        scores: dict[str, DRS] = {}
        for nid, result in zip(nutrient_ids, results):
            if isinstance(result, Exception):
                logger.warning("DRS failed for %s: %s", nid, result)
                scores[nid] = DRS(nutrient_id=nid, p_deficient=0.0,
                                  baseline=0.0, logit_posterior=0.0)
            else:
                scores[nid] = result
        return scores

    async def score(self, patient: PatientProfile, nutrient_id: str) -> DRS:
        """
        Single-nutrient Bayesian DRS.

        Pipeline:
          1. Population baseline (region/age/sex bucket)
          2. Geographic modifier
          3. BMI fat-soluble sequestration
          4. Lifestyle modifiers
          5. Disease edges (INCREASES_DEMAND_FOR + CAUSES_MALABSORPTION_OF)
          6. Drug edges (DEPLETES × duration_factor)
          7. Lab override — if present, collapses posterior toward measured value
        """
        contributors: list[ContributorFactor] = []

        # 1. Baseline
        baseline = await self._kg.get_baseline_prevalence(
            nutrient_id, patient.demographics
        )
        baseline = max(0.001, min(0.999, baseline))  # guard logit singularities
        logit_p = _logit(baseline)

        # 2. Geographic modifier
        geo_lr = _geo_modifier(nutrient_id, patient.demographics.region_code)
        if geo_lr != 1.0:
            logit_p += math.log(geo_lr)
            contributors.append(ContributorFactor(
                label=f"Region {patient.demographics.region_code}",
                lr=geo_lr, log_lr=math.log(geo_lr),
                source=f"geo:{patient.demographics.region_code}",
            ))

        # 3. BMI modifier (fat-soluble vitamins)
        bmi = patient.demographics.bmi
        if bmi and bmi >= 30 and nutrient_id in _BMI_LR:
            bmi_lr = _BMI_LR[nutrient_id]
            logit_p += math.log(bmi_lr)
            contributors.append(ContributorFactor(
                label=f"BMI {bmi:.1f} (adipose sequestration)",
                lr=bmi_lr, log_lr=math.log(bmi_lr),
                source="bmi",
            ))

        # 4. Lifestyle modifiers
        lifestyle_factors = _lifestyle_modifiers(
            nutrient_id, patient.demographics, patient.lifestyle
        )
        for factor, lr in lifestyle_factors:
            logit_p += math.log(lr)
            contributors.append(ContributorFactor(
                label=factor, lr=lr, log_lr=math.log(lr),
                source=f"lifestyle:{factor}",
            ))

        # 5. Condition edges — run concurrently across all conditions
        condition_tasks = [
            self._kg.get_condition_edges(c.icd10_code, nutrient_id)
            for c in patient.conditions
        ]
        condition_edge_lists = await asyncio.gather(*condition_tasks)

        for condition, edges in zip(patient.conditions, condition_edge_lists):
            for edge in edges:
                # Use CI lower bound — conservative: weak edges get penalized
                effective_lr = max(edge.lr_ci_lower, edge.lr)
                logit_p += math.log(effective_lr)
                contributors.append(ContributorFactor(
                    label=f"{condition.icd10_code} → {edge.rel_type}",
                    lr=effective_lr,
                    log_lr=math.log(effective_lr),
                    source=f"condition:{condition.icd10_code}",
                ))

        # 6. Drug depletion edges — with duration factor
        depletion_tasks = [
            self._kg.get_depletion_edges(m.rxnorm_cui, nutrient_id)
            for m in patient.medications
        ]
        depletion_edge_lists = await asyncio.gather(*depletion_tasks)

        for medication, edges in zip(patient.medications, depletion_edge_lists):
            for edge in edges:
                duration_factor = _duration_factor(
                    medication.months_on, edge.onset_months
                )
                effective_lr = 1.0 + (edge.lr - 1.0) * duration_factor
                effective_lr = max(effective_lr, 1.0)
                logit_p += math.log(effective_lr)
                contributors.append(ContributorFactor(
                    label=f"{medication.name} depletes (duration factor {duration_factor:.2f})",
                    lr=effective_lr,
                    log_lr=math.log(effective_lr),
                    source=f"medication:{medication.rxnorm_cui}",
                ))

        # 7. Lab override — measured values dominate (weight 0.8)
        lab_dominated = False
        meta = await self._kg.get_nutrient_meta(nutrient_id)
        if meta:
            for loinc_code in meta.loinc_codes:
                lab = patient.lab_for(loinc_code)
                if lab:
                    lab_lr = _lab_likelihood_ratio(lab)
                    # Bayesian blending: 20% prior, 80% lab
                    logit_p = logit_p * 0.2 + math.log(lab_lr) * 0.8
                    contributors.append(ContributorFactor(
                        label=f"Lab {loinc_code} = {lab.value_num} {lab.unit} (dominates)",
                        lr=lab_lr,
                        log_lr=math.log(lab_lr),
                        source=f"lab:{loinc_code}",
                    ))
                    lab_dominated = True
                    break  # one lab per nutrient is sufficient

        p_deficient = _sigmoid(logit_p)

        return DRS(
            nutrient_id=nutrient_id,
            p_deficient=min(0.999, max(0.001, p_deficient)),
            baseline=baseline,
            logit_posterior=logit_p,
            contributors=contributors,
            lab_dominated=lab_dominated,
        )


# ── Math helpers ───────────────────────────────────────────────────────────

def _logit(p: float) -> float:
    return math.log(p / (1.0 - p))

def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))

def _duration_factor(months_on: int, onset_months: Optional[int]) -> float:
    """
    Ramps from 0→1 as treatment duration approaches the depletion onset point.
    A new prescription gets almost no LR uplift; chronic use gets full LR.
    """
    if not onset_months or onset_months <= 0:
        return 1.0
    return min(1.0, months_on / onset_months)

def _lab_likelihood_ratio(lab: LabResult) -> float:
    """
    Converts a lab value into a likelihood ratio of deficiency.
    Below reference low → high LR (likely deficient).
    Above reference high → low LR (unlikely deficient).
    Within range → LR ~1.0 (uninformative).
    """
    if lab.flagged:
        return 8.0 if lab.value_num < (lab.reference_low or 0) else 0.15

    if lab.reference_low and lab.value_num < lab.reference_low:
        # Linear interpolation: at 0 → LR 10, at reference_low → LR 1
        severity = 1.0 - (lab.value_num / lab.reference_low)
        return 1.0 + severity * 9.0

    if lab.reference_high and lab.value_num > lab.reference_high:
        return 0.1   # clear sufficiency → very unlikely deficient

    return 1.0       # within normal range

def _geo_modifier(nutrient_id: str, region_code: str) -> float:
    country = region_code.split("-")[0] if "-" in region_code else region_code
    mods = _GEOGRAPHIC_MODIFIERS.get(nutrient_id, {})
    return mods.get(country, mods.get("default", 1.0))

def _lifestyle_modifiers(
    nutrient_id: str, demo: Demographics, lifestyle: Lifestyle
) -> list[tuple[str, float]]:
    """Returns list of (label, lr) for applicable lifestyle factors."""
    mods = _LIFESTYLE_LR.get(nutrient_id, {})
    factors: list[tuple[str, float]] = []

    if demo.veiled_dress and "veiled_dress" in mods:
        factors.append(("Veiled dress (reduced UV synthesis)", mods["veiled_dress"]))
    if demo.indoor_occupation and "indoor_occupation" in mods:
        factors.append(("Indoor occupation", mods["indoor_occupation"]))
    if lifestyle.sun_exposure_hrs_wk < 2 and "sun_lt_2hrs" in mods:
        factors.append(("Sun exposure <2 hrs/week", mods["sun_lt_2hrs"]))
    if lifestyle.diet_pattern == "vegan" and "vegan" in mods:
        factors.append(("Vegan diet", mods["vegan"]))
    if lifestyle.diet_pattern == "vegetarian" and "vegetarian" in mods:
        factors.append(("Vegetarian diet", mods["vegetarian"]))

    return factors
