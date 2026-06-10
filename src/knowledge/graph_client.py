"""
Neo4j knowledge graph client.
Every clinical claim — disease→nutrient LR, drug→nutrient depletion,
contraindication rule — lives here as a typed, evidence-weighted edge.

Pattern: async context manager + connection pooling via the official driver.
All queries return typed domain objects, never raw dicts.
"""
from __future__ import annotations

import hashlib
import json
import logging
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from typing import AsyncIterator, Optional

from neo4j import AsyncGraphDatabase, AsyncDriver
from neo4j.exceptions import ServiceUnavailable

from src.shared.models import (
    KGEdge, NutrientMeta, WarningSeverity, Demographics
)

logger = logging.getLogger(__name__)

CACHE_TTL_NUTRIENT = 3600       # 1 hour
CACHE_TTL_BASELINE = 86400      # 24 hours
CACHE_TTL_GUIDELINE = 86400     # 24 hours


@dataclass(frozen=True)
class GuidelineRecommendation:
    nutrient_id: str
    issuing_body: str
    dose: Optional[float]
    dose_unit: Optional[str]
    population: str
    strength: str          # "strong" | "conditional" | "weak"
    grade_weight: float


@dataclass(frozen=True)
class ContraindictionRule:
    nutrient_id: str
    condition_code: str
    severity: WarningSeverity
    mechanism: str


