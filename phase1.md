# Student Learning Analytics & AI Feedback System — Build Plan

## Context

Greenfield project (empty directory). Goal: a research-grade, production-quality, demo-ready
end-to-end learning analytics system inspired by CATALPA/LEAD:FUH (FernUniversität Hagen).
It simulates LMS data, runs an Airflow pipeline into a PostgreSQL star schema, computes
per-student learning indicators, generates personalized AI feedback via a LangChain RAG
pipeline, and surfaces everything through FastAPI + a Streamlit dashboard. Everything must
run with a single `docker-compose up`, no hardcoded secrets, idempotent DAGs, clean enough
for a technical interview.

Build strictly phase-by-phase, file-by-file, no placeholder stubs.

## Tech stack (strict — no substitutions)

Python 3.11 (container) · Airflow 2.9 · PostgreSQL 16 · Docker + Compose · Pandas/NumPy ·
LangChain + OpenAI · ChromaDB · FastAPI · Streamlit · GitHub Actions · pytest · ruff.

## Target folder structure

```
student-learning-analytics/
├── README.md
├── .env.example
├── .gitignore
├── docker-compose.yml
├── pyproject.toml                # deps + ruff + pytest config (single source)
├── Makefile                      # convenience: up, down, seed, test, lint
├── .github/
│   └── workflows/
│       └── ci.yml
├── data/
│   ├── raw/                      # generated CSV/JSON (gitignored except .gitkeep)
│   └── pedagogy/                 # 6 markdown docs for RAG
├── docker/
│   ├── airflow.Dockerfile
│   ├── api.Dockerfile
│   └── streamlit.Dockerfile
├── sql/
│   ├── 01_schema.sql             # staging + star + analytics schemas/tables
│   └── 02_indexes.sql
├── src/
│   └── sla/                      # installable package (shared by all services)
│       ├── __init__.py
│       ├── config.py             # pydantic-settings, env-driven
│       ├── db.py                 # SQLAlchemy engine/session helpers
│       ├── simulate/
│       │   ├── __init__.py
│       │   └── generate.py       # Faker data simulation → data/raw
│       ├── indicators/
│       │   ├── __init__.py
│       │   └── compute.py        # pure functions, one per indicator
│       ├── dq/
│       │   ├── __init__.py
│       │   └── checks.py         # missing/range/duplicate checks
│       ├── rag/
│       │   ├── __init__.py
│       │   ├── ingest.py         # load → chunk → embed → ChromaDB
│       │   ├── retrieve.py       # profile → top-3 chunks
│       │   └── generate.py       # LangChain feedback chain
│       └── api/
│           ├── __init__.py
│           ├── main.py           # FastAPI app + routes
│           ├── schemas.py        # Pydantic models
│           └── deps.py           # DB / service dependencies
├── dags/
│   ├── dag_ingest.py
│   ├── dag_transform.py
│   └── dag_indicators.py
├── dashboard/
│   ├── Home.py                   # Streamlit entry (Overview)
│   ├── api_client.py             # FastAPI client w/ graceful-degradation
│   └── pages/
│       ├── 1_Student_List.py
│       ├── 2_Student_Detail.py
│       └── 3_At_Risk.py
└── tests/
    ├── conftest.py
    ├── test_indicators.py        # Phase 3 unit tests
    ├── test_dq.py
    ├── test_simulate.py
    └── test_api.py               # Phase 4 integration tests (TestClient)
```

## Phase plan

### Phase 1 — Scaffolding + simulated LMS data
- Folder structure, `pyproject.toml`, `.gitignore`, `.env.example`, `README` skeleton.
- `src/sla/simulate/generate.py`: Faker seed (deterministic) →
  - 50 students (student_id, name, program, enrollment_date)
  - sessions (login/logout ts, duration, device type)
  - page_views (resource, time_spent)
  - quiz_attempts (quiz_id, score, attempt_number, ts)
  - assignment_submissions (assignment_id, submitted_at, grade, due_at)
  - dim courses + resources reference data
- Output CSV + JSON to `data/raw/`. CLI entrypoint (`python -m sla.simulate.generate`).
- `test_simulate.py` (row counts, FK integrity, value ranges).
- README Phase-1 section.

