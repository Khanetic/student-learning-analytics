"""Per-student learning indicators.

Each indicator is a small, pure function. :func:`compute_student` assembles the
inputs for one student into the full indicator set, and :func:`compute_all`
runs the cohort and returns a tidy DataFrame ready to upsert into
``analytics.student_indicators``.

Indicators
----------
* ``engagement_score``   — 0–100 weighted composite of weekly activity rates
* ``time_on_task_hours`` — active learning hours per week
* ``quiz_trend``         — slope over the last 5 quiz scores -> label + value
* ``session_regularity`` — std-dev of days between logins (lower = more regular)
* ``submission_rate``    — % of assignments submitted on time
* ``at_risk_flag``       — engagement < 40 AND quiz trend negative
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np
import pandas as pd

# --- tunable parameters (documented constants, no magic numbers inline) -----

#: Weights for the engagement composite (must sum to 1.0).
ENGAGEMENT_WEIGHTS = {"sessions": 0.5, "page_views": 0.3, "quiz_attempts": 0.2}

#: Per-week activity levels that map to a full score of 100 for each component.
ENGAGEMENT_CAPS_PER_WEEK = {"sessions": 5.0, "page_views": 20.0, "quiz_attempts": 8.0}

#: |slope| below this (points/attempt) is considered "flat".
QUIZ_TREND_FLAT_EPS = 0.5

#: Number of most-recent quiz scores used for the trend.
QUIZ_TREND_WINDOW = 5

#: at-risk thresholds.
AT_RISK_ENGAGEMENT_MAX = 40.0

#: Column order written to analytics.student_indicators.
INDICATOR_COLUMNS = [
    "student_id",
    "engagement_score",
    "time_on_task_hours",
    "quiz_trend",
    "quiz_trend_slope",
    "session_regularity",
    "submission_rate",
    "at_risk_flag",
    "computed_at",
]


# --- individual indicators -------------------------------------------------


def engagement_score(
    n_sessions: int,
    n_page_views: int,
    n_quiz_attempts: int,
    weeks: float,
) -> float:
    """Weighted composite of weekly activity, scaled to 0–100.

    Each component is the student's per-week rate divided by a reference cap
    (clamped to 1.0), combined with :data:`ENGAGEMENT_WEIGHTS`.
    """
    weeks = max(weeks, 1e-9)
    rates = {
        "sessions": n_sessions / weeks,
        "page_views": n_page_views / weeks,
        "quiz_attempts": n_quiz_attempts / weeks,
    }
    score = 0.0
    for key, weight in ENGAGEMENT_WEIGHTS.items():
        normalized = min(rates[key] / ENGAGEMENT_CAPS_PER_WEEK[key], 1.0)
        score += weight * normalized
    return round(score * 100.0, 2)


def time_on_task_hours(durations_minutes: Sequence[float], weeks: float) -> float:
    """Active learning hours per week (total session minutes / 60 / weeks)."""
    weeks = max(weeks, 1e-9)
    total_minutes = float(np.nansum(np.asarray(durations_minutes, dtype=float))) \
        if len(durations_minutes) else 0.0
    return round(total_minutes / 60.0 / weeks, 2)


def quiz_trend(scores_in_time_order: Sequence[float]) -> tuple[str, float]:
    """Trend over the last :data:`QUIZ_TREND_WINDOW` quiz scores.

    Fits a line (score vs. attempt index) to the most recent scores and
    classifies the slope as ``positive`` / ``negative`` / ``flat``. Fewer than
    two scores yields ``("flat", 0.0)``.

    Returns a ``(label, slope)`` tuple.
    """
    scores = [float(s) for s in scores_in_time_order if s is not None and not pd.isna(s)]
    recent = scores[-QUIZ_TREND_WINDOW:]
    if len(recent) < 2:
        return "flat", 0.0
    x = np.arange(len(recent), dtype=float)
    slope = float(np.polyfit(x, np.asarray(recent, dtype=float), 1)[0])
    if slope > QUIZ_TREND_FLAT_EPS:
        label = "positive"
    elif slope < -QUIZ_TREND_FLAT_EPS:
        label = "negative"
    else:
        label = "flat"
    return label, round(slope, 3)


def session_regularity(login_times: Sequence) -> float:
    """Std-dev (in days) of gaps between consecutive distinct login days.

    Lower means more regular. Fewer than two distinct login days returns
    ``0.0`` (not enough data to measure variability).
    """
    if len(login_times) == 0:
        return 0.0
    days = pd.to_datetime(pd.Series(list(login_times))).dt.normalize().drop_duplicates()
    days = days.sort_values()
    if len(days) < 2:
        return 0.0
    gaps = days.diff().dropna().dt.total_seconds().to_numpy() / 86400.0
    return round(float(np.std(gaps)), 3)


def submission_rate(on_time_flags: Sequence[bool]) -> float:
    """Percentage of assignments submitted on time (0–100).

    The denominator is the number of assigned assignments. No assignments
    returns ``0.0``.
    """
    total = len(on_time_flags)
    if total == 0:
        return 0.0
    on_time = sum(1 for flag in on_time_flags if bool(flag))
    return round(on_time / total * 100.0, 2)


def at_risk_flag(engagement: float, quiz_trend_label: str) -> bool:
    """At risk when engagement is low *and* the quiz trend is negative."""
    return engagement < AT_RISK_ENGAGEMENT_MAX and quiz_trend_label == "negative"


# --- per-student assembly --------------------------------------------------


@dataclass
class StudentFacts:
    """The slice of fact data for a single student."""

    n_sessions: int
    n_page_views: int
    durations_minutes: Sequence[float]
    login_times: Sequence
    quiz_scores_in_time_order: Sequence[float]
    on_time_flags: Sequence[bool]


def compute_student(student_id: str, facts: StudentFacts, weeks: float) -> dict:
    """Compute the full indicator set for one student as a row dict."""
    engagement = engagement_score(
        facts.n_sessions, facts.n_page_views,
        len(facts.quiz_scores_in_time_order), weeks,
    )
    trend_label, trend_slope = quiz_trend(facts.quiz_scores_in_time_order)
    return {
        "student_id": student_id,
        "engagement_score": engagement,
        "time_on_task_hours": time_on_task_hours(facts.durations_minutes, weeks),
        "quiz_trend": trend_label,
        "quiz_trend_slope": trend_slope,
        "session_regularity": session_regularity(facts.login_times),
        "submission_rate": submission_rate(facts.on_time_flags),
        "at_risk_flag": at_risk_flag(engagement, trend_label),
    }


def compute_all(
    students: pd.DataFrame,
    sessions: pd.DataFrame,
    page_views: pd.DataFrame,
    quiz_attempts: pd.DataFrame,
    submissions: pd.DataFrame,
    weeks: float,
    computed_at: datetime | None = None,
) -> pd.DataFrame:
    """Compute indicators for every student and return an ordered DataFrame.

    Each input is a core fact/dim DataFrame. Students with no activity still
    get a row (all-zero / flat indicators), so the analytics table covers the
    whole cohort.
    """
    # Naive UTC timestamp (matches the TIMESTAMP column type).
    computed_at = computed_at or datetime.now(UTC).replace(tzinfo=None)

    # Pre-group facts by student for O(1) lookup per student.
    sess_by = sessions.groupby("student_id") if len(sessions) else None
    pv_counts = page_views.groupby("student_id").size() if len(page_views) else pd.Series(dtype=int)
    quiz_sorted = (
        quiz_attempts.sort_values("submitted_at") if len(quiz_attempts) else quiz_attempts
    )
    quiz_by = quiz_sorted.groupby("student_id") if len(quiz_sorted) else None
    sub_by = submissions.groupby("student_id") if len(submissions) else None

    rows: list[dict] = []
    for student_id in students["student_id"]:
        if sess_by is not None and student_id in sess_by.groups:
            s = sess_by.get_group(student_id)
            durations = s["duration_minutes"].to_numpy()
            logins = s["login_at"].to_numpy()
            n_sessions = len(s)
        else:
            durations, logins, n_sessions = np.array([]), np.array([]), 0

        if quiz_by is not None and student_id in quiz_by.groups:
            scores = quiz_by.get_group(student_id)["score"].to_numpy()
        else:
            scores = np.array([])

        if sub_by is not None and student_id in sub_by.groups:
            on_time = sub_by.get_group(student_id)["on_time"].to_numpy()
        else:
            on_time = np.array([])

        facts = StudentFacts(
            n_sessions=n_sessions,
            n_page_views=int(pv_counts.get(student_id, 0)),
            durations_minutes=durations,
            login_times=logins,
            quiz_scores_in_time_order=scores,
            on_time_flags=on_time,
        )
        row = compute_student(student_id, facts, weeks)
        row["computed_at"] = computed_at
        rows.append(row)

    return pd.DataFrame(rows, columns=INDICATOR_COLUMNS)
