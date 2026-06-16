-- ===========================================================================
-- 02_indexes.sql — secondary indexes for the analytical query patterns
-- ===========================================================================
-- Idempotent (IF NOT EXISTS). Facts are queried per student (indicator
-- computation) and filtered by time, so index the foreign keys and timestamps.
-- ===========================================================================

CREATE INDEX IF NOT EXISTS ix_sessions_student   ON core.fact_sessions (student_id);
CREATE INDEX IF NOT EXISTS ix_sessions_login     ON core.fact_sessions (login_at);

CREATE INDEX IF NOT EXISTS ix_pageviews_student  ON core.fact_page_views (student_id);
CREATE INDEX IF NOT EXISTS ix_pageviews_session  ON core.fact_page_views (session_id);
CREATE INDEX IF NOT EXISTS ix_pageviews_resource ON core.fact_page_views (resource_id);

CREATE INDEX IF NOT EXISTS ix_quiz_student       ON core.fact_quiz_attempts (student_id);
CREATE INDEX IF NOT EXISTS ix_quiz_quiz          ON core.fact_quiz_attempts (student_id, quiz_id, attempt_number);

CREATE INDEX IF NOT EXISTS ix_subs_student       ON core.fact_assignment_submissions (student_id);

CREATE INDEX IF NOT EXISTS ix_resources_course   ON core.dim_resources (course_id);

CREATE INDEX IF NOT EXISTS ix_indicators_at_risk ON analytics.student_indicators (at_risk_flag);
