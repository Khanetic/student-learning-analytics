"""Dependencies for the API: data access and service providers.

Data access and the RAG feedback service are exposed through FastAPI
dependencies so they can be swapped for fakes in tests via
``app.dependency_overrides`` — no database or vector store required to test the
HTTP layer.
"""

from __future__ import annotations

import logging
from functools import lru_cache

import pandas as pd

from sla.api.schemas import Indicators, QuizAttempt, SessionActivity, Student
from sla.config import get_settings
from sla.db import ANALYTICS_SCHEMA, CORE_SCHEMA, fetch_df, get_engine
from sla.rag.provider import provider_name

log = logging.getLogger(__name__)

_INDICATOR_FIELDS = (
    "engagement_score",
    "time_on_task_hours",
    "quiz_trend",
    "quiz_trend_slope",
    "session_regularity",
    "submission_rate",
    "at_risk_flag",
    "computed_at",
)

_STUDENT_QUERY = f"""
    SELECT s.student_id, s.name, s.program, s.enrollment_date,
           i.engagement_score, i.time_on_task_hours, i.quiz_trend,
           i.quiz_trend_slope, i.session_regularity, i.submission_rate,
           i.at_risk_flag, i.computed_at
    FROM {CORE_SCHEMA}.dim_students s
    LEFT JOIN {ANALYTICS_SCHEMA}.student_indicators i USING (student_id)
"""


def _row_to_student(row: pd.Series) -> Student:
    """Map a joined DB row into a :class:`Student`, indicators optional."""
    indicators = None
    if pd.notna(row.get("engagement_score")):
        indicators = Indicators(**{f: row[f] for f in _INDICATOR_FIELDS})
    return Student(
        student_id=row["student_id"],
        name=row["name"],
        program=row["program"],
        enrollment_date=row["enrollment_date"],
        indicators=indicators,
    )


class StudentRepository:
    """Read access to students and their indicators."""

    def list_students(self) -> list[Student]:
        df = fetch_df(_STUDENT_QUERY + " ORDER BY s.student_id")
        return [_row_to_student(r) for _, r in df.iterrows()]

    def get_student(self, student_id: str) -> Student | None:
        df = fetch_df(
            _STUDENT_QUERY + " WHERE s.student_id = :sid",
            params={"sid": student_id},
        )
        if df.empty:
            return None
        return _row_to_student(df.iloc[0])

    def get_quiz_attempts(self, student_id: str) -> list[QuizAttempt]:
        df = fetch_df(
            f"""SELECT quiz_id, attempt_number, score, submitted_at
                FROM {CORE_SCHEMA}.fact_quiz_attempts
                WHERE student_id = :sid
                ORDER BY submitted_at""",
            params={"sid": student_id},
        )
        return [QuizAttempt(**r) for _, r in df.iterrows()]

    def get_sessions(self, student_id: str) -> list[SessionActivity]:
        df = fetch_df(
            f"""SELECT login_at, duration_minutes, device_type
                FROM {CORE_SCHEMA}.fact_sessions
                WHERE student_id = :sid
                ORDER BY login_at""",
            params={"sid": student_id},
        )
        return [SessionActivity(**r) for _, r in df.iterrows()]


# --- health probes ---------------------------------------------------------


def check_database() -> bool:
    """Return True if the database answers a trivial query."""
    try:
        fetch_df("SELECT 1 AS ok")
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("Database health check failed: %s", exc)
        return False


def check_vector_store() -> bool:
    """Return True if ChromaDB responds to a heartbeat."""
    try:
        from sla.rag.ingest import get_chroma_client

        get_chroma_client().heartbeat()
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("Vector store health check failed: %s", exc)
        return False


# --- FastAPI dependency providers ------------------------------------------


@lru_cache(maxsize=1)
def _repository() -> StudentRepository:
    return StudentRepository()


def get_student_repository() -> StudentRepository:
    """Provide the student repository (override in tests)."""
    return _repository()


@lru_cache(maxsize=1)
def _feedback_service():
    from sla.rag.service import build_feedback_service

    return build_feedback_service()


def get_feedback_service():
    """Provide the RAG feedback service (override in tests)."""
    return _feedback_service()


def get_llm_provider_name() -> str:
    """Name of the active LLM provider ('openai' or 'mock')."""
    return provider_name(get_settings())


def warm_engine() -> None:
    """Touch the engine at startup so connection errors surface early."""
    try:
        get_engine()
    except Exception as exc:  # noqa: BLE001
        log.warning("Engine warm-up failed: %s", exc)
