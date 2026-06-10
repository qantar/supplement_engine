"""Bulk patient sync: dbt run into Postgres patient realm."""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    "owner": "supplement_engine",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

ETL_DIR = "/opt/supplement_engine/etl"

with DAG(
    dag_id="dag_patient_bulk_sync",
    default_args=default_args,
    description="dbt bulk load into Postgres patient realm",
    schedule_interval="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["phase2a", "patient_realm"],
) as dag:
    dbt_seed = BashOperator(
        task_id="dbt_seed",
        bash_command=f"cd {ETL_DIR} && dbt seed",
    )
    dbt_patients = BashOperator(
        task_id="dbt_run_patients",
        bash_command=f"cd {ETL_DIR} && dbt run --select patient_realm.patients",
    )
    dbt_children = BashOperator(
        task_id="dbt_load_children",
        bash_command=f"cd {ETL_DIR} && dbt run-operation load_patient_children",
    )

    dbt_seed >> dbt_patients >> dbt_children
