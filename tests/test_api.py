"""Phase 4 integration tests for the FastAPI app.

The data layer and RAG service are replaced with in-memory fakes via
``app.dependency_overrides`` so the HTTP contract is tested without a database,
vector store, or LLM.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from sla.api import deps
from sla.api.main import app
from sla.api.schemas import (
    FeedbackLogEntry,
    FeedbackLogIn,
    Indicators,
    QuizAttempt,
    SessionActivity,
    Student,
)
from sla.rag.generate import FeedbackResult
from sla.rag.retrieve import RetrievedChunk


def _indicators(at_risk: bool = False) -> Indicators:
    return Indicators(
        engagement_score=72.5,
        time_on_task_hours=3.1,
        quiz_trend="positive",
        quiz_trend_slope=2.4,
        session_regularity=1.2,
        submission_rate=80.0,
        at_risk_flag=at_risk,
        computed_at=datetime(2026, 6, 16, 12, 0, 0),
    )


def _student(sid: str, with_indicators: bool = True, at_risk: bool = False) -> Student:
    return Student(
        student_id=sid,
        name=f"Student {sid}",
        program="B.Sc. Computer Science",
        enrollment_date=date(2025, 10, 1),
        indicators=_indicators(at_risk=at_risk) if with_indicators else None,
    )


class FakeRepo:
    def __init__(self, students: list[Student]) -> None:
        self._by_id = {s.student_id: s for s in students}
        self.logged: list[FeedbackLogEntry] = []

    def list_students(self) -> list[Student]:
        return list(self._by_id.values())

    def list_at_risk(self) -> list[Student]:
        return [
            s for s in self._by_id.values()
            if s.indicators is not None and s.indicators.at_risk_flag
        ]

    def log_feedback(self, student_id: str, entry: FeedbackLogIn) -> FeedbackLogEntry:
        stored = FeedbackLogEntry(
            id=len(self.logged) + 1,
            student_id=student_id,
            created_at=datetime(2026, 6, 16, 9, 0, 0),
            channel=entry.channel,
            status=entry.status,
            feedback_text=entry.feedback_text,
            note=entry.note,
        )
        self.logged.append(stored)
        return stored

    def get_student(self, student_id: str):
        return self._by_id.get(student_id)

    def get_quiz_attempts(self, student_id: str):
        return [
            QuizAttempt(quiz_id="QCS101-01", attempt_number=1, score=70.0,
                        submitted_at=datetime(2026, 5, 1, 10, 0, 0)),
            QuizAttempt(quiz_id="QCS101-01", attempt_number=2, score=80.0,
                        submitted_at=datetime(2026, 5, 8, 10, 0, 0)),
        ]

    def get_sessions(self, student_id: str):
        return [
            SessionActivity(login_at=datetime(2026, 5, 1, 18, 0, 0),
                            duration_minutes=45.0, device_type="laptop"),
        ]


class FakeFeedbackService:
    def generate_for(self, profile) -> FeedbackResult:
        return FeedbackResult(
            feedback="Para one.\n\nPara two.\n\nPara three.",
            provider="mock",
            context=[RetrievedChunk(text="Tip.", title="Study Habits", source="s.md")],
        )


@pytest.fixture
def client() -> TestClient:
    repo = FakeRepo([
        _student("S0001"),
        _student("S0002", with_indicators=False),
        _student("S0003", at_risk=True),
    ])
    app.dependency_overrides[deps.get_student_repository] = lambda: repo
    app.dependency_overrides[deps.get_feedback_service] = lambda: FakeFeedbackService()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_health_ok(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    # Provider is environment-driven (openai when a key is set, else mock).
    assert body["llm_provider"] in {"openai", "mock"}
    assert isinstance(body["database"], bool)
    assert isinstance(body["vector_store"], bool)


def test_list_students(client: TestClient) -> None:
    resp = client.get("/students")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    s1 = next(s for s in data if s["student_id"] == "S0001")
    assert s1["indicators"]["engagement_score"] == 72.5


def test_get_student_found(client: TestClient) -> None:
    resp = client.get("/students/S0001")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Student S0001"


def test_get_student_not_found(client: TestClient) -> None:
    resp = client.get("/students/NOPE")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_feedback_success(client: TestClient) -> None:
    resp = client.get("/students/S0001/feedback")
    assert resp.status_code == 200
    body = resp.json()
    assert body["student_id"] == "S0001"
    assert body["provider"] == "mock"
    assert len([p for p in body["feedback"].split("\n\n") if p.strip()]) == 3
    assert body["context"][0]["title"] == "Study Habits"


def test_feedback_student_not_found(client: TestClient) -> None:
    resp = client.get("/students/NOPE/feedback")
    assert resp.status_code == 404


def test_feedback_without_indicators_returns_409(client: TestClient) -> None:
    resp = client.get("/students/S0002/feedback")
    assert resp.status_code == 409
    assert "indicators" in resp.json()["detail"].lower()


def test_quiz_attempts(client: TestClient) -> None:
    resp = client.get("/students/S0001/quiz-attempts")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2 and data[0]["score"] == 70.0
    assert client.get("/students/NOPE/quiz-attempts").status_code == 404


def test_sessions(client: TestClient) -> None:
    resp = client.get("/students/S0001/sessions")
    assert resp.status_code == 200
    assert resp.json()[0]["device_type"] == "laptop"
    assert client.get("/students/NOPE/sessions").status_code == 404


def test_list_at_risk(client: TestClient) -> None:
    resp = client.get("/students/at-risk")
    assert resp.status_code == 200
    data = resp.json()
    # Only S0003 is flagged at-risk in the fixture.
    assert [s["student_id"] for s in data] == ["S0003"]
    assert data[0]["indicators"]["at_risk_flag"] is True


def test_log_feedback(client: TestClient) -> None:
    resp = client.post(
        "/students/S0001/feedback/log",
        json={"channel": "email", "status": "sent", "feedback_text": "Hi."},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["student_id"] == "S0001"
    assert body["status"] == "sent"
    assert body["id"] == 1


def test_log_feedback_student_not_found(client: TestClient) -> None:
    resp = client.post("/students/NOPE/feedback/log", json={"status": "sent"})
    assert resp.status_code == 404


def test_pipeline_trigger(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import sla.api.main as main

    monkeypatch.setattr(
        main, "trigger_dag",
        lambda dag_id: {"dag_run_id": "run_1", "state": "queued"},
    )
    resp = client.post("/pipeline/trigger", json={"dag_id": "dag_ingest"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["dag_id"] == "dag_ingest" and body["state"] == "queued"


def test_pipeline_status(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import sla.api.main as main

    monkeypatch.setattr(
        main, "latest_dag_run",
        lambda dag_id: {"dag_run_id": "run_1", "state": "success"},
    )
    resp = client.get("/pipeline/status/dag_ingest")
    assert resp.status_code == 200
    assert resp.json()["state"] == "success"


def test_pipeline_status_no_runs(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import sla.api.main as main

    monkeypatch.setattr(main, "latest_dag_run", lambda dag_id: None)
    resp = client.get("/pipeline/status/dag_ingest")
    assert resp.status_code == 404