class GraphClient:
    """
    Async Neo4j client with typed query methods.
    Inject this into every service that needs clinical knowledge.
    Never let raw Cypher leak past this class boundary.
    """

    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        database: str = "neo4j",
        redis_url: str | None = None,
    ):
        self._driver: AsyncDriver = AsyncGraphDatabase.driver(
            uri, auth=(user, password), max_connection_pool_size=50
        )
        self._database = database
        self._redis = None
        if redis_url:
            try:
                import redis.asyncio as aioredis
                self._redis = aioredis.from_url(redis_url, decode_responses=True)
            except Exception as exc:
                logger.warning("Redis unavailable — caching disabled: %s", exc)

    async def close(self) -> None:
        if self._redis:
            await self._redis.aclose()
        await self._driver.close()

    async def health_check(self) -> bool:
        try:
            async with self._driver.session(database=self._database) as session:
                await session.run("RETURN 1")
            return True
        except ServiceUnavailable:
            return False

    async def _cache_get(self, key: str) -> Optional[str]:
        if not self._redis:
            return None
        try:
            return await self._redis.get(key)
        except Exception as exc:
            logger.warning("Redis GET failed for %s: %s", key, exc)
            return None

    async def _cache_set(self, key: str, value: str, ttl: int) -> None:
        if not self._redis:
            return
        try:
            await self._redis.setex(key, ttl, value)
        except Exception as exc:
            logger.warning("Redis SET failed for %s: %s", key, exc)

    # ── KG versioning ──────────────────────────────────────────────────────

    async def get_kg_version(self) -> str:
        """Return curator-controlled KG version or Neo4j component version."""
        query = """
        MATCH (m:KGMetadata {id: 'current'})
        RETURN m.version AS version
        LIMIT 1
        """
        async with self._driver.session(database=self._database) as session:
            result = await session.run(query)
            record = await result.single()
            if record and record.get("version"):
                return str(record["version"])

        fallback = """
        CALL dbms.components() YIELD versions
        RETURN versions[0] AS version
        LIMIT 1
        """
        async with self._driver.session(database=self._database) as session:
            result = await session.run(fallback)
            record = await result.single()
            if record and record.get("version"):
                return str(record["version"])
        return "unknown"

    async def get_kg_stats(self) -> dict:
        """Aggregate KG counts for evidence snapshot content hash."""
        query = """
        MATCH (n:Nutrient) WITH count(n) AS nutrient_count
        MATCH ()-[r]->() WITH nutrient_count, count(r) AS edge_count
        RETURN nutrient_count, edge_count
        """
        async with self._driver.session(database=self._database) as session:
            result = await session.run(query)
            record = await result.single()
            if not record:
                return {"nutrient_count": 0, "edge_count": 0}
            stats = {
                "nutrient_count": int(record["nutrient_count"]),
                "edge_count": int(record["edge_count"]),
            }
            stats["content_hash"] = hashlib.sha256(
                json.dumps(stats, sort_keys=True).encode()
            ).hexdigest()[:16]
            return stats

    # ── Baseline prevalence ────────────────────────────────────────────────

    async def get_baseline_prevalence(
        self, nutrient_id: str, demo: Demographics
    ) -> float:
        """
        Fetch population baseline P(deficient) for a nutrient given a
        demographic bucket. Falls back to global default (0.30) if no
        specific bucket found.
        """
        age_group = _age_bucket(demo.age)
        cache_key = f"baseline:{nutrient_id}:{demo.region_code}:{demo.sex.value}:{age_group}"
        cached = await self._cache_get(cache_key)
        if cached is not None:
            return float(cached)

        query = """
        MATCH (d:Demographic)-[r:HAS_BASELINE_RISK]->(n:Nutrient {nutrient_id: $nutrient_id})
        WHERE d.region_code = $region OR d.region_code IS NULL
        AND d.sex = $sex OR d.sex IS NULL
        AND d.age_group = $age_group OR d.age_group IS NULL
        RETURN r.prevalence AS prevalence
        ORDER BY r.specificity DESC
        LIMIT 1
        """
        async with self._driver.session(database=self._database) as session:
            result = await session.run(
                query,
                nutrient_id=nutrient_id,
                region=demo.region_code,
                sex=demo.sex.value,
                age_group=age_group,
            )
            record = await result.single()
            prevalence = float(record["prevalence"]) if record else 0.30

        await self._cache_set(cache_key, str(prevalence), CACHE_TTL_BASELINE)
        return prevalence

    # ── Condition → Nutrient edges ─────────────────────────────────────────

    async def get_condition_edges(
        self, icd10_code: str, nutrient_id: str
    ) -> list[KGEdge]:
        """
        Returns INCREASES_DEMAND_FOR and CAUSES_MALABSORPTION_OF edges
        between a condition and a nutrient. Both relationship types drive
        the DRS upward.
        """
        query = """
        MATCH (c:Condition {icd10_code: $icd10_code})
              -[r:INCREASES_DEMAND_FOR|CAUSES_MALABSORPTION_OF]->
              (n:Nutrient {nutrient_id: $nutrient_id})
        RETURN type(r) AS rel_type,
               r.lr AS lr,
               r.lr_ci_lower AS lr_ci_lower,
               r.lr_ci_upper AS lr_ci_upper,
               r.mechanism AS mechanism,
               r.grade_weight AS grade_weight,
               r.evidence_ids AS evidence_ids
        """
        async with self._driver.session(database=self._database) as session:
            result = await session.run(
                query, icd10_code=icd10_code, nutrient_id=nutrient_id
            )
            return [_record_to_edge(r, icd10_code, nutrient_id) async for r in result]

    # ── Drug → Nutrient edges ──────────────────────────────────────────────

    async def get_depletion_edges(
        self, rxnorm_cui: str, nutrient_id: str
    ) -> list[KGEdge]:
        """DEPLETES edges: metformin→B12 (LR 2.4, onset 12mo)."""
        query = """
        MATCH (m:Medication {rxnorm_cui: $rxnorm_cui})
              -[r:DEPLETES]->
              (n:Nutrient {nutrient_id: $nutrient_id})
        RETURN type(r) AS rel_type,
               r.lr AS lr,
               r.lr_ci_lower AS lr_ci_lower,
               r.lr_ci_upper AS lr_ci_upper,
               r.mechanism AS mechanism,
               r.onset_months AS onset_months,
               r.grade_weight AS grade_weight,
               r.evidence_ids AS evidence_ids
        """
        async with self._driver.session(database=self._database) as session:
            result = await session.run(
                query, rxnorm_cui=rxnorm_cui, nutrient_id=nutrient_id
            )
            return [_record_to_edge(r, rxnorm_cui, nutrient_id) async for r in result]

    async def get_interaction_edges(
        self, rxnorm_cui: str, nutrient_id: str
    ) -> list[KGEdge]:
        """INTERACTS_WITH edges for the safety layer (4-tier severity)."""
        query = """
        MATCH (m:Medication {rxnorm_cui: $rxnorm_cui})
              -[r:INTERACTS_WITH]->
              (n:Nutrient {nutrient_id: $nutrient_id})
        RETURN type(r) AS rel_type,
               r.severity AS severity,
               r.lr AS lr,
               r.lr_ci_lower AS lr_ci_lower,
               r.lr_ci_upper AS lr_ci_upper,
               r.mechanism AS mechanism,
               r.action AS action,
               r.grade_weight AS grade_weight,
               r.evidence_ids AS evidence_ids
        """
        async with self._driver.session(database=self._database) as session:
            result = await session.run(
                query, rxnorm_cui=rxnorm_cui, nutrient_id=nutrient_id
            )
            return [_record_to_edge(r, rxnorm_cui, nutrient_id) async for r in result]

    # ── Nutrient ↔ Nutrient ────────────────────────────────────────────────

    async def get_antagonist_pairs(
        self, nutrient_ids: list[str]
    ) -> list[tuple[str, str, str]]:
        """
        Returns (nutrient_a, nutrient_b, action) for all ANTAGONIZES edges
        within the candidate set. Used by the safety layer to add timing warnings.
        """
        query = """
        MATCH (a:Nutrient)-[r:ANTAGONIZES]->(b:Nutrient)
        WHERE a.nutrient_id IN $ids AND b.nutrient_id IN $ids
        RETURN a.nutrient_id AS a, b.nutrient_id AS b, r.action AS action
        """
        async with self._driver.session(database=self._database) as session:
            result = await session.run(query, ids=nutrient_ids)
            return [(r["a"], r["b"], r["action"]) async for r in result]

    # ── Contraindications ──────────────────────────────────────────────────

    async def get_contraindications(
        self, nutrient_id: str
    ) -> list[ContraindictionRule]:
        query = """
        MATCH (n:Nutrient {nutrient_id: $nutrient_id})
              -[r:CONTRAINDICATED_IN]->
              (c:Condition)
        RETURN c.icd10_code AS condition_code,
               r.severity AS severity,
               r.mechanism AS mechanism
        """
        async with self._driver.session(database=self._database) as session:
            result = await session.run(query, nutrient_id=nutrient_id)
            rules = []
            async for r in result:
                rules.append(ContraindictionRule(
                    nutrient_id=nutrient_id,
                    condition_code=r["condition_code"],
                    severity=WarningSeverity(r["severity"]),
                    mechanism=r["mechanism"] or "",
                ))
            return rules

    # ── Guidelines ────────────────────────────────────────────────────────

    async def get_guideline(
        self, nutrient_id: str, demo: Demographics
    ) -> Optional[GuidelineRecommendation]:
        """
        Returns the strongest matching guideline for a nutrient/population.
        Pregnancy overrides all others.
        """
        population = _population_key(demo)
        cache_key = f"guideline:{nutrient_id}:{population}"
        cached = await self._cache_get(cache_key)
        if cached is not None:
            if cached == "__none__":
                return None
            data = json.loads(cached)
            return GuidelineRecommendation(**data)

        query = """
        MATCH (g:Guideline)-[r:RECOMMENDS]->(n:Nutrient {nutrient_id: $nutrient_id})
        WHERE r.population = $population OR r.population = 'general'
        RETURN g.issuing_body AS issuing_body,
               r.dose AS dose,
               r.dose_unit AS dose_unit,
               r.population AS population,
               r.strength AS strength,
               r.grade_weight AS grade_weight
        ORDER BY r.grade_weight DESC
        LIMIT 1
        """
        async with self._driver.session(database=self._database) as session:
            result = await session.run(
                query, nutrient_id=nutrient_id, population=population
            )
            record = await result.single()
            if not record:
                await self._cache_set(cache_key, "__none__", CACHE_TTL_GUIDELINE)
                return None
            guideline = GuidelineRecommendation(
                nutrient_id=nutrient_id,
                issuing_body=record["issuing_body"],
                dose=record["dose"],
                dose_unit=record["dose_unit"],
                population=record["population"],
                strength=record["strength"],
                grade_weight=float(record["grade_weight"]),
            )
            await self._cache_set(
                cache_key,
                json.dumps(asdict(guideline)),
                CACHE_TTL_GUIDELINE,
            )
            return guideline

    # ── Nutrient metadata ──────────────────────────────────────────────────

    async def get_nutrient_meta(self, nutrient_id: str) -> Optional[NutrientMeta]:
        cache_key = f"nutrient:{nutrient_id}"
        cached = await self._cache_get(cache_key)
        if cached is not None:
            data = json.loads(cached)
            data["loinc_codes"] = tuple(data.get("loinc_codes") or [])
            return NutrientMeta(**data)

        query = """
        MATCH (n:Nutrient {nutrient_id: $nutrient_id})
        RETURN n.name AS name, n.form AS form, n.rda AS rda,
               n.ear AS ear, n.ul AS ul, n.dose_unit AS dose_unit,
               n.bioavailability_factor AS bio, n.loinc_codes AS loinc_codes
        """
        async with self._driver.session(database=self._database) as session:
            result = await session.run(query, nutrient_id=nutrient_id)
            r = await result.single()
            if not r:
                return None
            meta = NutrientMeta(
                nutrient_id=nutrient_id,
                name=r["name"],
                form=r["form"],
                rda=float(r["rda"]),
                ear=float(r["ear"]),
                ul=float(r["ul"]),
                dose_unit=r["dose_unit"],
                bioavailability_factor=float(r["bio"] or 1.0),
                loinc_codes=tuple(r["loinc_codes"] or []),
            )

        payload = asdict(meta)
        payload["loinc_codes"] = list(meta.loinc_codes)
        await self._cache_set(cache_key, json.dumps(payload), CACHE_TTL_NUTRIENT)
        return meta

    async def get_all_nutrient_ids(self) -> list[str]:
        async with self._driver.session(database=self._database) as session:
            result = await session.run("MATCH (n:Nutrient) RETURN n.nutrient_id AS id")
            return [r["id"] async for r in result]


