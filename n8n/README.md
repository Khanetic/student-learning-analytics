# n8n Workflow Automation

n8n is the **event-driven automation** layer that sits alongside Airflow.

| Layer | Responsibility |
|-------|----------------|
| **Airflow** | Heavy ETL, SQL pipelines, DAG dependencies (`dag_ingest → dag_transform → dag_indicators`) |
| **n8n** | Notifications, API orchestration, AI-feedback delivery, human-in-the-loop review, onboarding |

n8n runs as a Docker Compose service on **http://localhost:5678**. For local dev the owner
login is disabled (`N8N_USER_MANAGEMENT_DISABLED=true` in `docker-compose.yml`), so the editor
opens straight away — no email/password. Workflow files are mounted read-only at `/workflows`
inside the container.

> n8n only shows workflows that live in **its own database** (the `n8n-data` volume). The JSON
> files in this repo are just files on disk — n8n does **not** auto-read them. Import them once
> (below).

## Importing credentials + workflows

`docker compose up -d` brings up n8n **and** Mailhog (local SMTP sink). Then import the two
shared credentials first, then the workflows. The `/workflows` mount is read-only, so copy the
credential file in via that mount (or use `docker cp`):

```bash
cp n8n/credentials.example.json n8n/workflows/_creds.json
docker exec student-learning-analytics-n8n-1 \
  n8n import:credentials --input=/workflows/_creds.json
rm n8n/workflows/_creds.json

docker exec student-learning-analytics-n8n-1 \
  n8n import:workflow --separate --input=/workflows
```

`credentials.example.json` defines two credentials with fixed ids the workflows reference, so the
email + Postgres nodes come **pre-wired** (no red triangles):
- **Mailhog SMTP** (`smtp`) → host `mailhog`, port `1025`, no auth → inbox at http://localhost:8025
- **SLA Postgres** (`postgres`) → host `postgres`, db `sla`, user `sla`

Refresh http://localhost:5678 → all workflows appear under **Workflows**. (UI alternative:
**Workflows → Import from File**, then attach credentials per node manually.)

> **Swap Mailhog for a real provider:** edit the **Mailhog SMTP** credential in the n8n UI —
> e.g. Gmail host `smtp.gmail.com`, port `587`, your address + a Google **App Password**.

Finally, **toggle each workflow Active** (top-right in the editor) to enable its schedule/webhook
triggers — all ship `active: false`, and **production webhooks only register on UI activation**.

> All workflows reach the API over the Docker network at `http://api:8001` and Postgres at
> `postgres:5432`. Webhook URLs are built from `WEBHOOK_URL` (default `http://localhost:5678`).

### Re-importing cleanly

`import:workflow` appends, so importing twice creates duplicates. To reset, wipe the volume:

```bash
docker compose rm -sf n8n
docker volume rm student-learning-analytics_n8n-data
docker compose up -d n8n
docker exec student-learning-analytics-n8n-1 n8n import:workflow --separate --input=/workflows
```

## Required environment variables (`.env`)

```
WEBHOOK_URL=http://localhost:5678
N8N_USER_MANAGEMENT_DISABLED=true   # skip the owner login (local dev)
SMTP_FROM=learning-analytics@example.com   # From address ($env.SMTP_FROM in email nodes)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...   # Slack nodes POST here
```

> The SMTP **server** (host/port/user/pass) and the Postgres connection live in n8n
> **credentials** (see `credentials.example.json`), not in `.env`. Only `SMTP_FROM` and
> `SLACK_WEBHOOK_URL` are read from the environment by the workflows (`$env.*`), and both are
> passed into the n8n container in `docker-compose.yml`.

The Postgres nodes use the **SLA Postgres** credential (host `postgres`, db `sla`, user `sla`),
imported from `credentials.example.json`.

---

## Workflows

### 1. At-Risk Student Alert — `01_at_risk_alert.json`
- **Trigger:** schedule, daily 08:00 (`0 8 * * *`).
- **Flow:** `GET /students/at-risk` → diff against last run (workflow static data) → if new
  at-risk students: email teacher (SMTP) + post to Slack `#at-risk-alerts` → insert a row into
  `analytics.feedback_log` (Postgres node).
- **Integrates with:** `GET /students/at-risk`, `analytics.feedback_log`, SMTP, Slack.
- **Test manually:** open the workflow → **Execute Workflow**. Seed an at-risk student by running
  the indicators DAG, or temporarily clear the workflow's static data to treat all as "new".

### 2. Weekly Feedback Delivery — `02_weekly_feedback.json`
- **Trigger:** schedule, Mondays 09:00 (`0 9 * * 1`).
- **Flow:** `GET /students` → loop each → `GET /students/{id}/feedback` (RAG) → email student →
  `POST /students/{id}/feedback/log` → Slack `#weekly-feedback` summary.
- **Integrates with:** `GET /students`, `/students/{id}/feedback`, `/students/{id}/feedback/log`, SMTP, Slack.
- **Test manually:** **Execute Workflow**. With no `OPENAI_API_KEY` the API uses the deterministic
  mock provider, so feedback still generates offline.

