{% macro load_patient_children() %}
  insert into patient_conditions (patient_id, icd10_code, source, ingest_batch_id, source_system, ingested_at)
  select patient_id, icd10_code, source, ingest_batch_id, source_system, now()
  from {{ ref('stg_conditions') }}
  on conflict do nothing;

  insert into patient_medications (patient_id, rxnorm_cui, name, months_on, dose_mg, ingest_batch_id, source_system, ingested_at, start_date)
  select patient_id::uuid, rxnorm_cui, name, months_on::int, nullif(dose_mg, '')::numeric, ingest_batch_id, source_system, now(), now()
  from {{ ref('seed_medications') }}
  on conflict do nothing;

  insert into patient_labs (patient_id, loinc, value_num, unit, reference_low, reference_high, collected_at, ingest_batch_id, source_system, ingested_at)
  select patient_id::uuid, loinc, value_num::numeric, unit, reference_low::numeric, reference_high::numeric, collected_at::timestamptz, ingest_batch_id, source_system, now()
  from {{ ref('seed_labs') }}
  on conflict do nothing;

  insert into ingest_batches (batch_id, source_system, row_counts, dbt_run_id)
  values ('dbt-seed-001', 'mock_warehouse', '{"source":"dbt"}'::jsonb, '{{ invocation_id }}')
  on conflict do nothing;
{% endmacro %}
