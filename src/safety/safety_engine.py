"""
SafetyEngine — deterministic rules-only gate.

This runs AFTER the recommender. No ML. No probabilities.
Every decision is a lookup + rule application → auditable + certifiable.

Design: pure functions over typed inputs. No state mutation.
Go equivalent would be even safer but Python is fine at this scale.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from src.knowledge.graph_client import GraphClient
from src.shared.models import (
    Candidate, Condition, Demographics, InteractionWarning,
    Medication, PatientProfile, WarningSeverity,
)

logger = logging.getLogger(__name__)


def _format_dose_amount(amount: float) -> str:
    """Format dose amounts for user-facing messages (no float artifacts)."""
    rounded = round(amount, 1)
    if rounded == int(rounded):
        return str(int(rounded))
    return f"{rounded:.1f}".rstrip("0").rstrip(".")


# IOM/EFSA upper limits — adult defaults. Full table in KG; this is the fallback.
_UL_FALLBACK: dict[str, tuple[float, str]] = {
    "vitamin_a":          (3000,  "mcg_RAE"),
    "vitamin_d3":         (4000,  "IU"),
    "vitamin_e":          (1000,  "mg"),
    "niacin":             (35,    "mg"),
    "vitamin_b6":         (100,   "mg"),
    "folate":             (1000,  "mcg"),
    "iron":               (45,    "mg"),
    "zinc":               (40,    "mg"),
    "selenium":           (400,   "mcg"),
    "calcium":            (2500,  "mg"),
    "magnesium":          (350,   "mg"),
    "iodine":             (1100,  "mcg"),
    "choline":            (3500,  "mg"),
    "vitamin_c":          (2000,  "mg"),
    "copper":             (10,    "mg"),
    "manganese":          (11,    "mg"),
    "phosphorus":         (4000,  "mg"),
}

# Absolute contraindications: (nutrient_id, condition_prefix, reason)
_ABSOLUTE_CONDITION_BLOCKS: list[tuple[str, str, str]] = [
    ("iron",         "E83.110", "Hemochromatosis — iron overload risk"),
    ("iron",         "E83.111", "Hemochromatosis — iron overload risk"),
    ("potassium",    "N18",     "CKD — hyperkalemia risk"),
    ("magnesium",    "N18.4",   "CKD Stage 4+ — hypermagnesemia risk"),
    ("magnesium",    "N18.5",   "CKD Stage 5 — contraindicated without monitoring"),
    ("vitamin_a",    "O",       "Pregnancy: high-dose retinol teratogenic"),
    ("niacin",       "K72",     "Hepatic failure — niacin hepatotoxic"),
]

# Absolute drug-nutrient contraindications: (nutrient_id, rxnorm_cui, reason)
_ABSOLUTE_DRUG_BLOCKS: list[tuple[str, str, str]] = [
    ("st_johns_wort", "36567",  "SSRI + St. John's Wort → serotonin syndrome"),
    ("st_johns_wort", "41493",  "SNRI + St. John's Wort → serotonin syndrome"),
    ("vitamin_b6",   "82064",   "Levodopa (no carbidopa) — B6 reduces efficacy"),
]

# Physician escalation triggers
_ESCALATION_TRIGGERS: list[tuple[str, str]] = [
    ("condition", "N18.4"),
    ("condition", "N18.5"),
    ("condition", "K72"),
    ("condition", "E83.110"),
]


@dataclass
class FilterResult:
    surviving: list[Candidate]
    blocked: list[dict]     # {nutrient_id, reason, trigger}
    escalate: bool
    escalation_reasons: list[str]


class SafetyEngine:
    """
    Final deterministic gate before recommendations are rendered.
    Order matters: drug interactions → disease CI → nutrient-nutrient → UL → escalation.
    """

    def __init__(self, graph_client: GraphClient):
        self._kg = graph_client

    async def run(
        self, candidates: list[Candidate], patient: PatientProfile
    ) -> FilterResult:
        surviving: list[Candidate] = []
        blocked: list[dict] = []

        for candidate in candidates:
            # — Drug-nutrient interactions —
            interaction_result = await self._check_drug_interactions(
                candidate, patient.medications
            )
            if interaction_result.get("blocked"):
                candidate.blocked = True
                candidate.block_reason = interaction_result["reason"]
                blocked.append({
                    "nutrient_id": candidate.nutrient_id,
                    "reason": interaction_result["reason"],
                    "trigger": "drug_interaction",
                })
                continue

            # Add warnings (non-blocking interactions)
            for w in interaction_result.get("warnings", []):
                candidate.warnings.append(w)

            # — Disease contraindications —
            ci_result = self._check_disease_contraindications(
                candidate.nutrient_id, patient.conditions, patient.demographics
            )
            if ci_result:
                candidate.blocked = True
                candidate.block_reason = ci_result
                blocked.append({
                    "nutrient_id": candidate.nutrient_id,
                    "reason": ci_result,
                    "trigger": "disease_contraindication",
                })
                continue

            # — UL enforcement (dose already set by DoseOptimizer) —
            if candidate.dose:
                ul_result = self._enforce_ul(candidate)
                candidate = ul_result

            surviving.append(candidate)

        # — Nutrient-nutrient antagonism (within surviving set) —
        surviving = await self._add_nn_warnings(surviving)

        # — Escalation check —
        escalate, escalation_reasons = self._check_escalation(
            surviving, patient, blocked
        )

        return FilterResult(
            surviving=surviving,
            blocked=blocked,
            escalate=escalate,
            escalation_reasons=escalation_reasons,
        )

    # ── Drug-nutrient interaction check ───────────────────────────────────

    async def _check_drug_interactions(
        self, candidate: Candidate, medications: tuple[Medication, ...]
    ) -> dict:
        warnings: list[InteractionWarning] = []

        for med in medications:
            edges = await self._kg.get_interaction_edges(
                med.rxnorm_cui, candidate.nutrient_id
            )
            for edge in edges:
                if edge.severity == WarningSeverity.CONTRAINDICATED:
                    return {
                        "blocked": True,
                        "reason": f"Contraindicated with {med.name}: {edge.mechanism or ''}",
                    }
                warnings.append(InteractionWarning(
                    severity=edge.severity or WarningSeverity.MINOR,
                    with_agent=med.name,
                    action=_interaction_action(edge.severity),
                    mechanism=edge.mechanism,
                ))

        # Also check static absolute drug blocks
        for nutrient_id, rxnorm_cui, reason in _ABSOLUTE_DRUG_BLOCKS:
            if (candidate.nutrient_id == nutrient_id
                    and any(m.rxnorm_cui == rxnorm_cui for m in medications)):
                return {"blocked": True, "reason": reason}

        return {"blocked": False, "warnings": warnings}

    # ── Disease contraindication check ────────────────────────────────────

    def _check_disease_contraindications(
        self,
        nutrient_id: str,
        conditions: tuple[Condition, ...],
        demo: Demographics,
    ) -> Optional[str]:
        for n_id, icd10_prefix, reason in _ABSOLUTE_CONDITION_BLOCKS:
            if nutrient_id != n_id:
                continue
            # Special case: high-dose vitamin A in pregnancy
            if n_id == "vitamin_a" and icd10_prefix == "O":
                if demo.pregnancy_status:
                    return reason
                continue
            # General prefix match
            if any(c.icd10_code.startswith(icd10_prefix) for c in conditions):
                return reason
        return None

    # ── UL enforcement ────────────────────────────────────────────────────

    def _enforce_ul(self, candidate: Candidate) -> Candidate:
        """
        Cap dose at 70% of UL. Raise a warning if we had to cap.
        Never recommend above UL — that's a hard block.
        """
        if not candidate.dose:
            return candidate

        ul_info = _UL_FALLBACK.get(candidate.nutrient_id)
        if not ul_info:
            return candidate

        ul_value, ul_unit = ul_info
        if candidate.dose.unit != ul_unit:
            return candidate   # unit mismatch — skip cap; UL table needs enrichment

        safe_max = 0.7 * ul_value
        ul_pct = (candidate.dose.amount / ul_value) * 100.0

        if candidate.dose.amount > ul_value:
            logger.error(
                "Dose %s %s exceeds UL %s for %s — hard blocking",
                candidate.dose.amount, ul_unit, ul_value, candidate.nutrient_id
            )
            candidate.blocked = True
            candidate.block_reason = f"Dose exceeds UL ({ul_value} {ul_unit})"
            return candidate

        if candidate.dose.amount > safe_max:
            from dataclasses import replace
            capped_amount = round(safe_max, 1)
            candidate.dose = replace(
                candidate.dose,
                amount=capped_amount,
                ul_pct_used=round((capped_amount / ul_value) * 100, 1),
                cap_applied=True,
            )
            candidate.warnings.append(InteractionWarning(
                severity=WarningSeverity.MINOR,
                with_agent="Upper Limit",
                action=(
                    f"Dose capped at 70% of UL "
                    f"({_format_dose_amount(capped_amount)} {ul_unit})"
                ),
            ))
        else:
            from dataclasses import replace
            candidate.dose = replace(
                candidate.dose,
                ul_pct_used=round(ul_pct, 1),
            )
        return candidate

    # ── Nutrient-nutrient antagonism ──────────────────────────────────────

    async def _add_nn_warnings(
        self, candidates: list[Candidate]
    ) -> list[Candidate]:
        """Add timing/separation warnings for antagonist pairs in the set."""
        nutrient_ids = [c.nutrient_id for c in candidates]
        if len(nutrient_ids) < 2:
            return candidates

        antagonist_pairs = await self._kg.get_antagonist_pairs(nutrient_ids)
        pair_lookup = {(a, b): action for a, b, action in antagonist_pairs}

        for candidate in candidates:
            for other in candidates:
                if other.nutrient_id == candidate.nutrient_id:
                    continue
                action = pair_lookup.get((candidate.nutrient_id, other.nutrient_id))
                if action:
                    candidate.warnings.append(InteractionWarning(
                        severity=WarningSeverity.MODERATE,
                        with_agent=other.nutrient_id,
                        action=action,
                    ))
        return candidates

    # ── Escalation ────────────────────────────────────────────────────────

    def _check_escalation(
        self,
        surviving: list[Candidate],
        patient: PatientProfile,
        blocked: list[dict],
    ) -> tuple[bool, list[str]]:
        reasons: list[str] = []

        # CKD 3b+ / hepatic failure
        for _, icd10 in _ESCALATION_TRIGGERS:
            if patient.has_condition(icd10):
                reasons.append(f"Serious condition: {icd10}")

        # Paediatric (dose > RDA)
        if patient.demographics.age < 18:
            reasons.append("Paediatric patient")

        # Pregnancy + any high-risk nutrient
        if patient.demographics.pregnancy_status:
            high_risk = {"vitamin_a", "vitamin_k2", "iodine"}
            for c in surviving:
                if c.nutrient_id in high_risk:
                    reasons.append(f"Pregnancy + {c.nutrient_id}")

        # Dose > 2× RDA for any surviving candidate
        high_dose = [c for c in surviving if c.dose and c.dose.ul_pct_used > 50]
        if high_dose:
            reasons.append(f"High dose: {[c.nutrient_id for c in high_dose]}")

        # ≥2 major drug interactions
        major_count = sum(
            1 for c in surviving
            for w in c.warnings
            if w.severity == WarningSeverity.MAJOR
        )
        if major_count >= 2:
            reasons.append(f"{major_count} major drug interactions detected")

        # Lab out of range
        for lab in patient.labs:
            if lab.flagged:
                reasons.append(f"Flagged lab: {lab.loinc} = {lab.value_num} {lab.unit}")
                break

        return bool(reasons), reasons


# ── Helpers ────────────────────────────────────────────────────────────────

def _interaction_action(severity: Optional[WarningSeverity]) -> str:
    return {
        WarningSeverity.MAJOR: "Seek clinician guidance before taking",
        WarningSeverity.MODERATE: "Separate doses by ≥2 hours",
        WarningSeverity.MINOR: "Monitor; timing may affect absorption",
    }.get(severity or WarningSeverity.MINOR, "Use with caution")
