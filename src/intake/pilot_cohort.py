"""Pilot seed cohort — stable IDs and fixture loading."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from src.intake.identity import MOCK_SOURCE_SYSTEM, compute_hashed_mrn
from src.shared.models import (
    Condition, ConditionSource, Demographics, LabResult, Lifestyle,
    Medication, PatientPreferences, PatientProfile, Sex,
)

ROOT = Path(__file__).resolve().parents[2]
PILOT_DIR = ROOT / "examples" / "pilot"


@dataclass(frozen=True)
class PilotPatientMeta:
    patient_id: uuid.UUID
    source_key: str
    fixture: str
    clinical_intent: str


PILOT_COHORT: tuple[PilotPatientMeta, ...] = (
    PilotPatientMeta(
        uuid.UUID("f47ac10b-58cc-4372-a567-0e02b2c3d479"),
        "MRN-T2DM-001",
        "patient_t2dm_riyadh.json",
        "T2DM + veiled/indoor + low vitamin D",
    ),
    PilotPatientMeta(
        uuid.UUID("a10bc10b-58cc-4372-a567-0e02b2c3d480"),
        "MRN-CKD-002",
        "ckd_stage3.json",
        "CKD stage 3 + T2DM + ACE inhibitor",
    ),
    PilotPatientMeta(
        uuid.UUID("b20bc10b-58cc-4372-a567-0e02b2c3d481"),
        "MRN-HEMO-003",
        "hemochromatosis.json",
        "Hemochromatosis — iron must be blocked",
    ),
    PilotPatientMeta(
        uuid.UUID("c30bc10b-58cc-4372-a567-0e02b2c3d482"),
        "MRN-PREG-004",
        "pregnancy.json",
        "Pregnancy — folate/iron guideline doses",
    ),
    PilotPatientMeta(
        uuid.UUID("d40bc10b-58cc-4372-a567-0e02b2c3d483"),
        "MRN-CEL-005",
        "celiac.json",
        "Celiac — malabsorption risk nutrients",
    ),
    PilotPatientMeta(
        uuid.UUID("e50bc10b-58cc-4372-a567-0e02b2c3d484"),
        "MRN-VEG-006",
        "vegan_b12.json",
        "Vegan + low B12 lab",
    ),
    PilotPatientMeta(
        uuid.UUID("f60bc10b-58cc-4372-a567-0e02b2c3d485"),
        "MRN-PPI-007",
        "elderly_ppi.json",
        "Elderly + long-term PPI depletion",
    ),
    PilotPatientMeta(
        uuid.UUID("a70bc10b-58cc-4372-a567-0e02b2c3d486"),
        "MRN-BASE-008",
        "healthy_baseline.json",
        "Low-risk baseline — replete labs, high sun (threshold test)",
    ),
    PilotPatientMeta(
        uuid.UUID("a80bc10b-58cc-4372-a567-0e02b2c3d487"),
        "MRN-CKD4-009",
        "ckd_stage4_warfarin.json",
        "CKD stage 4 + AF + warfarin — K/Mg blocks, escalation",
    ),
    PilotPatientMeta(
        uuid.UUID("a90bc10b-58cc-4372-a567-0e02b2c3d488"),
        "MRN-OBE-010",
        "obesity_t2dm_statin.json",
        "Morbid obesity + T2DM + statin — fat-soluble/BMI adj",
    ),
    PilotPatientMeta(
        uuid.UUID("aa0bc10b-58cc-4372-a567-0e02b2c3d489"),
        "MRN-DEP-011",
        "depression_ssri.json",
        "Major depression on SSRI — omega-3 demand path",
    ),
    PilotPatientMeta(
        uuid.UUID("ab0bc10b-58cc-4372-a567-0e02b2c3d48a"),
        "MRN-IBD-012",
        "ibd_crohn.json",
        "Crohn's + methotrexate — iron/D/B12 multi-depletion",
    ),
    PilotPatientMeta(
        uuid.UUID("ac0bc10b-58cc-4372-a567-0e02b2c3d48b"),
        "MRN-BAR-013",
        "post_bariatric.json",
        "Post-bariatric (Z98.84) — ADEK/B12/thiamine malabsorption",
    ),
    PilotPatientMeta(
        uuid.UUID("ad0bc10b-58cc-4372-a567-0e02b2c3d48c"),
        "MRN-OST-014",
        "osteoporosis_postmenopausal.json",
        "Postmenopausal osteoporosis + alendronate — Ca/D guideline",
    ),
    PilotPatientMeta(
        uuid.UUID("ae0bc10b-58cc-4372-a567-0e02b2c3d48d"),
        "MRN-LAC-015",
        "hypothyroid_lactating.json",
        "Hypothyroid + lactating — selenium/iodine sensitivity",
    ),
    PilotPatientMeta(
        uuid.UUID("af0bc10b-58cc-4372-a567-0e02b2c3d48e"),
        "MRN-POLY-016",
        "polypharmacy_bvit_depletion.json",
        "Metformin + PPI + smoking/alcohol — B-vitamin stack",
    ),
)

PILOT_PATIENT_IDS: tuple[str, ...] = tuple(str(m.patient_id) for m in PILOT_COHORT)


def cohort_by_source_key(source_key: str) -> PilotPatientMeta | None:
    for meta in PILOT_COHORT:
        if meta.source_key == source_key:
            return meta
    return None


def fixture_path(meta: PilotPatientMeta) -> Path:
    if meta.fixture == "patient_t2dm_riyadh.json":
        return ROOT / "examples" / meta.fixture
    return PILOT_DIR / meta.fixture


def load_fixture(meta: PilotPatientMeta) -> dict:
    return json.loads(fixture_path(meta).read_text(encoding="utf-8"))


def fixture_to_profile(meta: PilotPatientMeta, data: dict | None = None) -> PatientProfile:
    payload = data if data is not None else load_fixture(meta)
    p = payload["patient"]
    d = p["demographics"]
    lifestyle = p.get("lifestyle", {})
    prefs = p.get("preferences", {})
    return PatientProfile(
        patient_id=meta.patient_id,
        demographics=Demographics(
            age=d["age"],
            sex=Sex(d["sex"]),
            region_code=d["region_code"],
            bmi=d.get("bmi"),
            pregnancy_status=d.get("pregnancy_status", False),
            lactation_status=d.get("lactation_status", False),
            indoor_occupation=d.get("indoor_occupation", False),
            veiled_dress=d.get("veiled_dress", False),
        ),
        conditions=tuple(
            Condition(
                icd10_code=c["code"],
                source=ConditionSource(c.get("source", "ehr")),
            )
            for c in p.get("conditions", [])
        ),
        medications=tuple(
            Medication(
                rxnorm_cui=m["rxnorm"],
                name=m["name"],
                dose_mg=m.get("dose_mg"),
                months_on=m.get("months_on", 0),
            )
            for m in p.get("medications", [])
        ),
        labs=tuple(
            LabResult(
                loinc=l["loinc"],
                value_num=l["value"],
                unit=l["unit"],
                collected_at=datetime.now(timezone.utc),
                reference_low=l.get("reference_low"),
                reference_high=l.get("reference_high"),
            )
            for l in p.get("labs", [])
        ),
        lifestyle=Lifestyle(
            diet_pattern=lifestyle.get("diet_pattern", "omnivore"),
            sun_exposure_hrs_wk=lifestyle.get("sun_exposure_hrs_wk", 1.5),
            alcohol_units_wk=lifestyle.get("alcohol_units_wk", 0),
            smoking=lifestyle.get("smoking", False),
            activity_level=lifestyle.get("activity_level", "moderate"),
        ),
        preferences=PatientPreferences(
            halal=prefs.get("halal", True),
            vegan=prefs.get("vegan", False),
            budget_tier=prefs.get("budget_tier", "standard"),
        ),
    )


def hashed_mrn(meta: PilotPatientMeta) -> str:
    return compute_hashed_mrn(MOCK_SOURCE_SYSTEM, meta.source_key)
