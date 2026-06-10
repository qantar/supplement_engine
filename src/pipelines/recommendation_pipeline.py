"""
RecommendationPipeline — orchestrates all stages end-to-end.

This is the entry point for every recommendation request.
It composes the services like LEGO bricks — each stage gets typed inputs,
returns typed outputs. The pipeline owns the session lifecycle.

Pipeline stages:
  1. DRS scoring (concurrent per nutrient)
  2. Candidate generation (threshold + guideline)
  3. Dose optimization (per candidate)
  4. Safety gate (interaction filter + UL enforcement)
  5. Confidence scoring + ranking
  6. Explanation generation
  7. Audit logging
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.db.repositories import RecommendationRepository

from src.core.candidate_generator import (
    CandidateGenerator, ConfidenceCompositor, DoseOptimizer,
)
from src.core.deficiency_risk_scorer import DeficiencyRiskScorer
from src.explain.explain_service import ExplainService
from src.knowledge.graph_client import GraphClient
from src.personalization.engine import PersonalizationEngine
from src.safety.safety_engine import SafetyEngine
from src.shared.models import (
    Candidate, EvidenceGrade, EvidenceSnapshot, PatientProfile, RecommendationOutput,
    RecommendationSession,
)

logger = logging.getLogger(__name__)

MODEL_VERSION = "rec-engine-1.0.0"


class RecommendationPipeline:
    """
    Stateless pipeline — safe to share across concurrent requests.
    All state lives in the PatientProfile input and the returned Session.
    """

    def __init__(
        self,
        graph_client: GraphClient,
        max_recommendations: int = 8,
        drs_threshold: float = 0.35,
        min_confidence: float = 0.40,
        model_version: str = MODEL_VERSION,
        personalization: Optional[PersonalizationEngine] = None,
        personalization_enabled: bool = False,
    ):
        self._kg = graph_client
        self._model_version = model_version
        self._personalization = personalization
        self._personalization_enabled = personalization_enabled
        self._scorer = DeficiencyRiskScorer(graph_client)
        self._candidate_gen = CandidateGenerator(graph_client, drs_threshold)
        self._dose_optimizer = DoseOptimizer(graph_client)
        self._safety = SafetyEngine(graph_client)
        self._confidence = ConfidenceCompositor()
        self._explain = ExplainService()
        self._max_recs = max_recommendations
        self._min_confidence = min_confidence

    async def evaluate(
        self,
        patient: PatientProfile,
        include_low_confidence: bool = False,
        nutrient_ids: Optional[list[str]] = None,
        rec_repo: Optional["RecommendationRepository"] = None,
    ) -> RecommendationSession:
        session_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc)
        logger.info("Session %s started for patient %s", session_id, patient.patient_id)

        # ── Stage 1: DRS scoring (concurrent) ────────────────────────────
        drs_scores = await self._scorer.score_all(patient, nutrient_ids)
        if (
            self._personalization_enabled
            and self._personalization is not None
            and rec_repo is not None
        ):
            priors = await self._personalization.load_longitudinal_priors(
                patient.patient_id, rec_repo
            )
            if priors:
                drs_scores = self._personalization.apply_longitudinal_priors(
                    drs_scores, priors
                )
                logger.info(
                    "Stage 1b personalization: blended priors for %d nutrients",
                    len(priors),
                )
        drs_snapshot = {
            nid: round(drs.p_deficient, 6) for nid, drs in drs_scores.items()
        }
        logger.info("Stage 1 complete: %d nutrients scored", len(drs_scores))

        # ── Stage 2: Candidate generation ─────────────────────────────────
        candidates = await self._candidate_gen.generate(drs_scores, patient)
        logger.info("Stage 2 complete: %d candidates generated", len(candidates))

        # ── Stage 3: Dose optimization (concurrent per candidate) ─────────
        dose_tasks = [
            self._dose_optimizer.optimize(c, patient)
            for c in candidates
        ]
        doses = await asyncio.gather(*dose_tasks)
        for candidate, dose in zip(candidates, doses):
            candidate.dose = dose
        logger.info("Stage 3 complete: doses computed")

        # ── Stage 4: Safety gate ───────────────────────────────────────────
        filter_result = await self._safety.run(candidates, patient)
        logger.info(
            "Stage 4 complete: %d surviving, %d blocked",
            len(filter_result.surviving), len(filter_result.blocked)
        )

        # ── Stage 5: Confidence scoring + ranking ─────────────────────────
        for candidate in filter_result.surviving:
            conf = self._confidence.compute(candidate, patient)
            candidate.confidence_score = conf
            candidate.evidence_grade = self._confidence.grade(conf)
            candidate.rank_score = self._confidence.rank_score(candidate)

        # Filter by confidence threshold
        if not include_low_confidence:
            filter_result.surviving = [
                c for c in filter_result.surviving
                if c.confidence_score >= self._min_confidence
            ]

        # Sort by rank score descending
        filter_result.surviving.sort(key=lambda c: c.rank_score, reverse=True)
        top_candidates = filter_result.surviving[:self._max_recs]
        logger.info("Stage 5 complete: %d final recommendations", len(top_candidates))

        # ── Stage 6: Explanation generation ──────────────────────────────
        explanation_tasks = [
            asyncio.to_thread(self._explain.explain, c, patient)
            for c in top_candidates
        ]
        explanations = await asyncio.gather(*explanation_tasks)

        # ── Stage 7: Assemble outputs ─────────────────────────────────────
        evidence_snapshot = await self._snapshot_evidence(session_id)
        evidence_snapshot_id = evidence_snapshot.snapshot_id
        outputs: list[RecommendationOutput] = []

        for rank, (candidate, explanation) in enumerate(
            zip(top_candidates, explanations), start=1
        ):
            output = RecommendationOutput(
                rec_id=uuid.uuid4(),
                session_id=session_id,
                patient_id=patient.patient_id,
                nutrient_id=candidate.nutrient_id,
                nutrient_name=explanation.nutrient_name,
                form=explanation.form,
                dose=candidate.dose,
                rank=rank,
                confidence_score=candidate.confidence_score,
                evidence_grade=candidate.evidence_grade,
                warnings=tuple(candidate.warnings),
                requires_clinician=filter_result.escalate,
                rationale_why=explanation.why,
                rationale_evidence=explanation.evidence,
                rationale_safety=explanation.safety,
                model_version=self._model_version,
                evidence_snapshot_id=evidence_snapshot_id,
                served_at=datetime.now(timezone.utc),
            )
            outputs.append(output)

        elapsed_ms = (datetime.now(timezone.utc) - started_at).total_seconds() * 1000
        logger.info("Session %s complete in %.0fms", session_id, elapsed_ms)

        return RecommendationSession(
            session_id=session_id,
            patient_id=patient.patient_id,
            model_version=self._model_version,
            evidence_snapshot_id=evidence_snapshot_id,
            recommendations=outputs,
            suppressed=filter_result.blocked,
            requires_clinician=filter_result.escalate,
            clinician_handoff=self._build_handoff(
                filter_result.escalate, filter_result.escalation_reasons, outputs
            ),
            next_review_weeks=_review_schedule(top_candidates),
            served_at=datetime.now(timezone.utc),
            evidence_snapshot=evidence_snapshot,
            drs_snapshot=drs_snapshot,
        )

    async def _snapshot_evidence(self, session_id: str) -> EvidenceSnapshot:
        """Capture KG version, stats, and content hash for regulatory reproducibility."""
        kg_version = await self._kg.get_kg_version()
        stats = await self._kg.get_kg_stats()
        contents = {"kg_version": kg_version, **stats}
        contents["content_hash"] = hashlib.sha256(
            json.dumps(contents, sort_keys=True).encode()
        ).hexdigest()
        snapshot_id = f"kg-{kg_version}-{session_id[:8]}"
        return EvidenceSnapshot(
            snapshot_id=snapshot_id,
            kg_version=kg_version,
            contents=contents,
        )

    def _build_handoff(
        self,
        escalate: bool,
        reasons: list[str],
        outputs: list[RecommendationOutput],
    ) -> Optional[str]:
        if not escalate:
            return None
        reason_text = "; ".join(reasons)
        nutrient_summary = ", ".join(o.nutrient_name for o in outputs[:5])
        return (
            f"Clinician review recommended. Reasons: {reason_text}. "
            f"Indicated supplements: {nutrient_summary}. "
            f"Model version: {self._model_version}."
        )


def _review_schedule(candidates: list[Candidate]) -> int:
    """
    Return recommended follow-up weeks based on the highest-priority candidate.
    Lab-dominated recommendations need earlier re-check.
    """
    if any(c.drs.lab_dominated for c in candidates):
        return 8    # therapeutic replacement — re-check lab sooner
    if any(c.drs.p_deficient > 0.80 for c in candidates):
        return 12
    return 24
