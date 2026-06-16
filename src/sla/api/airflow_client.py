"""Thin client for the Airflow stable REST API.

Used by the ``/pipeline/*`` endpoints so n8n (and other automation) can trigger
and monitor the ETL DAGs through the API instead of talking to Airflow
directly. Connection + credentials come from :mod:`sla.config` — never
hardcoded. Errors are surfaced as :class:`AirflowError` for the API layer to
translate into HTTP responses.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from sla.config import get_settings

log = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(10.0)


class AirflowError(RuntimeError):
    """Raised when the Airflow REST API is unreachable or returns an error."""


def _client() -> httpx.Client:
    settings = get_settings()
    return httpx.Client(
        base_url=settings.airflow_api_url.rstrip("/"),
        auth=(settings.airflow_admin_user, settings.airflow_admin_password),
        timeout=_TIMEOUT,
        headers={"Content-Type": "application/json"},
    )


def trigger_dag(dag_id: str, conf: dict[str, Any] | None = None) -> dict[str, Any]:
    """Trigger a new DAG run and return the created run record."""
    try:
        with _client() as client:
            resp = client.post(f"/dags/{dag_id}/dagRuns", json={"conf": conf or {}})
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        raise AirflowError(
            f"Airflow rejected trigger for '{dag_id}': "
            f"{exc.response.status_code} {exc.response.text}"
        ) from exc
    except httpx.HTTPError as exc:
        raise AirflowError(f"Airflow unreachable: {exc}") from exc


def latest_dag_run(dag_id: str) -> dict[str, Any] | None:
    """Return the most recent DAG run for ``dag_id`` (or None if there are none)."""
    try:
        with _client() as client:
            resp = client.get(
                f"/dags/{dag_id}/dagRuns",
                params={"order_by": "-execution_date", "limit": 1},
            )
            resp.raise_for_status()
            runs = resp.json().get("dag_runs", [])
            return runs[0] if runs else None
    except httpx.HTTPStatusError as exc:
        raise AirflowError(
            f"Airflow rejected status query for '{dag_id}': "
            f"{exc.response.status_code} {exc.response.text}"
        ) from exc
    except httpx.HTTPError as exc:
        raise AirflowError(f"Airflow unreachable: {exc}") from exc
