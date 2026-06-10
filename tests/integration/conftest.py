"""Integration test fixtures — require running Docker stack."""
from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
import pytest


def pytest_addoption(parser):
    parser.addoption("--api-base-url", default=os.getenv("API_BASE_URL", "http://localhost:8000"))
    parser.addoption("--neo4j-uri", default=os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    parser.addoption(
        "--postgres-dsn",
        default=os.getenv(
            "POSTGRES_DSN",
            "postgresql+asyncpg://supplement:devpassword@localhost:5432/supplement_db",
        ),
    )


@pytest.fixture(scope="session")
def api_base_url(request) -> str:
    return request.config.getoption("--api-base-url").rstrip("/")


@pytest.fixture(scope="session")
def postgres_dsn(request) -> str:
    return request.config.getoption("--postgres-dsn")


@pytest.fixture(scope="session")
def stack_available(api_base_url: str) -> bool:
    try:
        resp = httpx.get(f"{api_base_url}/health", timeout=5.0)
        data = resp.json()
        return resp.status_code == 200 and data.get("neo4j") and data.get("postgres")
    except Exception:
        return False


@pytest.fixture
def require_stack(stack_available: bool):
    if not stack_available:
        pytest.skip("Docker stack not available — start with: docker compose up -d")


@pytest.fixture
def t2dm_patient_payload() -> dict:
    """T2DM Riyadh patient — loaded from examples/ for parity with README."""
    example_path = Path(__file__).resolve().parents[2] / "examples" / "patient_t2dm_riyadh.json"
    if example_path.exists():
        return json.loads(example_path.read_text(encoding="utf-8"))
    return _default_t2dm_payload()


def _default_t2dm_payload() -> dict:
    return {
        "patient": {
            "demographics": {
                "age": 52,
                "sex": "F",
                "region_code": "SA-01",
                "bmi": 31.0,
                "indoor_occupation": True,
                "veiled_dress": True,
                "pregnancy_status": False,
            },
            "conditions": [
                {"code": "E11.9", "system": "ICD-10"},
                {"code": "K21.0", "system": "ICD-10"},
            ],
            "medications": [
                {"rxnorm": "6809", "name": "Metformin", "months_on": 18},
                {"rxnorm": "41493", "name": "Omeprazole", "months_on": 24},
            ],
            "labs": [
                {
                    "loinc": "1989-3",
                    "value": 18,
                    "unit": "ng/mL",
                    "reference_low": 30,
                    "reference_high": 80,
                }
            ],
            "lifestyle": {
                "diet_pattern": "omnivore",
                "sun_exposure_hrs_wk": 1.5,
                "indoor_occupation": True,
            },
        },
        "options": {"max_recommendations": 6},
    }


@pytest.fixture
def hemochromatosis_patient_payload() -> dict:
    """Forces iron into pipeline via low ferritin lab, then safety must block it."""
    return {
        "patient": {
            "demographics": {
                "age": 45,
                "sex": "M",
                "region_code": "SA-01",
                "bmi": 28.0,
            },
            "conditions": [{"code": "E83.110", "system": "ICD-10"}],
            "medications": [],
            "labs": [
                {
                    "loinc": "2498-4",
                    "value": 25,
                    "unit": "ug/dL",
                    "reference_low": 60,
                    "reference_high": 170,
                }
            ],
        },
        "options": {
            "max_recommendations": 8,
            "include_low_confidence": True,
            "nutrient_ids": ["iron"],
        },
    }


@pytest.fixture
def celiac_patient_payload() -> dict:
    return {
        "patient": {
            "demographics": {
                "age": 34,
                "sex": "F",
                "region_code": "SA-01",
                "bmi": 22.0,
            },
            "conditions": [{"code": "K90.0", "system": "ICD-10"}],
            "medications": [],
            "labs": [],
        },
        "options": {"max_recommendations": 8, "include_low_confidence": True},
    }
