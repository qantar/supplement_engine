-- Conditions append via post-load macro; view for contract tests
select
    patient_id::uuid as patient_id,
    icd10_code,
    source,
    ingest_batch_id,
    source_system
from {{ ref('seed_conditions') }}
