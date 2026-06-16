# Improvement Ideas

Concrete, prioritized improvements for the Student Learning Analytics stack. Each item lists
**what / why / sketch**, plus **difficulty**, **est. time**, and **impact** (portfolio + production).
Sketches reference real files so they can be picked up directly.

## Top quick wins (start here)

| # | Improvement | Difficulty | Est. | Why it's a win |
|---|-------------|-----------|------|----------------|
| 1 | Pagination on `GET /students` | Easy | 0.5 d | Scales to large cohorts; tiny change |
| 2 | Cohort percentiles / class averages | Easy | 1 d | High analytics value, pure-Python |
| 3 | Prometheus metrics + `/metrics` | Easy | 0.5 d | Instant "production-ready" signal |
| 4 | Structured logging (structlog) | Easy | 0.5 d | Better debugging, low risk |
| 5 | Great Expectations on staging | Medium | 2 d | Hardens the existing DQ story |

---

## 1. New Learning Indicators & Analytics

### 1.1 Cohort-level analytics (class averages, percentiles)
- **What:** add cohort aggregates — mean/median/p25/p75 per indicator, and each student's
  percentile rank within their program.
- **Why:** a raw engagement of 55 is meaningless without "is that top-quartile or bottom?".
  Turns absolute numbers into relative insight teachers actually act on.
- **Sketch:** new `compute_cohort(indicators_df)` in `src/sla/indicators/compute.py` returning a
  cohort summary; persist to a new `analytics.cohort_stats` table; expose `GET /cohort/stats`.
  Show percentile bands behind the radar in `frontend/components/charts/indicator-radar.tsx`.
- **Difficulty:** Easy · **Est.:** 1 d · **Impact:** High analytics value; cheap.

### 1.2 Learning velocity tracking over time
- **What:** snapshot indicators per run (SCD-style) and compute week-over-week deltas
  (Δengagement, Δquiz score).
- **Why:** direction matters more than level for intervention timing.
- **Sketch:** append-only `analytics.indicator_history(student_id, computed_at, …)` written by
  `dags/dag_indicators.py`; a `velocity()` helper; a sparkline on the student detail page.
- **Difficulty:** Medium · **Est.:** 2 d · **Impact:** High; unlocks trend ML (§2).

### 1.3 Peer comparison
- **What:** "students like you" — compare a student against their program/cohort cluster.
- **Why:** motivational framing; supports the RAG feedback with concrete benchmarks.
- **Sketch:** reuse cohort stats (§1.1) + cluster labels (§2.4); add comparison fields to the
  `StudentProfile` passed into `src/sla/rag/generate.py`.
- **Difficulty:** Medium · **Est.:** 2 d · **Impact:** Medium-high; differentiates the feedback.

## 2. ML / Predictive Features

### 2.1 Dropout / churn prediction
- **What:** classifier predicting disengagement/dropout from historical indicators.
- **Why:** moves the product from descriptive → predictive; the headline portfolio feature.
- **Sketch:** needs `indicator_history` (§1.2) for labels. New `src/sla/ml/dropout.py` training a
  scikit-learn `GradientBoostingClassifier`; persist with joblib; serve via `GET /students/{id}/risk-score`.
  Train in a new `dag_train_model` (weekly).
- **Difficulty:** Hard · **Est.:** 4–5 d · **Impact:** Very high portfolio; needs real history to be honest.

### 2.2 Grade prediction from early-semester behavior
- **What:** regress final grade on first-N-weeks indicators.
- **Why:** enables early intervention before grades are final.
- **Sketch:** `src/sla/ml/grade.py`, features = early-window aggregates, target =
  `fact_assignment_submissions.grade`. Report MAE + feature importances for explainability.
- **Difficulty:** Hard · **Est.:** 3–4 d · **Impact:** High; pairs well with §2.1.

### 2.3 Anomaly detection for sudden engagement drops
- **What:** flag students whose engagement drops > k·σ vs their own rolling baseline.
- **Why:** catches acute problems (illness, disengagement) the static `at_risk_flag` misses.
- **Sketch:** rolling z-score on `indicator_history`; emit events that **n8n workflow 1**
  consumes for alerting. Pure NumPy — no model to train.
- **Difficulty:** Medium · **Est.:** 1.5 d · **Impact:** High; ties ML to the existing alert pipeline.

