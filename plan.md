# Plan: Next.js Dashboard + n8n Automation + Improvement Doc

## Context

The repo (`student-learning-analytics`) is a mature, phase-built Student Learning
Analytics stack: Airflow ETL → Postgres star schema → indicators → LangChain/Chroma RAG
→ FastAPI → Streamlit, all wired in `docker-compose.yml`. The shared logic lives in
`src/sla/` and is reused by Airflow, the API, and tests.

Goal of this work (3 tasks, phased):

1. **Task 1** — Add a Next.js 14 (App Router) dashboard that mirrors Streamlit, talking
   only to FastAPI. New `frontend/` service on port 3000.
2. **Task 2** — Add self-hosted **n8n** as an event/automation layer alongside Airflow,
   with 5 importable workflows + the 4 supporting API endpoints (and one audit table)
   they depend on.
3. **Task 3** — Deliver `IMPROVEMENTS.md`: a structured ideas doc (8 categories, each
   item tagged difficulty / time / portfolio-impact). No code.

### Key facts established from exploration
- **CORS already includes `http://localhost:3000`** — `src/sla/config.py:64` default and
  `.env.example`. The "update CORS" requirement is already satisfied; just confirm.
- `GET /students` already returns full indicators inline (`Student.indicators`), so the
  Overview KPIs + Student List need a single fetch. Contract in `src/sla/api/schemas.py`.
- Existing endpoints: `/health`, `/students`, `/students/{id}`, `/students/{id}/quiz-attempts`,
  `/students/{id}/sessions`, `/students/{id}/feedback`. Defined in `src/sla/api/main.py`,
  data access in `src/sla/api/deps.py` (`StudentRepository`).
- No audit/log table exists. n8n workflows 1 & 4 need one — add `analytics.feedback_log`.
- Indicator value ranges (for radar normalization) come from `src/sla/indicators/compute.py`:
  engagement 0–100, submission_rate 0–100, quiz_trend_slope (signed), session_regularity
  (days std-dev, lower=better → invert), time_on_task_hours (cap ~10/wk for scaling).
- Schemas: `core` (dims/facts), `analytics` (`student_indicators`). `CORE_SCHEMA`/
  `ANALYTICS_SCHEMA` constants in `src/sla/db.py`.

---

## Phase A — Backend: new endpoints + audit table (do FIRST; both Task 1 & 2 lean on it)

New SQL (append to `sql/01_schema.sql`, idempotent `IF NOT EXISTS`): `analytics.feedback_log`
(id, student_id FK, channel, status, feedback_text, note, created_at).

New endpoints (`src/sla/api/main.py` + repo methods in `src/sla/api/deps.py`,
schemas in `src/sla/api/schemas.py`):
- `GET  /students/at-risk` → reuse `repo.list_students()`, filter `indicators.at_risk_flag`.
  Add `list_at_risk()` to `StudentRepository`. Must be declared BEFORE `/students/{id}`.
- `POST /students/{id}/feedback/log` → insert into `analytics.feedback_log`.
- `POST /pipeline/trigger` → Airflow REST `POST /api/v1/dags/{dag_id}/dagRuns`.
- `GET  /pipeline/status/{dag_id}` → Airflow REST latest dagRun state.
  Airflow REST calls in new `src/sla/api/airflow_client.py` (httpx).

Config additions (`src/sla/config.py` + `.env.example`): `AIRFLOW_API_URL`, reuse
`AIRFLOW_ADMIN_USER/PASSWORD`. Enable Airflow REST basic-auth backend on the webserver.

Tests: extend `tests/test_api.py` with dependency-overridden fakes.

---

## Phase B — Task 1: Next.js dashboard (`frontend/`)

Stack: Next.js 14 App Router, TypeScript, Tailwind, shadcn/ui, Recharts. Talks to
`NEXT_PUBLIC_API_URL` (default `http://localhost:8001`).

Pages: `/` Overview (KPI cards, engagement histogram, at-risk donut, quiz-trend bar);
`/students` sortable/filterable table; `/students/[id]` radar + quiz-trend line + session
heatmap + AI feedback panel; `/at-risk` filtered list + bulk feedback + CSV export.

`lib/api.ts` typed client, `lib/types.ts` mirroring schemas, `lib/utils.ts`
(`normalizeIndicators` for radar). shadcn ui components, Recharts charts, theme toggle,
loading skeletons, error boundary + API-unreachable banner, dark mode, multi-stage Dockerfile.

Compose: add `frontend` service (port 3000, `NEXT_PUBLIC_API_URL=http://localhost:8001`
browser-side host URL, `depends_on: api`). Streamlit kept (mirror, not replace).

---

## Phase C — Task 2: n8n integration

Compose: add `n8n` service (`n8nio/n8n`, port 5678, basic auth admin/admin from `.env`,
`WEBHOOK_URL`, volume `n8n-data`). New `.env` keys: n8n auth, SMTP_*, SLACK_WEBHOOK_URL.

Workflows under `n8n/workflows/` (importable JSON), documented in `n8n/README.md`:
1. `01_at_risk_alert.json` — daily 8AM → at-risk → diff → email + Slack + feedback_log.
2. `02_weekly_feedback.json` — Mon 9AM → loop students → feedback → email → log → Slack.
3. `03_pipeline_trigger_monitor.json` — trigger dag_ingest, poll, chain, alert, refresh.
4. `04_teacher_review.json` — webhook → Slack Approve/Edit/Reject → email/log.
5. `05_new_student_onboarding.json` — webhook → welcome email → card → schedule.

---

## Phase D — Task 3: `IMPROVEMENTS.md`

Single markdown doc, 8 sections, each idea = what / why / sketch / difficulty / time /
impact. Sketches anchored to actual files. Prioritized top-5 quick-wins table at top.

---

## Verification

- Backend: `pytest -q`, `ruff check`; `docker compose up -d`; curl new endpoints.
- Next.js: `docker compose up frontend` → click 4 pages, feedback, CSV; stop api → banner.
- n8n: import 5 JSON at :5678; run workflow 1 + fire workflow 4 webhook via curl.
- CI: `.github/workflows/ci.yml` green; optional frontend build step.

## Notes
- CORS for :3000 already configured — verify only.
- Streamlit kept (mirrored). SMTP/Slack/Notion creds user-supplied via `.env`.
