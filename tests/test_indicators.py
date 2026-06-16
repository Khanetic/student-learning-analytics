"""Phase 3 unit tests for the learning-indicator functions.

Each indicator is tested in isolation, including the edge cases the DAG must
survive: no data, a single attempt, ties/flat trends, and boundary thresholds.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from sla.indicators import (
    INDICATOR_COLUMNS,
    at_risk_flag,
    compute_all,
    engagement_score,
    quiz_trend,
    session_regularity,
    submission_rate,
    time_on_task_hours,
)
from sla.indicators.compute import AT_RISK_ENGAGEMENT_MAX

# --- engagement_score ------------------------------------------------------


def test_engagement_zero_activity_is_zero() -> None:
    assert engagement_score(0, 0, 0, weeks=12) == 0.0


def test_engagement_caps_at_100() -> None:
    # Far above every cap over a 1-week window -> all components saturate.
    assert engagement_score(100, 1000, 100, weeks=1) == 100.0


def test_engagement_is_weighted_composite() -> None:
    # Exactly at the session cap (5/wk), nothing else: 0.5 weight * 100 = 50.
    assert engagement_score(5, 0, 0, weeks=1) == 50.0
    # Exactly at the page-view cap (20/wk): 0.3 weight * 100 = 30.
    assert engagement_score(0, 20, 0, weeks=1) == 30.0


def test_engagement_handles_zero_weeks_safely() -> None:
    # Must not divide by zero.
    assert engagement_score(1, 1, 1, weeks=0) == 100.0


# --- time_on_task_hours ----------------------------------------------------


def test_time_on_task_basic() -> None:
    # 120 + 120 minutes = 4 hours over 2 weeks -> 2.0 h/week.
    assert time_on_task_hours([120.0, 120.0], weeks=2) == 2.0


def test_time_on_task_empty() -> None:
    assert time_on_task_hours([], weeks=12) == 0.0


# --- quiz_trend ------------------------------------------------------------


def test_quiz_trend_positive() -> None:
    label, slope = quiz_trend([50, 55, 60, 65, 70])
    assert label == "positive" and slope > 0


def test_quiz_trend_negative() -> None:
    label, slope = quiz_trend([90, 80, 70, 60, 50])
    assert label == "negative" and slope < 0


def test_quiz_trend_flat() -> None:
    label, slope = quiz_trend([70, 70, 70, 70])
    assert label == "flat" and slope == 0.0


def test_quiz_trend_uses_last_five_only() -> None:
    # Early decline then a recent climb: only the last 5 (rising) count.
    label, _ = quiz_trend([100, 90, 80, 10, 20, 30, 40, 50])
    assert label == "positive"


def test_quiz_trend_single_attempt_is_flat() -> None:
    assert quiz_trend([42]) == ("flat", 0.0)


def test_quiz_trend_empty_is_flat() -> None:
    assert quiz_trend([]) == ("flat", 0.0)


def test_quiz_trend_ignores_nan() -> None:
    label, _ = quiz_trend([50, np.nan, 60, 70, 80])
    assert label == "positive"


# --- session_regularity ----------------------------------------------------


def test_session_regularity_perfectly_regular() -> None:
    base = datetime(2026, 1, 1)
    logins = [base + timedelta(days=i) for i in range(5)]  # gap = 1 day always
    assert session_regularity(logins) == 0.0


def test_session_regularity_irregular_is_positive() -> None:
    base = datetime(2026, 1, 1)
    logins = [base, base + timedelta(days=1), base + timedelta(days=10)]
    assert session_regularity(logins) > 0


def test_session_regularity_too_few_logins() -> None:
    assert session_regularity([]) == 0.0
    assert session_regularity([datetime(2026, 1, 1)]) == 0.0


def test_session_regularity_dedupes_same_day() -> None:
    base = datetime(2026, 1, 1)
    same_day = [base, base + timedelta(hours=2), base + timedelta(hours=5)]
    assert session_regularity(same_day) == 0.0


# --- submission_rate -------------------------------------------------------


def test_submission_rate_all_on_time() -> None:
    assert submission_rate([True, True, True]) == 100.0


def test_submission_rate_mixed() -> None:
    assert submission_rate([True, False, True, False]) == 50.0


def test_submission_rate_no_assignments() -> None:
    assert submission_rate([]) == 0.0


# --- at_risk_flag ----------------------------------------------------------


def test_at_risk_true_when_low_engagement_and_negative_trend() -> None:
    assert at_risk_flag(30.0, "negative") is True


def test_at_risk_false_when_engagement_ok() -> None:
    assert at_risk_flag(50.0, "negative") is False


def test_at_risk_false_when_trend_not_negative() -> None:
    assert at_risk_flag(20.0, "flat") is False
    assert at_risk_flag(20.0, "positive") is False


def test_at_risk_threshold_is_exclusive() -> None:
    # Exactly at the threshold is NOT at risk (strict less-than).
    assert at_risk_flag(AT_RISK_ENGAGEMENT_MAX, "negative") is False


# --- compute_all -----------------------------------------------------------


def _empty(cols: list[str]) -> pd.DataFrame:
    return pd.DataFrame({c: [] for c in cols})


def test_compute_all_covers_every_student_even_without_activity() -> None:
    students = pd.DataFrame({"student_id": ["S1", "S2"]})
    sessions = _empty(["student_id", "duration_minutes", "login_at"])
    page_views = _empty(["student_id"])
    quizzes = _empty(["student_id", "score", "submitted_at"])
    subs = _empty(["student_id", "on_time"])

    out = compute_all(students, sessions, page_views, quizzes, subs, weeks=12)

    assert list(out.columns) == INDICATOR_COLUMNS
    assert set(out["student_id"]) == {"S1", "S2"}
    assert (out["engagement_score"] == 0.0).all()
    assert (out["quiz_trend"] == "flat").all()
    assert not out["at_risk_flag"].any()  # flat trend -> never at risk


def test_compute_all_marks_disengaged_declining_student_at_risk() -> None:
    students = pd.DataFrame({"student_id": ["LOW", "HIGH"]})
    base = datetime(2026, 1, 1)
    sessions = pd.DataFrame(
        {
            "student_id": ["HIGH"] * 30,
            "duration_minutes": [90.0] * 30,
            "login_at": [base + timedelta(days=i) for i in range(30)],
        }
    )
    page_views = pd.DataFrame({"student_id": ["HIGH"] * 200})
    quizzes = pd.DataFrame(
        {
            "student_id": ["LOW"] * 5 + ["HIGH"] * 5,
            "score": [90, 80, 70, 60, 50] + [50, 60, 70, 80, 90],
            "submitted_at": [base + timedelta(days=i) for i in range(5)] * 2,
        }
    )
    subs = pd.DataFrame({"student_id": ["LOW", "HIGH"], "on_time": [False, True]})

    out = compute_all(students, sessions, page_views, quizzes, subs, weeks=12)
    by_id = out.set_index("student_id")

    # LOW: no sessions/page views -> low engagement, declining quizzes -> at risk.
    assert by_id.loc["LOW", "at_risk_flag"]
    assert by_id.loc["LOW", "quiz_trend"] == "negative"
    # HIGH: lots of activity, improving quizzes -> not at risk.
    assert not by_id.loc["HIGH", "at_risk_flag"]
    assert by_id.loc["HIGH", "quiz_trend"] == "positive"
    assert by_id.loc["HIGH", "engagement_score"] > by_id.loc["LOW", "engagement_score"]
