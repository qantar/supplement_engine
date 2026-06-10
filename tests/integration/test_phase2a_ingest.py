"""Phase 2a integration tests: patient_id scoring and delta lab ingest."""
from __future__ import annotations

import subprocess
from pathlib import Path

import httpx
import pytest

from src.intake.identity import T2DM_RIYADH_PATIENT_ID

pytestmark = pytest.mark.integration

PATIENT_ID = str(T2DM_RIYADH_PATIENT_ID)
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module", autouse=True)
def seed_patient_realm(stack_available: bool, api_base_url: str):
    if not stack_available:
        pytest.skip("Docker stack not available")

    import httpx

    with httpx.Client(base_url=api_base_url, timeout=30.0) as client:
        probe = client.post(
            "/v1/recommendations",
            json={"patient_id": PATIENT_ID, "options": {"max_recommendations": 1}},
        )
        if probe.status_code == 404:
            subprocess.run(
                ["docker", "compose", "exec", "-T", "api", "python", "scripts/seed_patient_realm.py"],
                check=True,
                cwd=str(ROOT),
            )
        elif probe.status_code != 200:
            pytest.fail(f"Patient realm probe failed: {probe.status_code} {probe.text}")


@pytest.mark.asyncio
async def test_recommendations_by_patient_id(require_stack, api_base_url: str):
    async with httpx.AsyncClient(base_url=api_base_url, timeout=30.0) as client:
        resp = await client.post(
            "/v1/recommendations",
            json={"patient_id": PATIENT_ID, "options": {"max_recommendations": 6}},
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["recommendations"]
    nutrient_ids = {r["supplement"]["nutrient_id"] for r in data["recommendations"]}
    assert "vitamin_d3" in nutrient_ids


@pytest.mark.asyncio
async def test_append_lab_delta_then_rescore(require_stack, api_base_url: str):
    async with httpx.AsyncClient(base_url=api_base_url, timeout=30.0) as client:
        lab_resp = await client.post(
            f"/v1/patients/{PATIENT_ID}/labs",
            json={
                "loinc": "2498-4",
                "value": 22,
                "unit": "ug/dL",
                "reference_low": 60,
                "reference_high": 170,
            },
        )
        assert lab_resp.status_code == 201, lab_resp.text
        assert lab_resp.json()["lab_row_id"]

        score = await client.post(
            "/v1/recommendations",
            json={"patient_id": PATIENT_ID, "options": {"max_recommendations": 8}},
        )
        assert score.status_code == 200, score.text
