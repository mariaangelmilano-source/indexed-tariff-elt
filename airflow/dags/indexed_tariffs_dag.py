"""Airflow DAG: price-log workbooks -> warehouse -> tested dbt models.

Runs whenever a new price log lands (here: hourly sensor-free schedule that
is cheap because extraction is idempotent). Set WAREHOUSE_TARGET=bigquery and
the GCP variables to run against BigQuery; the default is local DuckDB.

Task graph:
    extract_logs -> load_raw -> dbt_build -> publish_scorecard
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

from airflow import DAG

try:  # Airflow 3
    from airflow.providers.standard.operators.bash import BashOperator
except ImportError:  # Airflow 2.x
    from airflow.operators.bash import BashOperator

REPO = os.getenv("TARIFF_REPO_DIR", "/opt/airflow/repo")
TARGET = os.getenv("WAREHOUSE_TARGET", "duckdb")

default_args = {
    "owner": "revenue-assurance",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="indexed_tariffs",
    description="Certify indexed tariff adjustments from Excel price logs",
    start_date=datetime(2026, 1, 1),
    schedule="@hourly",
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["revenue-assurance", "dbt", "tariffs"],
) as dag:
    env = {**os.environ, "PYTHONPATH": f"{REPO}/src", "DBT_TARGET": TARGET}

    extract_logs = BashOperator(
        task_id="extract_logs",
        bash_command=f"cd {REPO} && python -m tariff_pipeline.extract "
                     "--landing data/landing --staged data/staged",
        env=env,
    )

    load_raw = BashOperator(
        task_id="load_raw",
        bash_command=f"cd {REPO} && python -m tariff_pipeline.load --target {TARGET}",
        env=env,
    )

    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command=f"cd {REPO}/dbt && dbt build --profiles-dir . --target {TARGET}",
        env=env,
    )

    publish_scorecard = BashOperator(
        task_id="publish_scorecard",
        bash_command=f"cd {REPO} && python -m tariff_pipeline.report --target {TARGET}",
        env=env,
    )

    extract_logs >> load_raw >> dbt_build >> publish_scorecard
