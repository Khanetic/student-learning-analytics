"""Airflow DAG: ingest raw simulated files into staging tables.

Flow:  ensure schema  ->  validate + stage each raw table (in parallel)

Idempotent: schema DDL uses ``IF NOT EXISTS`` and staging tables are
truncate-reloaded, so re-running is always safe.
"""

from __future__ import annotations

import pendulum
from airflow.decorators import dag, task

from sla.config import PROJECT_ROOT
from sla.db import run_sql_file
from sla.etl.ingest import ingest_table
from sla.etl.spec import TABLE_SPECS

DEFAULT_ARGS = {"retries": 1, "retry_delay": pendulum.duration(minutes=1)}


@dag(
    dag_id="dag_ingest",
    description="Raw CSV/JSON -> validate -> staging tables",
    schedule=None,
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["sla", "ingest"],
)
def dag_ingest():
    @task
    def ensure_schema() -> None:
        """Create schemas, star-schema tables and indexes (idempotent)."""
        run_sql_file(PROJECT_ROOT / "sql" / "01_schema.sql")
        run_sql_file(PROJECT_ROOT / "sql" / "02_indexes.sql")

    @task
    def ingest(table_name: str) -> int:
        """Validate one raw table and load it into staging."""
        return ingest_table(table_name)

    schema_ready = ensure_schema()
    for spec in TABLE_SPECS:
        schema_ready >> ingest.override(task_id=f"ingest_{spec.name}")(spec.name)


dag_ingest()