### Phase 2 — Docker + PostgreSQL + Airflow
- `docker-compose.yml`: postgres, airflow-init, airflow-webserver, airflow-scheduler,
  chromadb, api, streamlit. Healthchecks + depends_on. Named volumes.
- `sql/01_schema.sql`: `staging`, star (`dim_students`, `dim_courses`, `dim_resources`,
  `fact_sessions`, `fact_quiz_attempts`, `fact_page_views`, fact_submissions),
  `analytics.student_indicators`.
- DAGs (idempotent via upsert / truncate-reload of staging, `MERGE`/ON CONFLICT for dims):
  - `dag_ingest.py`: raw → validate (`sla.dq`) → staging
  - `dag_transform.py`: staging → star + DQ gate
  - `dag_indicators.py`: star → `analytics.student_indicators`
- DQ layer `sla/dq/checks.py`: missing values, out-of-range scores (0–100), duplicates.

### Phase 3 — Learning indicators
- `src/sla/indicators/compute.py`, one pure function each:
  - `engagement_score` (0–100 weighted composite)
  - `time_on_task_hours` (per week)
  - `quiz_trend` (slope over last 5 → positive/negative/flat)
  - `session_regularity` (std-dev of days between logins)
  - `submission_rate` (% on-time)
  - `at_risk_flag` (engagement < 40 AND quiz_trend negative)
- Wired into `dag_indicators.py`. Full unit tests in `test_indicators.py` (edge cases:
  no data, single attempt, ties).

### Phase 4 — RAG + FastAPI
- `data/pedagogy/`: 6 markdown docs (self-regulated learning, time management,
  interpreting quiz feedback, study-habit research, motivation, help-seeking).
- RAG: `ingest.py` (chunk + embed → ChromaDB), `retrieve.py` (profile → top-3),
  `generate.py` (LangChain chain → 3-paragraph feedback). LLM provider abstracted so it
  runs without an OpenAI key (see Decisions).
- FastAPI `api/main.py`: `GET /health`, `GET /students`, `GET /students/{id}`,
  `GET /students/{id}/feedback`. Pydantic schemas, proper status codes + error bodies.
- `test_api.py` integration tests via `TestClient` (mocked LLM).

### Phase 5 — Streamlit dashboard
- Multi-page app, Plotly charts, all data via `api_client.py` (no direct DB).
  - Overview: metric cards (total, % at-risk, avg engagement, avg quiz trend)
  - Student list: sortable table → detail
  - Student detail: radar chart, quiz trend line, AI feedback panel, session heatmap
  - At-risk: filtered list + bulk generate-feedback
- Graceful banner when API unavailable.

### Phase 6 — CI/CD + polish
- `.github/workflows/ci.yml`: ruff → pytest → docker build.
- Full README: overview, Mermaid architecture diagram, prerequisites, quickstart,
  per-phase run instructions, screenshots placeholder, tech-stack table.
- `.env.example` complete; docstrings everywhere.

## Cross-cutting

- Single installable package `src/sla` reused by DAGs, API, simulation, tests → no
  duplicated logic across services.
- `sla/config.py` via pydantic-settings; all secrets/config from env.
- Determinism: seeded Faker + seeded NumPy so indicators/tests are reproducible.

## Verification

- `python -m sla.simulate.generate` produces files in `data/raw/` (Phase 1).
- `pytest` green for indicators, dq, simulate, api.
- `ruff check .` clean.
- `docker-compose up` brings all services healthy; trigger DAGs in Airflow UI (or
  `airflow dags trigger`) in order ingest → transform → indicators; verify
  `analytics.student_indicators` populated.
- Hit `GET /health` and `GET /students` on the API; open Streamlit, confirm pages render
  and feedback panel returns text.

## Decisions

- **LLM**: OpenAI when `OPENAI_API_KEY` is set; deterministic mock fallback (mock embeddings
  + templated feedback) when absent → demo + CI run offline, real key upgrades quality.
  Provider chosen in `sla/config.py`, abstracted behind `sla/rag/generate.py`.
- **Start with Phase 1** (scaffolding + Faker simulation), fully file-by-file, then stop for
  review before Phase 2.
