"""Indicator stage: core star schema -> analytics.student_indicators.

Reads the core facts, computes the per-student indicator set with
:func:`sla.indicators.compute_all`, and upserts the result. Upsert keeps the
DAG idempotent.
"""

from __future__ import annotations

import logging

from sla.config import get_settings
from sla.db import ANALYTICS_SCHEMA, CORE_SCHEMA, fetch_df, upsert
from sla.indicators import INDICATOR_COLUMNS, compute_all

log = logging.getLogger(__name__)

INDICATORS_TABLE = "student_indicators"


def _core(table: str):
    """Load a core table into a DataFrame."""
    return fetch_df(f'SELECT * FROM {CORE_SCHEMA}."{table}"')


def run_indicators(weeks: float | None = None) -> int:
    """Compute indicators for the whole cohort and upsert them.

    Returns the number of student rows written.
    """
    weeks = weeks if weeks is not None else float(get_settings().sim_weeks)

    students = _core("dim_students")
    indicators = compute_all(
        students=students,
        sessions=_core("fact_sessions"),
        page_views=_core("fact_page_views"),
        quiz_attempts=_core("fact_quiz_attempts"),
        submissions=_core("fact_assignment_submissions"),
        weeks=weeks,
    )

    rows = upsert(
        indicators[INDICATOR_COLUMNS],
        ANALYTICS_SCHEMA,
        INDICATORS_TABLE,
        conflict_cols=["student_id"],
    )
    at_risk = int(indicators["at_risk_flag"].sum())
    log.info("Computed indicators for %s students (%s at risk)", rows, at_risk)
    return rows
