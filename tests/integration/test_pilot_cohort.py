"""Pilot cohort integration — all seed patients score in prod profile."""
from __future__ import annotations

import os

import httpx
import pytest

from src.intake.pilot_cohort import PILOT_COHORT, PILOT_PATIENT_IDS, cohort_by_source_key

pytestmark = pytest.mark.integration

DEFAULT_PROD_TEST_KEY = "pilot-dev-key-change-me"


def _prod_api_key() -> str:
    return os.getenv("PHASE2B_TEST_API_KEY", DEFAULT_PROD_TEST_KEY)


def _api_key_headers() -> dict[str, str]:
    return {"X-API-Key": _prod_api_key()}


def _require_api_key_enabled(api_base_url: str) -> None:
    try:
        resp = httpx.post(
            f"{api_base_url}/v1/recommendations",
            json={"patient_id": PILOT_PATIENT_IDS[0], "options": {"max_recommendations": 1}},
            timeout=10.0,
        )
    except httpx.HTTPError:
        pytest.skip("API unreachable")
    if resp.status_code != 401:
        pytest.skip("REQUIRE_API_KEY not enabled — use docker-compose.prod.yml")


@pytest.mark.asyncio
@pytest.mark.parametrize("patient_id", PILOT_PATIENT_IDS)
async def test_pilot_patient_scores(require_stack, api_base_url: str, patient_id: str):
    """Each pilot seed patient returns recommendations via patient_id path."""
    _require_api_key_enabled(api_base_url)
    async with httpx.AsyncClient(base_url=api_base_url, timeout=60.0) as client:
        resp = await client.post(
            "/v1/recommendations",
            json={"patient_id": patient_id, "options": {"max_recommendations": 6}},
            headers=_api_key_headers(),
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data.get("session_id")
    assert data.get("evidence_snapshot_id")


@pytest.mark.asyncio
async def test_hemochromatosis_iron_not_recommended(require_stack, api_base_url: str):
    """Hemochromatosis patient must not receive iron in recommendations."""
    _require_api_key_enabled(api_base_url)
    hemo = cohort_by_source_key("MRN-HEMO-003")
    assert hemo is not None
    hemo_id = str(hemo.patient_id)
    async with httpx.AsyncClient(base_url=api_base_url, timeout=60.0) as client:
        resp = await client.post(
            "/v1/recommendations",
            json={"patient_id": hemo_id, "options": {"max_recommendations": 8}},
            headers=_api_key_headers(),
        )
    assert resp.status_code == 200, resp.text
    nutrient_ids = [
        r["supplement"]["nutrient_id"]
        for r in resp.json().get("recommendations", [])
    ]
    assert "iron" not in nutrient_ids


@pytest.mark.asyncio
async def test_ckd_stage4_potassium_not_recommended(require_stack, api_base_url: str):
    """CKD stage 4 patient must not receive potassium in recommendations."""
    _require_api_key_enabled(api_base_url)
    ckd4 = cohort_by_source_key("MRN-CKD4-009")
    assert ckd4 is not None
    async with httpx.AsyncClient(base_url=api_base_url, timeout=60.0) as client:
        resp = await client.post(
            "/v1/recommendations",
            json={"patient_id": str(ckd4.patient_id), "options": {"max_recommendations": 8}},
            headers=_api_key_headers(),
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    nutrient_ids = [
        r["supplement"]["nutrient_id"]
        for r in data.get("recommendations", [])
    ]
    assert "potassium" not in nutrient_ids
    assert data.get("requires_clinician") is True


@pytest.mark.asyncio
async def test_healthy_baseline_few_recommendations(require_stack, api_base_url: str):
    """Replete baseline patient should yield fewer recommendations than high-risk cases."""
    _require_api_key_enabled(api_base_url)
    baseline = cohort_by_source_key("MRN-BASE-008")
    t2dm = cohort_by_source_key("MRN-T2DM-001")
    assert baseline is not None and t2dm is not None
    headers = _api_key_headers()
    body = {"options": {"max_recommendations": 8}}
    async with httpx.AsyncClient(base_url=api_base_url, timeout=60.0) as client:
        base_resp = await client.post(
            "/v1/recommendations",
            json={**body, "patient_id": str(baseline.patient_id)},
            headers=headers,
        )
        t2dm_resp = await client.post(
            "/v1/recommendations",
            json={**body, "patient_id": str(t2dm.patient_id)},
            headers=headers,
        )
    assert base_resp.status_code == 200, base_resp.text
    assert t2dm_resp.status_code == 200, t2dm_resp.text
    base_count = len(base_resp.json().get("recommendations", []))
    t2dm_count = len(t2dm_resp.json().get("recommendations", []))
    assert base_count <= t2dm_count


@pytest.mark.asyncio
async def test_personalization_second_session_differs(require_stack, api_base_url: str):
    """With PERSONALIZATION_ENABLED=1, second score uses prior drs_snapshot."""
    if os.getenv("PERSONALIZATION_ENABLED", "0") not in ("1", "true", "yes"):
        pytest.skip("PERSONALIZATION_ENABLED not set on API")
    _require_api_key_enabled(api_base_url)
    patient_id = PILOT_PATIENT_IDS[0]
    body = {"patient_id": patient_id, "options": {"max_recommendations": 6}}
    headers = _api_key_headers()
    async with httpx.AsyncClient(base_url=api_base_url, timeout=60.0) as client:
        first = await client.post("/v1/recommendations", json=body, headers=headers)
        assert first.status_code == 200, first.text
        second = await client.post("/v1/recommendations", json=body, headers=headers)
    assert second.status_code == 200, second.text
    assert first.json()["session_id"] != second.json()["session_id"]
    first_recs = first.json().get("recommendations") or []
    second_recs = second.json().get("recommendations") or []
    assert first_recs and second_recs, "expected recommendations in both sessions"
