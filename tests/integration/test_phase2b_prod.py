"""Phase 2b-prod integration tests — enable as milestones ship."""
from __future__ import annotations

import os

import httpx
import pytest

pytestmark = pytest.mark.integration

PATIENT_ID = "f47ac10b-58cc-4372-a567-0e02b2c3d479"
DEFAULT_PROD_TEST_KEY = "pilot-dev-key-change-me"


def _prod_api_key() -> str:
    return os.getenv("PHASE2B_TEST_API_KEY", DEFAULT_PROD_TEST_KEY)


def _api_key_headers() -> dict[str, str]:
    return {"X-API-Key": _prod_api_key()}


def _require_api_key_enabled(api_base_url: str) -> None:
    """Skip prod auth tests when stack runs dev profile."""
    try:
        resp = httpx.post(
            f"{api_base_url}/v1/recommendations",
            json={"patient_id": PATIENT_ID, "options": {"max_recommendations": 1}},
            timeout=10.0,
        )
    except httpx.HTTPError:
        pytest.skip("API unreachable")
    if resp.status_code != 401:
        pytest.skip("REQUIRE_API_KEY not enabled — use docker-compose.prod.yml (M1)")


@pytest.mark.asyncio
async def test_health_live(require_stack, api_base_url: str):
    """M2: /health/live returns 200 when API process is up."""
    async with httpx.AsyncClient(base_url=api_base_url, timeout=15.0) as client:
        resp = await client.get("/health/live")
    assert resp.status_code == 200
    assert resp.json().get("status") == "alive"


@pytest.mark.asyncio
async def test_readiness_endpoint(require_stack, api_base_url: str):
    """M2: /health/ready returns 200 when dependencies are up."""
    async with httpx.AsyncClient(base_url=api_base_url, timeout=15.0) as client:
        resp = await client.get("/health/ready")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "ready"
    assert data.get("postgres") is True
    assert data.get("neo4j") is True


@pytest.mark.asyncio
async def test_evidence_snapshot_has_real_kg_version(
    require_stack, api_base_url: str,
):
    """M2: evidence snapshot kg_commit_sha is not a placeholder."""
    _require_api_key_enabled(api_base_url)
    headers = _api_key_headers()
    body = {"patient_id": PATIENT_ID, "options": {"max_recommendations": 3}}
    async with httpx.AsyncClient(base_url=api_base_url, timeout=60.0) as client:
        resp = await client.post("/v1/recommendations", json=body, headers=headers)
    assert resp.status_code == 200, resp.text
    snapshot_id = resp.json()["evidence_snapshot_id"]
    async with httpx.AsyncClient(base_url=api_base_url, timeout=15.0) as client:
        ev = await client.get(f"/v1/evidence/{snapshot_id}", headers=headers)
    assert ev.status_code == 200
    body = ev.json()
    sha = body.get("kg_commit_sha") or ""
    assert sha not in ("", "unknown", "placeholder"), f"kg_commit_sha still placeholder: {sha!r}"
    contents = body.get("contents") or {}
    content_hash = contents.get("content_hash") or ""
    assert len(content_hash) == 64, f"expected SHA-256 hex content_hash, got {content_hash!r}"
    assert contents.get("kg_version") == sha


@pytest.mark.asyncio
async def test_prod_inline_patient_rejected(require_stack, api_base_url: str):
    """M1: inline patient JSON returns 400 when ALLOW_INLINE_PATIENT=0."""
    _require_api_key_enabled(api_base_url)
    payload = {
        "patient": {
            "demographics": {"age": 52, "sex": "F", "region_code": "SA-01", "bmi": 31.0},
            "conditions": [],
            "medications": [],
            "labs": [],
        },
    }
    async with httpx.AsyncClient(base_url=api_base_url, timeout=30.0) as client:
        resp = await client.post(
            "/v1/recommendations",
            json=payload,
            headers=_api_key_headers(),
        )
    assert resp.status_code == 400
    assert "inline" in resp.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_prod_missing_api_key_returns_401(require_stack, api_base_url: str):
    """M1: /v1/* without X-API-Key returns 401 when REQUIRE_API_KEY=1."""
    _require_api_key_enabled(api_base_url)
    async with httpx.AsyncClient(base_url=api_base_url, timeout=15.0) as client:
        resp = await client.post(
            "/v1/recommendations",
            json={"patient_id": PATIENT_ID, "options": {"max_recommendations": 1}},
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_prod_patient_id_score_with_api_key(require_stack, api_base_url: str):
    """M1: authenticated patient_id scoring works."""
    _require_api_key_enabled(api_base_url)
    async with httpx.AsyncClient(base_url=api_base_url, timeout=60.0) as client:
        resp = await client.post(
            "/v1/recommendations",
            json={"patient_id": PATIENT_ID, "options": {"max_recommendations": 6}},
            headers=_api_key_headers(),
        )
    assert resp.status_code == 200, resp.text
    assert resp.json().get("recommendations")
