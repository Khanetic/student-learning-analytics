# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# FastAPI backend image (Phase 4).
# Installs the `sla` package with the api + rag + db extras. The package is
# installed editable and the repo is mounted at /app by compose, so code and
# pedagogy edits are picked up without a rebuild.
# ---------------------------------------------------------------------------
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first (better layer caching).
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --upgrade pip && pip install -e ".[api,rag,db]"

# Copy the rest (pedagogy docs, sql, etc.).
COPY . .

EXPOSE 8001
CMD ["uvicorn", "sla.api.main:app", "--host", "0.0.0.0", "--port", "8001"]
