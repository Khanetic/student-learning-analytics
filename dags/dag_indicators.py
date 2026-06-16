"""Airflow DAG: compute learning indicators from the core star schema.

Flow:  compute + upsert analytics.student_indicators

Reads ``core`` facts, computes the per-student indicator set and upserts it into
``analytics.student_indicators``. Idempotent via upsert; safe to re-run after
each transform.
"""

from __future__ import annotations

import pendulum
from airflow.decorators import dag, task

from sla.etl.indicators import run_indicators

DEFAULT_ARGS = {"retries": 1, "retry_delay": pendulum.duration(minutes=1)}


@dag(
    dag_id="dag_indicators",
    description="core star schema -> analytics.student_indicators",
    schedule=None,
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["sla", "indicators"],
)
def dag_indicators():
    @task
    def compute() -> int:
        """Compute and upsert indicators for the whole cohort."""
        return run_indicators()

    compute()


dag_indicators()
