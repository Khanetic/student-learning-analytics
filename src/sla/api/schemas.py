"""Pydantic request/response models for the API.

A single schema layer keeps the API contract explicit and self-documenting
(FastAPI renders it into OpenAPI). All response models are read-only.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class Indicators(BaseModel):
    """The per-student learning indicators (Phase 3 output)."""

    engagement_score: float = Field(..., ge=0, le=100)
    time_on_task_hours: float = Field(..., ge=0)
    quiz_trend: str = Field(..., examples=["positive", "negative", "flat"])
    quiz_trend_slope: float
    session_regularity: float = Field(..., ge=0)
    submission_rate: float = Field(..., ge=0, le=100)
    at_risk_flag: bool
    computed_at: datetime


class StudentBase(BaseModel):
    """Core student attributes."""

    student_id: str
    name: str
    program: str
    enrollment_date: date


class Student(StudentBase):
    """A student plus their indicators (indicators may be absent if not computed)."""

    indicators: Indicators | None = None


class QuizAttempt(BaseModel):
    """A single quiz attempt (for the score-trend chart)."""

    quiz_id: str
    attempt_number: int
    score: float
    submitted_at: datetime


class SessionActivity(BaseModel):
    """A single learning session (for the activity heatmap)."""

    login_at: datetime
    duration_minutes: float
    device_type: str


class RetrievedContext(BaseModel):
    """A pedagogy passage used to ground the generated feedback."""

    title: str
    source: str
    text: str


class Feedback(BaseModel):
    """Generated personalized feedback for a student."""

    student_id: str
    feedback: str
    provider: str = Field(..., examples=["openai", "mock"])
    context: list[RetrievedContext] = Field(default_factory=list)


class Health(BaseModel):
    """Service health report."""

    status: str = Field(..., examples=["ok", "degraded"])
    database: bool
    vector_store: bool
    llm_provider: str


class ErrorResponse(BaseModel):
    """Uniform error body."""

    detail: str
