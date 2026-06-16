"""FastAPI application: students, indicators and AI feedback endpoints.

Endpoints
---------
* ``GET /health``                      — service + dependency health
* ``GET /students``                    — all students with indicators
* ``GET /students/at-risk``            — only at-risk students (alerting convenience)
* ``GET /students/{id}``               — one student + indicators
* ``GET /students/{id}/quiz-attempts`` — quiz attempts (trend chart)
* ``GET /students/{id}/sessions``      — sessions (activity heatmap)
* ``GET /students/{id}/feedback``      — RAG-generated personalized feedback
* ``POST /students/{id}/feedback/log`` — record a feedback delivery / review event
* ``POST /pipeline/trigger``           — trigger an Airflow DAG run
* ``GET /pipeline/status/{dag_id}``    — latest Airflow DAG run state
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Body, Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from sla.api import deps
from sla.api.airflow_client import AirflowError, latest_dag_run, trigger_dag
from sla.api.schemas import (
    Feedback,
    FeedbackLogEntry,
    FeedbackLogIn,
    Health,
    PipelineRun,
    PipelineTriggerIn,
    QuizAttempt,
    RetrievedContext,
    SessionActivity,
    Student,
)
from sla.config import get_settings
from sla.rag.generate import StudentProfile


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Warm the database engine on startup so connection errors surface early."""
    deps.warm_engine()
    yield


app = FastAPI(
    title="Student Learning Analytics API",
    description="Learning indicators and AI-generated feedback for a student cohort.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=Health, tags=["meta"])
def health() -> Health:
    """Report API health and the status of its dependencies."""
    db_ok = deps.check_database()
    vec_ok = deps.check_vector_store()
    return Health(
        status="ok" if db_ok else "degraded",
        database=db_ok,
        vector_store=vec_ok,
        llm_provider=deps.get_llm_provider_name(),
    )


@app.get("/students", response_model=list[Student], tags=["students"])
def list_students(
    repo: deps.StudentRepository = Depends(deps.get_student_repository),
) -> list[Student]:
    """Return every student with their computed indicators."""
    return repo.list_students()


@app.get("/students/at-risk", response_model=list[Student], tags=["students"])
def list_at_risk(
    repo: deps.StudentRepository = Depends(deps.get_student_repository),
) -> list[Student]:
    """Return only students flagged at-risk (convenience for alerting workflows).

    Declared before ``/students/{student_id}`` so the literal path wins over the
    dynamic one.
    """
    return repo.list_at_risk()


@app.get(
    "/students/{student_id}",
    response_model=Student,
    responses={404: {"description": "Student not found"}},
    tags=["students"],
)
def get_student(
    student_id: str,
    repo: deps.StudentRepository = Depends(deps.get_student_repository),
) -> Student:
    """Return a single student and their indicators."""
    student = repo.get_student(student_id)
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student '{student_id}' not found",
        )
    return student


@app.get(
    "/students/{student_id}/quiz-attempts",
    response_model=list[QuizAttempt],
    responses={404: {"description": "Student not found"}},
    tags=["students"],
)
def get_quiz_attempts(
    student_id: str,
    repo: deps.StudentRepository = Depends(deps.get_student_repository),
) -> list[QuizAttempt]:
    """Return a student's quiz attempts ordered by time (for the trend chart)."""
    if repo.get_student(student_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Student '{student_id}' not found")
    return repo.get_quiz_attempts(student_id)


@app.get(
    "/students/{student_id}/sessions",
    response_model=list[SessionActivity],
    responses={404: {"description": "Student not found"}},
    tags=["students"],
)
def get_sessions(
    student_id: str,
    repo: deps.StudentRepository = Depends(deps.get_student_repository),
) -> list[SessionActivity]:
    """Return a student's sessions ordered by time (for the activity heatmap)."""
    if repo.get_student(student_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Student '{student_id}' not found")
    return repo.get_sessions(student_id)


@app.get(
    "/students/{student_id}/feedback",
    response_model=Feedback,
    responses={
        404: {"description": "Student not found"},
        409: {"description": "Indicators not computed for this student"},
    },
    tags=["feedback"],
)
def get_feedback(
    student_id: str,
    repo: deps.StudentRepository = Depends(deps.get_student_repository),
    service=Depends(deps.get_feedback_service),
) -> Feedback:
    """Generate personalized feedback for a student via the RAG pipeline."""
    student = repo.get_student(student_id)
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student '{student_id}' not found",
        )
    if student.indicators is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"No indicators computed for '{student_id}'. "
                "Run the indicators pipeline first."
            ),
        )

    ind = student.indicators
    profile = StudentProfile(
        student_id=student.student_id,
        name=student.name,
        program=student.program,
        engagement_score=ind.engagement_score,
        time_on_task_hours=ind.time_on_task_hours,
        quiz_trend=ind.quiz_trend,
        quiz_trend_slope=ind.quiz_trend_slope,
        session_regularity=ind.session_regularity,
        submission_rate=ind.submission_rate,
        at_risk_flag=ind.at_risk_flag,
    )
    result = service.generate_for(profile)
    return Feedback(
        student_id=student_id,
        feedback=result.feedback,
        provider=result.provider,
        context=[
            RetrievedContext(title=c.title, source=c.source, text=c.text)
            for c in result.context
        ],
    )


@app.post(
    "/students/{student_id}/feedback/log",
    response_model=FeedbackLogEntry,
    status_code=status.HTTP_201_CREATED,
    responses={404: {"description": "Student not found"}},
    tags=["feedback"],
)
def log_feedback(
    student_id: str,
    entry: FeedbackLogIn,
    repo: deps.StudentRepository = Depends(deps.get_student_repository),
) -> FeedbackLogEntry:
    """Record a feedback delivery / review event (audit trail for n8n workflows)."""
    if repo.get_student(student_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Student '{student_id}' not found")
    return repo.log_feedback(student_id, entry)


# --- pipeline orchestration (Airflow REST passthrough) ---------------------


def _to_pipeline_run(dag_id: str, run: dict) -> PipelineRun:
    return PipelineRun(
        dag_id=dag_id,
        dag_run_id=run.get("dag_run_id", ""),
        state=run.get("state", "unknown"),
        logical_date=run.get("logical_date") or run.get("execution_date"),
        end_date=run.get("end_date"),
    )


@app.post("/pipeline/trigger", response_model=PipelineRun, tags=["pipeline"])
def pipeline_trigger(payload: PipelineTriggerIn = Body(default=PipelineTriggerIn())) -> PipelineRun:
    """Trigger an Airflow DAG run (e.g. dag_ingest) via the Airflow REST API."""
    try:
        run = trigger_dag(payload.dag_id)
    except AirflowError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return _to_pipeline_run(payload.dag_id, run)


@app.get(
    "/pipeline/status/{dag_id}",
    response_model=PipelineRun,
    responses={404: {"description": "No runs for this DAG"}},
    tags=["pipeline"],
)
def pipeline_status(dag_id: str) -> PipelineRun:
    """Return the latest run state for a DAG (poll target for the monitor workflow)."""
    try:
        run = latest_dag_run(dag_id)
    except AirflowError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"No runs found for '{dag_id}'")
    return _to_pipeline_run(dag_id, run)
