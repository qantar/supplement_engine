# Pilot patient fixtures — diverse clinical test matrix

16 seeded patients for Postgres patient realm (`scripts/seed_patient_realm.py`).
Each maps to a stable UUID in `src/intake/pilot_cohort.py` and appears in the
clinician console pilot picker.

| MRN | Fixture | Primary test focus |
|-----|---------|-------------------|
| MRN-T2DM-001 | `patient_t2dm_riyadh.json` (root examples/) | Appendix A — KSA indoor, T2DM, PPI, low Vit D |
| MRN-CKD-002 | `ckd_stage3.json` | CKD3 + T2DM + ACEi |
| MRN-HEMO-003 | `hemochromatosis.json` | Iron must be **blocked** |
| MRN-PREG-004 | `pregnancy.json` | Pregnancy folate/iron; retinol CI |
| MRN-CEL-005 | `celiac.json` | Celiac malabsorption |
| MRN-VEG-006 | `vegan_b12.json` | Vegan diet + low B12 lab |
| MRN-PPI-007 | `elderly_ppi.json` | Elderly + long PPI |
| MRN-BASE-008 | `healthy_baseline.json` | Replete labs — **few recs expected** |
| MRN-CKD4-009 | `ckd_stage4_warfarin.json` | CKD4 K/Mg blocks + warfarin + escalation |
| MRN-OBE-010 | `obesity_t2dm_statin.json` | BMI ≥38 fat-soluble adj + statin |
| MRN-DEP-011 | `depression_ssri.json` | Depression → omega-3 path |
| MRN-IBD-012 | `ibd_crohn.json` | Crohn + methotrexate multi-depletion |
| MRN-BAR-013 | `post_bariatric.json` | Post-bariatric ADEK/B12/thiamine |
| MRN-OST-014 | `osteoporosis_postmenopausal.json` | Osteoporosis Ca/D guideline |
| MRN-LAC-015 | `hypothyroid_lactating.json` | Hypothyroid + lactation |
| MRN-POLY-016 | `polypharmacy_bvit_depletion.json` | B-complex collapse trigger |

## Reseed after adding fixtures

```powershell
docker compose exec api python scripts/seed_patient_realm.py
```

Or: `python scripts/run_app.py` (seeds automatically on first run).

## Score all patients (prod profile)

```powershell
$headers = @{ "X-API-Key" = "pilot-dev-key-change-me"; "Content-Type" = "application/json" }
python -c "from src.intake.pilot_cohort import PILOT_PATIENT_IDS; print(len(PILOT_PATIENT_IDS), 'patients')"
```
