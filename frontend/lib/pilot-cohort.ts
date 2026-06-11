/** Pilot cohort — IDs mirror src/intake/pilot_cohort.py (seed via scripts/seed_patient_realm.py). */

export interface PilotPatient {
  patient_id: string;
  source_key: string;
  label: string;
  clinical_intent: string;
  /** What this case is designed to exercise in the engine. */
  test_focus: string;
}

export const PILOT_COHORT: PilotPatient[] = [
  {
    patient_id: "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    source_key: "MRN-T2DM-001",
    label: "T2DM · Riyadh",
    clinical_intent: "T2DM + veiled/indoor + low vitamin D",
    test_focus: "KSA geo modifier, metformin/PPI depletion, lab override",
  },
  {
    patient_id: "a10bc10b-58cc-4372-a567-0e02b2c3d480",
    source_key: "MRN-CKD-002",
    label: "CKD stage 3",
    clinical_intent: "CKD stage 3 + T2DM + ACE inhibitor",
    test_focus: "Renal impairment, electrolyte caution",
  },
  {
    patient_id: "b20bc10b-58cc-4372-a567-0e02b2c3d481",
    source_key: "MRN-HEMO-003",
    label: "Hemochromatosis",
    clinical_intent: "Hemochromatosis — iron must be blocked",
    test_focus: "Absolute iron contraindication",
  },
  {
    patient_id: "c30bc10b-58cc-4372-a567-0e02b2c3d482",
    source_key: "MRN-PREG-004",
    label: "Pregnancy",
    clinical_intent: "Pregnancy — folate/iron guideline doses",
    test_focus: "Pregnancy overrides, retinol block",
  },
  {
    patient_id: "d40bc10b-58cc-4372-a567-0e02b2c3d483",
    source_key: "MRN-CEL-005",
    label: "Celiac",
    clinical_intent: "Celiac — malabsorption risk nutrients",
    test_focus: "Malabsorption edges, low ferritin",
  },
  {
    patient_id: "e50bc10b-58cc-4372-a567-0e02b2c3d484",
    source_key: "MRN-VEG-006",
    label: "Vegan + low B12",
    clinical_intent: "Vegan + low B12 lab",
    test_focus: "Diet pattern + measured B12 deficiency",
  },
  {
    patient_id: "f60bc10b-58cc-4372-a567-0e02b2c3d485",
    source_key: "MRN-PPI-007",
    label: "Elderly + PPI",
    clinical_intent: "Elderly + long-term PPI depletion",
    test_focus: "Age + chronic PPI B12/magnesium depletion",
  },
  {
    patient_id: "a70bc10b-58cc-4372-a567-0e02b2c3d486",
    source_key: "MRN-BASE-008",
    label: "Healthy baseline",
    clinical_intent: "Low-risk baseline — replete labs, high sun",
    test_focus: "Threshold / few recommendations expected",
  },
  {
    patient_id: "a80bc10b-58cc-4372-a567-0e02b2c3d487",
    source_key: "MRN-CKD4-009",
    label: "CKD 4 + warfarin",
    clinical_intent: "CKD stage 4 + AF + warfarin",
    test_focus: "K/Mg blocks, clinician escalation",
  },
  {
    patient_id: "a90bc10b-58cc-4372-a567-0e02b2c3d488",
    source_key: "MRN-OBE-010",
    label: "Morbid obesity",
    clinical_intent: "BMI 38 + T2DM + statin",
    test_focus: "BMI fat-soluble adjustment, multi-morbidity",
  },
  {
    patient_id: "aa0bc10b-58cc-4372-a567-0e02b2c3d489",
    source_key: "MRN-DEP-011",
    label: "Depression + SSRI",
    clinical_intent: "Major depression on sertraline",
    test_focus: "Omega-3 demand, SSRI interaction awareness",
  },
  {
    patient_id: "ab0bc10b-58cc-4372-a567-0e02b2c3d48a",
    source_key: "MRN-IBD-012",
    label: "Crohn's + MTX",
    clinical_intent: "Crohn's on methotrexate",
    test_focus: "IBD iron/D/B12 stack, folate depletion drug",
  },
  {
    patient_id: "ac0bc10b-58cc-4372-a567-0e02b2c3d48b",
    source_key: "MRN-BAR-013",
    label: "Post-bariatric",
    clinical_intent: "Post-bariatric malabsorption",
    test_focus: "Z98.84 high LR nutrients (D, B12, thiamine, copper)",
  },
  {
    patient_id: "ad0bc10b-58cc-4372-a567-0e02b2c3d48c",
    source_key: "MRN-OST-014",
    label: "Osteoporosis",
    clinical_intent: "Postmenopausal osteoporosis + alendronate",
    test_focus: "Ca/D guideline path, low 25-OH-D",
  },
  {
    patient_id: "ae0bc10b-58cc-4372-a567-0e02b2c3d48d",
    source_key: "MRN-LAC-015",
    label: "Hypothyroid + lactating",
    clinical_intent: "Hypothyroid while breastfeeding",
    test_focus: "Selenium/iodine, lactation demand",
  },
  {
    patient_id: "af0bc10b-58cc-4372-a567-0e02b2c3d48e",
    source_key: "MRN-POLY-016",
    label: "Polypharmacy B-vit",
    clinical_intent: "Metformin + PPI + smoking/alcohol",
    test_focus: "B-complex collapse (≥3 B-vitamin candidates)",
  },
];