# ── Private helpers ────────────────────────────────────────────────────────

def _record_to_edge(record, source_id: str, target_id: str) -> KGEdge:
    severity_raw = record.get("severity")
    return KGEdge(
        rel_type=record["rel_type"],
        source_id=source_id,
        target_id=target_id,
        lr=float(record.get("lr") or 1.0),
        lr_ci_lower=float(record.get("lr_ci_lower") or 1.0),
        lr_ci_upper=float(record.get("lr_ci_upper") or 1.0),
        mechanism=record.get("mechanism"),
        onset_months=record.get("onset_months"),
        severity=WarningSeverity(severity_raw) if severity_raw else None,
        grade_weight=float(record.get("grade_weight") or 0.5),
        evidence_ids=tuple(record.get("evidence_ids") or []),
    )

def _age_bucket(age: int) -> str:
    if age < 18:   return "child"
    if age < 30:   return "adult_18_29"
    if age < 50:   return "adult_30_49"
    if age < 65:   return "adult_50_64"
    return "adult_65_plus"

def _population_key(demo: Demographics) -> str:
    if demo.pregnancy_status:
        return "pregnancy"
    if demo.lactation_status:
        return "lactation"
    if demo.age < 18:
        return "paediatric"
    return f"{demo.sex.value.lower()}_adult"
