{{ config(
    materialized='incremental',
    unique_key='patient_id',
    schema='public',
    alias='patients',
    incremental_strategy='merge',
    on_schema_change='append_new_columns'
) }}

select
    patient_id,
    hashed_mrn,
    dob_year,
    sex,
    region_code,
    pregnancy_status,
    lactation_status,
    bmi,
    indoor_occupation,
    veiled_dress,
    now() as updated_at
from {{ ref('stg_patients') }}
