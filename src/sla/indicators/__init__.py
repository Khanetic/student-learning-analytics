"""Learning indicator computation (Phase 3).

Pure functions — one per indicator — plus a cohort-level aggregator. Each
function takes plain inputs (counts / sequences) so it is trivially unit-tested
in isolation, independent of the database or Airflow.
"""

from sla.indicators.compute import (
    INDICATOR_COLUMNS,
    at_risk_flag,
    compute_all,
    compute_student,
    engagement_score,
    quiz_trend,
    session_regularity,
    submission_rate,
    time_on_task_hours,
)

__all__ = [
    "INDICATOR_COLUMNS",
    "at_risk_flag",
    "compute_all",
    "compute_student",
    "engagement_score",
    "quiz_trend",
    "session_regularity",
    "submission_rate",
    "time_on_task_hours",
]
