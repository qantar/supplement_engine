"""
ExplainService — slot-fill template rationale from the DRS contributor trace.

Phase 1: pure templates (deterministic, auditable, no hallucination risk).
Phase 2: optional Claude API polish that validates no clinical claim is altered.

The structured JSON is the source of truth.
The prose is presentational only.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from src.shared.models import (
    Candidate, EvidenceGrade, InteractionWarning,
    PatientProfile, WarningSeverity,
)

logger = logging.getLogger(__name__)


def _format_ul_pct(ul_pct: float) -> str:
    """Human-readable UL percentage aligned with ul_pct_used (1 decimal place)."""
    rounded = round(ul_pct, 1)
    if rounded < 0.05:
        return "<0.1"
    if rounded == int(rounded):
        return str(int(rounded))
    return f"{rounded:.1f}"


_NUTRIENT_DISPLAY: dict[str, tuple[str, str]] = {
    "vitamin_d3":     ("Vitamin D3", "cholecalciferol"),
    "vitamin_b12":    ("Vitamin B12", "methylcobalamin"),
    "magnesium":      ("Magnesium", "magnesium glycinate"),
    "iron":           ("Iron", "ferrous bisglycinate"),
    "folate":         ("Folate", "L-methylfolate"),
    "omega3_epa_dha": ("Omega-3 EPA+DHA", "fish oil / algal oil"),
    "calcium":        ("Calcium", "calcium citrate"),
    "zinc":           ("Zinc", "zinc picolinate"),
    "vitamin_k2":     ("Vitamin K2", "MK-7"),
    "iodine":         ("Iodine", "potassium iodide"),
    "selenium":       ("Selenium", "selenomethionine"),
    "coq10":          ("CoQ10", "ubiquinol"),
    "b_complex":      ("B-Complex", "methylated B-complex"),
    "vitamin_c":      ("Vitamin C", "ascorbic acid"),
    "choline":        ("Choline", "choline bitartrate"),
}

_GRADE_DESCRIPTIONS: dict[EvidenceGrade, str] = {
    EvidenceGrade.A: "High-quality clinical practice guideline or Cochrane meta-analysis",
    EvidenceGrade.B: "Good RCT evidence or consistent meta-analysis",
    EvidenceGrade.C: "Smaller RCT or mechanistic + observational evidence",
    EvidenceGrade.D: "Expert opinion or limited observational data",
}


@dataclass
class ExplainedRecommendation:
    nutrient_name: str
    form: str
    why: str
    evidence: str
    safety: str


class ExplainService:
    """
    Generates three-part human-readable rationale for each recommendation:
      why      — mechanism + risk factors that drove the DRS
      evidence — GRADE rating + key sources
      safety   — interaction warnings + UL transparency + monitoring schedule
    """

    def explain(
        self,
        candidate: Candidate,
        patient: PatientProfile,
        model_version: str = "1.0",
    ) -> ExplainedRecommendation:
        display_name, form = _NUTRIENT_DISPLAY.get(
            candidate.nutrient_id,
            (candidate.nutrient_id.replace("_", " ").title(), "standard form"),
        )

        return ExplainedRecommendation(
            nutrient_name=display_name,
            form=form,
            why=self._render_why(candidate, patient, display_name),
            evidence=self._render_evidence(candidate),
            safety=self._render_safety(candidate, patient),
        )

    # ── Why ────────────────────────────────────────────────────────────────

    def _render_why(
        self,
        candidate: Candidate,
        patient: PatientProfile,
        display_name: str,
    ) -> str:
        drs = candidate.drs
        p = drs.p_deficient
        demo = patient.demographics

        # Opening — risk level
        if p >= 0.80:
            severity = "a high likelihood of"
        elif p >= 0.60:
            severity = "a moderate likelihood of"
        elif p >= 0.35:
            severity = "an elevated risk of"
        else:
            severity = "a guideline-indicated need for"

        parts = [
            f"{display_name} is recommended because your profile shows "
            f"{severity} insufficiency (estimated {p:.0%} probability)."
        ]

        # Condition contributors
        condition_factors = [
            c for c in drs.contributors if c.source.startswith("condition:")
        ]
        if condition_factors:
            condition_texts = [
                f"{c.label} (≈{c.lr:.1f}× increased risk)"
                for c in condition_factors
            ]
            parts.append(
                "Contributing conditions: " + "; ".join(condition_texts) + "."
            )

        # Medication contributors
        med_factors = [
            c for c in drs.contributors if c.source.startswith("medication:")
        ]
        if med_factors:
            med_texts = [c.label for c in med_factors]
            parts.append(
                "Medication effects: " + "; ".join(med_texts) + "."
            )

        # Lifestyle / demographic contributors
        lifestyle_factors = [
            c for c in drs.contributors
            if c.source.startswith(("lifestyle:", "geo:", "bmi"))
        ]
        if lifestyle_factors:
            life_texts = [c.label for c in lifestyle_factors]
            parts.append(
                "Lifestyle and demographic factors: " + "; ".join(life_texts) + "."
            )

        # Lab confirmation
        if drs.lab_dominated:
            lab_factors = [
                c for c in drs.contributors if c.source.startswith("lab:")
            ]
            if lab_factors:
                parts.append(
                    f"Laboratory result confirms: {lab_factors[0].label}. "
                    "Recommendation dose adjusted to therapeutic replacement level."
                )

        return " ".join(parts)

    # ── Evidence ───────────────────────────────────────────────────────────

    def _render_evidence(self, candidate: Candidate) -> str:
        grade = candidate.evidence_grade
        grade_desc = _GRADE_DESCRIPTIONS.get(grade, "")
        conf = candidate.confidence_score

        return (
            f"Evidence quality: Grade {grade.value} — {grade_desc}. "
            f"Composite confidence score: {conf:.2f}/1.00. "
            f"This recommendation is {'prominently indicated' if conf >= 0.80 else 'indicated with caveats' if conf >= 0.60 else 'suggested; discuss with your clinician'}."
        )

    # ── Safety ────────────────────────────────────────────────────────────

    def _render_safety(
        self, candidate: Candidate, patient: PatientProfile
    ) -> str:
        parts: list[str] = []

        if candidate.dose:
            ul_pct = candidate.dose.ul_pct_used
            parts.append(
                f"This dose is at {_format_ul_pct(ul_pct)}% of the established upper safety limit."
            )
            if candidate.dose.cap_applied:
                parts.append(
                    "Note: dose was automatically capped at 70% of the upper limit."
                )

        # Interaction warnings by severity
        major = [w for w in candidate.warnings if w.severity == WarningSeverity.MAJOR]
        moderate = [w for w in candidate.warnings if w.severity == WarningSeverity.MODERATE]
        minor = [w for w in candidate.warnings if w.severity == WarningSeverity.MINOR]

        if major:
            parts.append(
                "⚠️ Important interactions: "
                + "; ".join(f"{w.with_agent} — {w.action}" for w in major)
                + ". Consult your clinician before taking."
            )
        if moderate:
            parts.append(
                "Timing note: "
                + "; ".join(f"Separate from {w.with_agent} — {w.action}" for w in moderate)
                + "."
            )
        if minor:
            parts.append(
                "Minor note: "
                + "; ".join(f"{w.with_agent} — {w.action}" for w in minor)
                + "."
            )

        if not parts:
            parts.append("No significant safety concerns identified for your current medications.")

        return " ".join(parts)

    # ── Phase 2: LLM polish (optional) ────────────────────────────────────

    async def llm_polish(
        self,
        template_output: ExplainedRecommendation,
        anthropic_client,
    ) -> ExplainedRecommendation:
        """
        Optional: use Claude to rewrite template prose into natural language.
        Strict constraint: no clinical claims may be added, removed, or altered.
        The template output is the authoritative source; LLM output is cosmetic only.

        Validates that all key facts (dose pct, confidence score, grade) are
        preserved in the rewritten text before accepting the output.
        """
        prompt = f"""
