-- Staging: mock warehouse patients
select
    patient_id::uuid as patient_id,
    hashed_mrn,
    sex,
    region_code,
    dob_year::int as dob_year,
    bmi::numeric as bmi,
    indoor_occupation::boolean as indoor_occupation,
    veiled_dress::boolean as veiled_dress,
    pregnancy_status::boolean as pregnancy_status,
    lactation_status::boolean as lactation_status,
    ingest_batch_id,
    source_system
from {{ ref('seed_patients') }}
