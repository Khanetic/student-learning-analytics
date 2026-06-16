-- ===========================================================================
-- 01_schema.sql — schemas + star schema + analytics tables
-- ===========================================================================
-- Idempotent: safe to run repeatedly (IF NOT EXISTS everywhere). Runs against
-- the application database (`sla`).
--
--   staging   : raw landing tables (created dynamically by the ingest DAG)
--   core      : the dimensional star schema (dims + facts)
--   analytics : derived per-student learning indicators
-- ===========================================================================

CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS analytics;

-- ---------------------------------------------------------------------------
-- Dimensions
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS core.dim_students (
    student_id      TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    program         TEXT NOT NULL,
    enrollment_date DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS core.dim_courses (
    course_id   TEXT PRIMARY KEY,
    course_code TEXT NOT NULL,
    course_name TEXT NOT NULL,
    credits     INTEGER NOT NULL CHECK (credits > 0)
);

CREATE TABLE IF NOT EXISTS core.dim_resources (
    resource_id   TEXT PRIMARY KEY,
    course_id     TEXT NOT NULL REFERENCES core.dim_courses (course_id),
    title         TEXT NOT NULL,
    resource_type TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- Facts
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS core.fact_sessions (
    session_id       TEXT PRIMARY KEY,
    student_id       TEXT NOT NULL REFERENCES core.dim_students (student_id),
    login_at         TIMESTAMP NOT NULL,
    logout_at        TIMESTAMP NOT NULL,
    duration_minutes NUMERIC(6, 1) NOT NULL CHECK (duration_minutes >= 0),
    device_type      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS core.fact_page_views (
    page_view_id       TEXT PRIMARY KEY,
    session_id         TEXT NOT NULL REFERENCES core.fact_sessions (session_id),
    student_id         TEXT NOT NULL REFERENCES core.dim_students (student_id),
    resource_id        TEXT NOT NULL REFERENCES core.dim_resources (resource_id),
    viewed_at          TIMESTAMP NOT NULL,
    time_spent_seconds NUMERIC(8, 1) NOT NULL CHECK (time_spent_seconds >= 0)
);

CREATE TABLE IF NOT EXISTS core.fact_quiz_attempts (
    attempt_id     TEXT PRIMARY KEY,
    student_id     TEXT NOT NULL REFERENCES core.dim_students (student_id),
    course_id      TEXT NOT NULL REFERENCES core.dim_courses (course_id),
    quiz_id        TEXT NOT NULL,
    attempt_number INTEGER NOT NULL CHECK (attempt_number >= 1),
    score          NUMERIC(5, 1) NOT NULL CHECK (score BETWEEN 0 AND 100),
    submitted_at   TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS core.fact_assignment_submissions (
    submission_id TEXT PRIMARY KEY,
    student_id    TEXT NOT NULL REFERENCES core.dim_students (student_id),
    course_id     TEXT NOT NULL REFERENCES core.dim_courses (course_id),
    assignment_id TEXT NOT NULL,
    due_at        TIMESTAMP NOT NULL,
    submitted_at  TIMESTAMP,
    grade         NUMERIC(5, 1) CHECK (grade IS NULL OR grade BETWEEN 0 AND 100),
    on_time       BOOLEAN NOT NULL DEFAULT FALSE
);

-- ---------------------------------------------------------------------------
-- Analytics (Phase 3 populates this, declared now so the schema is complete)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS analytics.student_indicators (
    student_id         TEXT PRIMARY KEY REFERENCES core.dim_students (student_id),
    engagement_score   NUMERIC(5, 2) NOT NULL,
    time_on_task_hours NUMERIC(7, 2) NOT NULL,
    quiz_trend         TEXT NOT NULL CHECK (quiz_trend IN ('positive', 'negative', 'flat')),
    quiz_trend_slope   NUMERIC(7, 3) NOT NULL,
    session_regularity NUMERIC(7, 3) NOT NULL,
    submission_rate    NUMERIC(5, 2) NOT NULL CHECK (submission_rate BETWEEN 0 AND 100),
    at_risk_flag       BOOLEAN NOT NULL DEFAULT FALSE,
    computed_at        TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Feedback delivery audit log (Phase 6: n8n automation + human-in-the-loop)
-- ---------------------------------------------------------------------------
-- Every feedback delivery / review decision is appended here so the n8n
-- workflows (weekly delivery, teacher review) and the dashboard have an audit
-- trail. Append-only; one row per event.

CREATE TABLE IF NOT EXISTS analytics.feedback_log (
    id            BIGSERIAL PRIMARY KEY,
    student_id    TEXT NOT NULL REFERENCES core.dim_students (student_id),
    channel       TEXT NOT NULL DEFAULT 'email'      -- email | slack | manual
        CHECK (channel IN ('email', 'slack', 'manual')),
    status        TEXT NOT NULL                       -- sent | approved | edited | rejected | failed
        CHECK (status IN ('sent', 'approved', 'edited', 'rejected', 'failed')),
    feedback_text TEXT,
    note          TEXT,                               -- rejection reason / edit note
    created_at    TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feedback_log_student
    ON analytics.feedback_log (student_id, created_at DESC);
