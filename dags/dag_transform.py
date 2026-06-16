"""Airflow DAG: transform staging tables into the core star schema.

Flow:  load dimensions (parallel)  ->  load facts (parallel)

Dimensions load first so the fact-table foreign-key checks validate against
populated core dimensions. Upserts keep the DAG idempotent.
"""

from __future__ import annotations

import pendulum
from airflow.decorators import dag, task

from sla.etl.spec import DIMENSION_NAMES, FACT_NAMES
from sla.etl.transform import transform_table

DEFAULT_ARGS = {"retries": 1, "retry_delay": pendulum.duration(minutes=1)}


@dag(
    dag_id="dag_transform",
    description="staging -> core star schema with data-quality gate",
    schedule=None,
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["sla", "transform"],
)
def dag_transform():
    @task
    def transform(table_name: str) -> int:
        """Validate (incl. foreign keys) and upsert one table into core."""
        return transform_table(table_name)

    dims = [transform.override(task_id=f"load_{n}")(n) for n in DIMENSION_NAMES]
    facts = [transform.override(task_id=f"load_{n}")(n) for n in FACT_NAMES]

    # Every fact depends on all dimensions being loaded first.
    for f in facts:
        dims >> f  # type: ignore[operator]


dag_transform()