### 3. Airflow Pipeline Trigger & Monitor — `03_pipeline_trigger_monitor.json`
- **Trigger:** schedule daily 02:00 **or** webhook `POST /webhook/run-pipeline`.
- **Flow:** `POST /pipeline/trigger {dag_ingest}` → wait 30s → poll `GET /pipeline/status/dag_ingest`
  → on `success` chain `dag_transform` then `dag_indicators`; on `failed` Slack alert; otherwise
  loop back and keep polling.
- **Integrates with:** `POST /pipeline/trigger`, `GET /pipeline/status/{dag_id}` (Airflow REST passthrough), Slack.
- **Test manually:**
  ```bash
  curl -X POST http://localhost:5678/webhook/run-pipeline
  ```

### 4. Teacher Feedback Review (Human-in-the-Loop) — `04_teacher_review.json`
- **Trigger A:** webhook `POST /webhook/request-review` (from the dashboard "Request Review" button).
- **Flow A:** `GET /students/{id}/feedback` → post Slack interactive message with
  Approve / Edit / Reject buttons.
- **Trigger B:** webhook `POST /webhook/review-action` (Slack interactivity / a form posts the decision back).
- **Flow B:** switch on `decision` → Approve → email student; Edit → email edited text; Reject → log only.
  All branches `POST /students/{id}/feedback/log` with status `approved|edited|rejected` for the audit trail.
- **Integrates with:** `/students/{id}/feedback`, `/students/{id}/feedback/log`, Slack, SMTP.
- **Test manually:**
  ```bash
  # 1) request a review
  curl -X POST http://localhost:5678/webhook/request-review \
    -H 'Content-Type: application/json' -d '{"student_id":"S0001"}'

  # 2) simulate the teacher's decision
  curl -X POST http://localhost:5678/webhook/review-action \
    -H 'Content-Type: application/json' \
    -d '{"student_id":"S0001","decision":"approve","feedback_text":"Great progress!"}'
  ```
  > Real Slack buttons need a Slack app with interactivity pointing at the `review-action` webhook;
  > the second `curl` stands in for that callback during local testing.

### 5. New Student Onboarding — `05_new_student_onboarding.json`
- **Trigger:** webhook `POST /webhook/new-students` (called by `dag_ingest` when new students are detected).
- **Flow:** query `core.dim_students` for recent enrollments → loop → welcome email → notify teacher
  (Slack; swap for a Trello/Notion node) → wait 2 weeks → generate first feedback via RAG.
- **Integrates with:** `core.dim_students` (Postgres), `/students/{id}/feedback`, SMTP, Slack.
- **Test manually:**
  ```bash
  curl -X POST http://localhost:5678/webhook/new-students -d '{}'
  ```

---

## Webhook paths: test vs live
n8n exposes two URLs per webhook:
- **`/webhook-test/<path>`** — fires once while the editor is open and you've clicked
  **Listen for test event**. Use this to try a webhook workflow without activating it.
- **`/webhook/<path>`** — the production URL, live only when the workflow is **Active**.

The `curl` commands above use `/webhook/...` (assumes the workflow is Active). For a quick
one-off test, swap in `/webhook-test/...` and arm the trigger in the UI first.

> **Production webhooks must be activated from the UI.** Toggling **Active** via the CLI
> (`n8n update:workflow --active=true`) sets the flag but does **not** register the
> `/webhook/<path>` route — those `curl`s will 404. Open the workflow in the editor and flip the
> **Active** toggle (top-right) to register the production webhook. For a one-off test without
> activating, use the `/webhook-test/<path>` URL with **Listen for test event** armed.

## Quick verify (no credentials needed)
`00_smoke_test.json` is a manual-trigger health check: **GET /students/at-risk → POST
/students/{id}/feedback/log** for each. It needs no SMTP/Slack and can be run head-less:

```bash
docker exec student-learning-analytics-n8n-1 \
  n8n import:workflow --input=/workflows/00_smoke_test.json   # wrap in [ ] if importing one file
# find its id, then:
docker exec student-learning-analytics-n8n-1 n8n execute --id <SMOKE_ID>
```

Confirm the side effect (rows written through n8n → API → Postgres):
```sql
SELECT count(*) FROM analytics.feedback_log WHERE note = 'smoke-test via n8n';
```
> `n8n execute` only works on workflows with a **Manual / Execute-Workflow trigger** (like the
> smoke test). Schedule/webhook-triggered workflows are run via their trigger, not `execute`.

## Running without external credentials
With no SMTP / Slack creds configured, the HTTP-request, Code, IF/Switch, Wait and Postgres
nodes still run — only the **Email** and **Slack** delivery nodes error. Workflow **03 (Pipeline
Trigger & Monitor)** is pure HTTP on its happy path, so it executes end-to-end with no creds.

## Notes
- All workflows are imported **inactive**; enable schedules deliberately.
- `n8n-data` named volume persists workflows, credentials, and execution history.
- For local email testing, add a [Mailhog](https://github.com/mailhog/MailHog) service and point
  `SMTP_HOST=mailhog`, `SMTP_PORT=1025`.
