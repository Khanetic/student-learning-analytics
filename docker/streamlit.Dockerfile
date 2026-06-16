# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# Streamlit dashboard image (Phase 5).
# Talks only to the FastAPI backend (API_BASE_URL); no database access.
# ---------------------------------------------------------------------------
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first for better layer caching.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --upgrade pip && pip install -e ".[dashboard]"

# Copy the dashboard (and the rest of the repo, also mounted by compose).
COPY . .

EXPOSE 8501
CMD ["streamlit", "run", "dashboard/Home.py", \
     "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
