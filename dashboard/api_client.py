"""Thin client for the Student Learning Analytics API.

The dashboard talks **only** to the FastAPI backend (never the database). Every
call degrades gracefully: network/HTTP errors raise :class:`ApiError`, which the
pages catch to show a friendly banner instead of a stack trace.
"""

from __future__ import annotations

import os

import pandas as pd
import requests
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8001").rstrip("/")

DEFAULT_TIMEOUT = 15
FEEDBACK_TIMEOUT = 90  # real OpenAI generation can be slow


class ApiError(Exception):
    """Raised when the API is unreachable or returns an error status."""


def _get(path: str, timeout: int = DEFAULT_TIMEOUT) -> object:
    """GET ``path`` from the API and return parsed JSON, or raise ApiError."""
    url = f"{API_BASE_URL}{path}"
    try:
        resp = requests.get(url, timeout=timeout)
    except requests.RequestException as exc:
        raise ApiError(f"Cannot reach the API at {API_BASE_URL}. Is it running?") from exc
    if resp.status_code == 404:
        raise ApiError("Not found.")
    if resp.status_code == 409:
        raise ApiError(resp.json().get("detail", "Indicators not available."))
    if not resp.ok:
        raise ApiError(f"API error {resp.status_code}: {resp.text[:200]}")
    return resp.json()


def get_health() -> dict | None:
    """Return the health payload, or ``None`` if the API is unreachable."""
    try:
        return _get("/health", timeout=5)
    except ApiError:
        return None


@st.cache_data(ttl=60, show_spinner=False)
def list_students() -> list[dict]:
    """All students with indicators (cached 60s)."""
    return _get("/students")


@st.cache_data(ttl=60, show_spinner=False)
def get_student(student_id: str) -> dict:
    """One student with indicators (cached 60s)."""
    return _get(f"/students/{student_id}")


@st.cache_data(ttl=60, show_spinner=False)
def get_quiz_attempts(student_id: str) -> list[dict]:
    """A student's quiz attempts ordered by time (cached 60s)."""
    return _get(f"/students/{student_id}/quiz-attempts")


@st.cache_data(ttl=60, show_spinner=False)
def get_sessions(student_id: str) -> list[dict]:
    """A student's sessions ordered by time (cached 60s)."""
    return _get(f"/students/{student_id}/sessions")


def get_feedback(student_id: str) -> dict:
    """Generate feedback for a student (not cached; triggered on demand)."""
    return _get(f"/students/{student_id}/feedback", timeout=FEEDBACK_TIMEOUT)


def students_frame(students: list[dict]) -> pd.DataFrame:
    """Flatten the nested student/indicator JSON into a tidy DataFrame."""
    rows = []
    for s in students:
        ind = s.get("indicators") or {}
        rows.append(
            {
                "student_id": s["student_id"],
                "name": s["name"],
                "program": s["program"],
                "engagement_score": ind.get("engagement_score"),
                "time_on_task_hours": ind.get("time_on_task_hours"),
                "quiz_trend": ind.get("quiz_trend"),
                "quiz_trend_slope": ind.get("quiz_trend_slope"),
                "session_regularity": ind.get("session_regularity"),
                "submission_rate": ind.get("submission_rate"),
                "at_risk_flag": ind.get("at_risk_flag"),
            }
        )
    return pd.DataFrame(rows)


def require_api() -> dict:
    """Stop the page with a banner if the API is down; else return health."""
    health = get_health()
    if health is None:
        st.error(
            f"⚠️ The API at `{API_BASE_URL}` is unavailable. "
            "Start the stack with `docker compose up -d` and reload."
        )
        st.stop()
    return health


def render_sidebar(health: dict) -> None:
    """Render shared sidebar status (API health + LLM provider)."""
    with st.sidebar:
        st.caption("Backend status")
        db_ok = health.get("database")
        vec_ok = health.get("vector_store")
        st.write("🟢 API online" if health.get("status") == "ok" else "🟠 API degraded")
        st.write(f"{'🟢' if db_ok else '🔴'} Database")
        st.write(f"{'🟢' if vec_ok else '🔴'} Vector store")
        st.write(f"🤖 LLM: `{health.get('llm_provider', 'unknown')}`")