### 2.4 Clustering students by learning pattern
- **What:** KMeans/HDBSCAN over normalized indicators → persona labels ("crammer", "steady", "night-owl").
- **Why:** powers peer comparison (§1.3) and cohort dashboards.
- **Sketch:** `src/sla/ml/clusters.py`; reuse `normalizeIndicators` logic server-side; store
  `cluster_label` on `student_indicators`; color the engagement histogram by cluster.
- **Difficulty:** Medium · **Est.:** 2 d · **Impact:** Medium-high; visually compelling.

## 3. AI & RAG Enhancements

### 3.1 Hybrid search + reranking
- **What:** combine BM25/keyword + vector retrieval, then cross-encoder rerank the top-k.
- **Why:** pedagogy passages are short; pure embeddings miss exact-term matches. Better grounding.
- **Sketch:** in `src/sla/rag/retrieve.py` add a keyword index alongside Chroma; rerank with a
  small cross-encoder (or an LLM-as-reranker when a key is set). Keep the mock path deterministic.
- **Difficulty:** Medium · **Est.:** 2–3 d · **Impact:** High; demonstrates real RAG depth.

### 3.2 Feedback history as context
- **What:** feed the last N feedbacks (now stored in `analytics.feedback_log`) into the prompt.
- **Why:** avoids repetition, lets feedback reference prior advice — feels coherent over time.
- **Sketch:** read recent `feedback_log` rows in `src/sla/rag/service.py`, add to `StudentProfile`;
  the audit table from this round already exists.
- **Difficulty:** Easy · **Est.:** 1 d · **Impact:** Medium-high; cheap given the table exists.

### 3.3 Multi-language feedback
- **What:** generate feedback in the student's preferred language.
- **Why:** the project is hosted at a German university — direct real-world relevance.
- **Sketch:** add `language` to `dim_students`; pass into the prompt template; mock provider
  returns a canned translation for offline tests.
- **Difficulty:** Easy · **Est.:** 0.5 d · **Impact:** Medium; strong domain fit.

### 3.4 Teacher-facing "why this feedback" explanation
- **What:** surface which indicators + which retrieved passages drove each paragraph.
- **Why:** trust and the human-in-the-loop review (n8n workflow 4) need explainability.
- **Sketch:** the API already returns `context[]`; extend `generate.py` to tag each paragraph with
  the indicators it addresses; render in `frontend/components/feedback-panel.tsx`.
- **Difficulty:** Medium · **Est.:** 1.5 d · **Impact:** High; pairs with the review workflow.

### 3.5 Feedback effectiveness tracking
- **What:** measure whether indicators improved after feedback was delivered.
- **Why:** closes the loop — proves the system actually helps.
- **Sketch:** join `feedback_log.created_at` against subsequent `indicator_history`; report
  uplift; A/B feedback vs no-feedback cohorts.
- **Difficulty:** Hard · **Est.:** 3 d · **Impact:** Very high; rare and impressive.

## 4. Data Pipeline & Quality

### 4.1 Real LMS integration (Moodle / Canvas)
- **What:** replace the Faker simulation with a real Moodle REST / Canvas LTI source.
- **Why:** the single biggest credibility jump — real data, real value.
- **Sketch:** new `src/sla/etl/sources/moodle.py` implementing the same interface
  `src/sla/etl/ingest.py` expects; keep Faker as a fallback/`SLA_SOURCE=sim`.
- **Difficulty:** Hard · **Est.:** 5+ d · **Impact:** Very high; production-defining.

### 4.2 dbt for SQL transformations
- **What:** move the raw SQL in `dags/dag_transform.py` into dbt models with tests + lineage.
- **Why:** versioned, testable, documented transforms; industry-standard.
- **Sketch:** `dbt/` project (`staging_*` → `core_*` models); replace the transform task with
  `BashOperator: dbt run`; dbt tests cover not-null/unique/relationships.
- **Difficulty:** Medium · **Est.:** 3 d · **Impact:** High; recognizable signal to data employers.

### 4.3 Great Expectations on the staging layer
- **What:** declarative expectation suites complementing `src/sla/dq/checks.py`.
- **Why:** richer checks (distributions, value sets) + auto-generated Data Docs.
- **Sketch:** GE suite per staging table, run as a task between ingest and transform; fail the DAG
  on a critical breach; publish Data Docs as an artifact.
- **Difficulty:** Medium · **Est.:** 2 d · **Impact:** Medium-high; hardens an existing strength.

