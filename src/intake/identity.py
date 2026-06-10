"""Stable IDs for mock warehouse / dbt seed patients."""
from __future__ import annotations

import hashlib
import uuid

# T2DM Riyadh fixture — matches examples/patient_t2dm_riyadh.json intent
T2DM_RIYADH_PATIENT_ID = uuid.UUID("f47ac10b-58cc-4372-a567-0e02b2c3d479")
T2DM_RIYADH_SOURCE_KEY = "MRN-T2DM-001"
MOCK_SOURCE_SYSTEM = "mock_warehouse"


def compute_hashed_mrn(source_system: str, source_patient_key: str) -> str:
    payload = f"{source_system}:{source_patient_key}"
    return hashlib.sha256(payload.encode()).hexdigest()
