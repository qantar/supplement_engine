"""End-to-end integration tests against the running Docker stack."""
from __future__ import annotations

import httpx
import pytest


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_full_recommendation_session(
    require_stack, api_base_url: str, t2dm_patient_payload: dict,
):
    async with httpx.AsyncClient(base_url=api_base_url, timeout=30.0) as client:
        resp = await client.post("/v1/recommendations", json=t2dm_patient_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"]
    assert data["recommendations"]
    assert len(data["recommendations"]) >= 1
    assert data["recommendations"][0]["rank"] == 1
    assert data["evidence_snapshot_id"].startswith("kg-")
    assert data["model_version"] == "rec-engine-1.0.0"
    nutrient_ids = {r["supplement"]["nutrient_id"] for r in data["recommendations"]}
    assert "vitamin_d3" in nutrient_ids


@pytest.mark.asyncio
async def test_safety_block_hemochromatosis_iron(
    require_stack, api_base_url: str, hemochromatosis_patient_payload: dict,
):
    async with httpx.AsyncClient(base_url=api_base_url, timeout=30.0) as client:
        resp = await client.post("/v1/recommendations", json=hemochromatosis_patient_payload)
    assert resp.status_code == 200
    data = resp.json()
    rec_nutrients = {r["supplement"]["nutrient_id"] for r in data["recommendations"]}
    assert "iron" not in rec_nutrients
    suppressed = data.get("suppressed", [])
    assert len(suppressed) >= 1
    iron_blocks = [s for s in suppressed if s.get("nutrient_id") == "iron"]
    assert iron_blocks, "iron must appear in suppressed with hemochromatosis + low iron lab"
    assert any(
        "hemochromatosis" in (s.get("reason") or "").lower()
        or "Hemochromatosis" in (s.get("reason") or "")
        for s in iron_blocks
    )


@pytest.mark.asyncio
async def test_celiac_recommends_malabsorption_nutrients(
    require_stack, api_base_url: str, celiac_patient_payload: dict,
):
    async with httpx.AsyncClient(base_url=api_base_url, timeout=30.0) as client:
        resp = await client.post("/v1/recommendations", json=celiac_patient_payload)
    assert resp.status_code == 200
    data = resp.json()
    rec_nutrients = {r["supplement"]["nutrient_id"] for r in data["recommendations"]}
    celiac_expected = {"iron", "folate", "vitamin_d3", "vitamin_b12", "calcium", "zinc"}
    assert rec_nutrients & celiac_expected, (
        f"Expected at least one celiac malabsorption nutrient in {rec_nutrients}"
    )


@pytest.mark.asyncio
async def test_postgres_persistence(
    require_stack, api_base_url: str, t2dm_patient_payload: dict,
):
    async with httpx.AsyncClient(base_url=api_base_url, timeout=30.0) as client:
        create = await client.post("/v1/recommendations", json=t2dm_patient_payload)
        assert create.status_code == 200
        session_id = create.json()["session_id"]

        fetch = await client.get(f"/v1/sessions/{session_id}")
        assert fetch.status_code == 200
        stored = fetch.json()
        assert stored["session_id"] == session_id
        assert len(stored["recommendations"]) == len(create.json()["recommendations"])


@pytest.mark.asyncio
async def test_audit_log_input_hash(
    require_stack, api_base_url: str, t2dm_patient_payload: dict,
):
    async with httpx.AsyncClient(base_url=api_base_url, timeout=30.0) as client:
        create = await client.post("/v1/recommendations", json=t2dm_patient_payload)
        session_id = create.json()["session_id"]

        audit = await client.get(f"/v1/audit/{session_id}")
        assert audit.status_code == 200
        record = audit.json()
        assert record["input_hash"]
        assert len(record["input_hash"]) == 64  # SHA-256 hex


@pytest.mark.asyncio
async def test_evidence_snapshot_persisted(
    require_stack, api_base_url: str, t2dm_patient_payload: dict,
):
    async with httpx.AsyncClient(base_url=api_base_url, timeout=30.0) as client:
        create = await client.post("/v1/recommendations", json=t2dm_patient_payload)
        data = create.json()
        snapshot_id = data["evidence_snapshot_id"]
        assert snapshot_id.startswith("kg-")

        session = await client.get(f"/v1/sessions/{data['session_id']}")
        assert session.json()["evidence_snapshot_id"] == snapshot_id

        evidence = await client.get(f"/v1/evidence/{snapshot_id}")
        assert evidence.status_code == 200
        snap = evidence.json()
        assert snap["snapshot_id"] == snapshot_id
        assert snap["kg_commit_sha"]
        assert snap["contents"]
        assert snap["contents"].get("nutrient_count", 0) > 0
