"""Longitudinal personalization from prior session DRS snapshots."""
from __future__ import annotations

import math
import uuid
from typing import Optional

from src.db.repositories import RecommendationRepository
from src.shared.models import DRS, LabResult, PatientProfile


def _logit(p: float) -> float:
    p = min(0.999, max(0.001, p))
    return math.log(p / (1.0 - p))


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


class PersonalizationEngine:
    """
    Layer 3 personalization: blend current DRS with priors from the patient's
    most recent served session (stored drs_snapshot).
    """

    PRIOR_WEIGHT = 0.35

    async def load_longitudinal_priors(
        self,
        patient_id: uuid.UUID,
        repo: RecommendationRepository,
    ) -> dict[str, float]:
        snapshot = await repo.get_last_drs_snapshot(patient_id)
        return snapshot or {}

    def apply_longitudinal_priors(
        self,
        drs_scores: dict[str, DRS],
        priors: dict[str, float],
    ) -> dict[str, DRS]:
        if not priors:
            return drs_scores
        updated: dict[str, DRS] = {}
        for nutrient_id, drs in drs_scores.items():
            prior_p = priors.get(nutrient_id)
            if prior_p is None:
                updated[nutrient_id] = drs
                continue
            blended_logit = (
                (1.0 - self.PRIOR_WEIGHT) * drs.logit_posterior
                + self.PRIOR_WEIGHT * _logit(prior_p)
            )
            p_deficient = _sigmoid(blended_logit)
            updated[nutrient_id] = DRS(
                nutrient_id=nutrient_id,
                p_deficient=min(0.999, max(0.001, p_deficient)),
                baseline=drs.baseline,
                logit_posterior=blended_logit,
                contributors=drs.contributors,
                lab_dominated=drs.lab_dominated,
            )
        return updated

    def bayesian_update(
        self,
        prior_p: float,
        lab: LabResult,
        assay_variance: float = 0.05,
    ) -> float:
        """Gaussian conjugate-style shift toward measured lab (longitudinal lab drift)."""
        if lab.reference_low is None or lab.reference_high is None:
            return prior_p
        mid = (lab.reference_low + lab.reference_high) / 2.0
        if mid == 0:
            return prior_p
        deviation = (mid - lab.value_num) / mid
        weight = min(1.0, max(0.05, 1.0 - assay_variance))
        shifted_logit = _logit(prior_p) + weight * deviation
        return min(0.999, max(0.001, _sigmoid(shifted_logit)))