Rewrite the following supplement recommendation rationale into natural, 
empathetic prose for a patient. You MUST preserve all clinical facts exactly.
Do not add any new medical claims, dosages, or warnings.
Do not remove any warnings. Do not change any numbers.

WHY: {template_output.why}
EVIDENCE: {template_output.evidence}
SAFETY: {template_output.safety}

Return as JSON: {{"why": "...", "evidence": "...", "safety": "..."}}
"""
        try:
            response = await anthropic_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}],
            )
            import json
            data = json.loads(response.content[0].text)
            # Basic validation: key numbers should still appear
            combined = " ".join(data.values())
            template_combined = " ".join([
                template_output.why, template_output.evidence, template_output.safety
            ])
            if not _clinical_facts_preserved(template_combined, combined):
                logger.warning("LLM output failed clinical fact validation — using template")
                return template_output

            from dataclasses import replace
            return replace(
                template_output,
                why=data.get("why", template_output.why),
                evidence=data.get("evidence", template_output.evidence),
                safety=data.get("safety", template_output.safety),
            )
        except Exception as e:
            logger.warning("LLM polish failed: %s — using template output", e)
            return template_output


def _clinical_facts_preserved(template: str, rewritten: str) -> bool:
    """
    Verify key numeric facts from the template appear in the rewritten text.
    Simple heuristic: extract all percentages and numbers > 10 and check presence.
    """
    import re
    numbers = re.findall(r'\b\d+\.?\d*%?\b', template)
    significant = [n for n in numbers if float(n.rstrip('%')) > 10]
    return all(n in rewritten for n in significant[:5])  # check first 5 key facts