### 4.4 Slowly Changing Dimensions (SCD Type 2)
- **What:** track changes to `dim_students` (program switch, name) with validity ranges.
- **Why:** correct historical analytics; enables velocity/history features (§1.2, §2).
- **Sketch:** add `valid_from/valid_to/is_current` to `core.dim_students`; upsert logic in
  `src/sla/db.py` (extend `upsert`); update `sql/01_schema.sql`.
- **Difficulty:** Medium · **Est.:** 2 d · **Impact:** Medium; foundational for time-series work.

## 5. Backend & API

### 5.1 JWT auth with roles (teacher / student / admin)
- **What:** authenticate requests; scope data (students see only themselves).
- **Why:** real student data is sensitive (GDPR); table-stakes for production.
- **Sketch:** `src/sla/api/auth.py` (OAuth2 password + JWT), FastAPI dependency `require_role`;
  protect `/students/*`. Students get a filtered `/me` view.
- **Difficulty:** Medium · **Est.:** 2–3 d · **Impact:** High; required before any real deployment.

### 5.2 Pagination on `GET /students`
- **What:** `?limit&offset` (or cursor) + total count header.
- **Why:** the current full-cohort fetch won't scale; the dashboard already loads everything once.
- **Sketch:** params in `src/sla/api/main.py`, `LIMIT/OFFSET` in `StudentRepository.list_students`;
  update `frontend/lib/api.ts` + the table to page.
- **Difficulty:** Easy · **Est.:** 0.5 d · **Impact:** Medium; obvious scalability fix.

### 5.3 WebSocket for real-time indicator updates
- **What:** push updates to the dashboard when `dag_indicators` finishes.
- **Why:** live dashboards feel premium; removes manual refresh.
- **Sketch:** FastAPI WebSocket endpoint; n8n workflow 3's "refresh" step posts an event the API
  fans out; frontend subscribes and revalidates.
- **Difficulty:** Medium · **Est.:** 2 d · **Impact:** Medium; great demo factor.

### 5.4 GraphQL layer
- **What:** a `/graphql` endpoint (Strawberry) for flexible dashboard queries.
- **Why:** lets the frontend fetch exactly what each view needs in one round-trip.
- **Sketch:** Strawberry schema mirroring the Pydantic models; resolvers reuse `StudentRepository`.
- **Difficulty:** Medium · **Est.:** 2–3 d · **Impact:** Medium; nice-to-have vs REST.

### 5.5 Rate limiting & API keys
- **What:** per-key quotas, especially on the LLM-backed `/feedback` route.
- **Why:** `/feedback` costs real money; protect against abuse/runaway loops.
- **Sketch:** `slowapi` middleware; API-key table; tighter limit on feedback endpoints.
- **Difficulty:** Easy · **Est.:** 1 d · **Impact:** Medium; protects cost.

## 6. Observability & Monitoring

### 6.1 Prometheus metrics + `/metrics`
- **What:** request counts, latency histograms, feedback-generation duration, LLM provider in use.
- **Why:** instant production credibility; foundation for alerting.
- **Sketch:** `prometheus-fastapi-instrumentator` in `src/sla/api/main.py`; scrape config in compose.
- **Difficulty:** Easy · **Est.:** 0.5 d · **Impact:** High signal per effort.

### 6.2 Grafana dashboards
- **What:** panels for API latency, DAG durations, DQ pass rates, feedback throughput.
- **Why:** single pane of glass; pairs with §6.1.
- **Sketch:** add `prometheus` + `grafana` services; provision dashboards as JSON in `monitoring/`.
- **Difficulty:** Medium · **Est.:** 2 d · **Impact:** High visual impact.

### 6.3 Structured logging (structlog)
- **What:** JSON logs with request IDs across API + DAGs.
- **Why:** the current `logging.getLogger` calls are unstructured; hard to query.
- **Sketch:** central `src/sla/logging.py` configuring structlog; bind request IDs via middleware.
- **Difficulty:** Easy · **Est.:** 0.5 d · **Impact:** Medium; quality-of-life.

### 6.4 Airflow SLA-miss alerts via n8n
- **What:** route Airflow SLA misses to Slack through n8n.
- **Why:** reuses the automation layer built this round; closes the ops loop.
- **Sketch:** Airflow `sla_miss_callback` → POST the pipeline-monitor webhook (workflow 3) → Slack.
- **Difficulty:** Easy · **Est.:** 0.5 d · **Impact:** Medium; good integration story.

### 6.5 ChromaDB query performance monitoring
- **What:** time + log retrieval latency and top-k hit quality.
- **Why:** RAG quality silently degrades; measure it.
- **Sketch:** wrap calls in `src/sla/rag/retrieve.py` with timing → Prometheus histogram (§6.1).
- **Difficulty:** Easy · **Est.:** 0.5 d · **Impact:** Medium.

## 7. Infrastructure & Deployment

### 7.1 Kubernetes Helm chart
- **What:** Helm chart deploying the full stack to a cluster.
- **Why:** demonstrates production deployment skills beyond Compose.
- **Sketch:** `deploy/helm/` with templates per service, values per env, secrets via Secret objects.
- **Difficulty:** Hard · **Est.:** 4 d · **Impact:** High portfolio; over-kill for local.

### 7.2 Dev / staging / prod environments
- **What:** environment-specific config + compose/Helm overlays.
- **Why:** safe promotion path; config already env-driven via `src/sla/config.py`.
- **Sketch:** `.env.{dev,staging,prod}` + `docker-compose.override.yml`; document promotion.
- **Difficulty:** Easy · **Est.:** 1 d · **Impact:** Medium.

### 7.3 DVC for data versioning
- **What:** version `data/raw` and model artifacts.
- **Why:** reproducibility for the ML work (§2); track dataset drift.
- **Sketch:** `dvc init`, track `data/`, remote on S3/GDrive; wire into CI.
- **Difficulty:** Medium · **Est.:** 1.5 d · **Impact:** Medium; shines once ML lands.

### 7.4 Terraform for cloud infra
- **What:** IaC for managed Postgres + container hosting (AWS RDS + ECS, or GKE).
- **Why:** the "I can ship this for real" capstone.
- **Sketch:** `deploy/terraform/` modules: VPC, RDS, ECS services/Fargate, ALB, secrets.
- **Difficulty:** Hard · **Est.:** 5+ d · **Impact:** Very high portfolio; significant effort.

## 8. Testing

### 8.1 Playwright e2e for the Next.js dashboard
- **What:** browser tests for the 4 pages incl. the API-unreachable degraded state.
- **Why:** protects the UI built this round; covers the graceful-degradation requirement.
- **Sketch:** `frontend/e2e/` with mocked API responses; run headless in CI.
- **Difficulty:** Medium · **Est.:** 2 d · **Impact:** High; guards the headline feature.

### 8.2 Contract tests (Pact) between API and frontend
- **What:** consumer-driven contracts so schema drift breaks CI, not prod.
- **Why:** `frontend/lib/types.ts` mirrors `schemas.py` by hand today — fragile.
- **Sketch:** Pact consumer tests in frontend, provider verification against FastAPI in CI.
- **Difficulty:** Medium · **Est.:** 2 d · **Impact:** Medium-high; prevents a whole bug class.

### 8.3 Load testing with Locust
- **What:** load profiles for `/students` and the costly `/feedback`.
- **Why:** find the breaking point before users do; justifies pagination/rate-limiting.
- **Sketch:** `tests/load/locustfile.py`; document p95 latency vs concurrency.
- **Difficulty:** Easy · **Est.:** 1 d · **Impact:** Medium.

### 8.4 n8n workflow tests with mock HTTP
- **What:** run workflows against a stubbed API (WireMock/Prism) and assert side effects.
- **Why:** workflows are real code now; regressions are silent otherwise.
- **Sketch:** spin n8n + a mock API in CI; trigger via the webhook URLs; assert DB rows / mock hits.
- **Difficulty:** Medium · **Est.:** 2 d · **Impact:** Medium; matches the new automation layer.

### 8.5 Mutation testing for indicator functions
- **What:** `mutmut`/`cosmic-ray` on `src/sla/indicators/compute.py`.
- **Why:** the indicators are the analytical core; verify the tests actually catch bugs.
- **Sketch:** add `mutmut` config scoped to `indicators/`; track the mutation score in CI.
- **Difficulty:** Easy · **Est.:** 1 d · **Impact:** Medium; deepens an existing test strength.

---

### Suggested sequencing
1. **Foundations:** §1.2 indicator history + §4.4 SCD2 → unlocks the time-series ML.
2. **Predictive headline:** §2.1 dropout + §2.3 anomaly (wires into n8n alerts).
3. **Production polish:** §5.1 auth, §5.2 pagination, §6.1–6.2 observability.
4. **Credibility:** §4.1 real LMS, §4.2 dbt, §8.1 Playwright.
