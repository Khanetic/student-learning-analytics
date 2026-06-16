"""Database access helpers (PostgreSQL via SQLAlchemy).

A thin, dependency-light wrapper used by the Airflow DAGs and the FastAPI
backend so connection handling, staging loads and idempotent upserts live in
one place. Connection details come from :mod:`sla.config` (environment-driven)
— never hardcoded.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from functools import lru_cache
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

# Import Engine from sqlalchemy.engine so this works on both SQLAlchemy 1.4
# (shipped with Airflow 2.9) and 2.0 (used locally / by the API service).
from sqlalchemy.engine import Engine

from sla.config import get_settings

STAGING_SCHEMA = "staging"
CORE_SCHEMA = "core"
ANALYTICS_SCHEMA = "analytics"


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Return a cached SQLAlchemy engine for the application database."""
    settings = get_settings()
    return create_engine(settings.database_url, pool_pre_ping=True, future=True)


def exec_sql(sql: str, params: dict | None = None) -> None:
    """Execute a single statement (or batch) in its own transaction."""
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(sql), params or {})


def _split_statements(sql: str) -> list[str]:
    """Split a SQL script into executable statements.

    Strips ``--`` line comments first so a semicolon appearing inside a comment
    cannot break statement splitting, then splits on semicolons and drops empty
    fragments. (The project's DDL contains no ``--`` inside string literals.)
    """
    no_comments = []
    for line in sql.splitlines():
        idx = line.find("--")
        no_comments.append(line if idx == -1 else line[:idx])
    cleaned = "\n".join(no_comments)
    return [s.strip() for s in cleaned.split(";") if s.strip()]


def run_sql_file(path: str | Path) -> None:
    """Run every statement in a ``.sql`` file."""
    sql = Path(path).read_text(encoding="utf-8")
    engine = get_engine()
    with engine.begin() as conn:
        for stmt in _split_statements(sql):
            conn.execute(text(stmt))


def fetch_df(sql: str, params: dict | None = None) -> pd.DataFrame:
    """Run a query and return the result as a DataFrame."""
    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})


def load_staging(df: pd.DataFrame, table: str) -> int:
    """Replace ``staging.<table>`` with the contents of ``df`` (idempotent).

    Truncate-and-reload makes re-running an ingest safe.
    """
    engine = get_engine()
    df.to_sql(
        table,
        engine,
        schema=STAGING_SCHEMA,
        if_exists="replace",
        index=False,
        method="multi",
        chunksize=1000,
    )
    return len(df)


def upsert(
    df: pd.DataFrame,
    schema: str,
    table: str,
    conflict_cols: Sequence[str],
    update_cols: Iterable[str] | None = None,
) -> int:
    """Idempotently upsert ``df`` into ``schema.table`` via ``ON CONFLICT``.

    Rows are staged into a temporary table, then inserted into the target with
    ``ON CONFLICT (conflict_cols) DO UPDATE``. Re-running with the same data is
    a no-op, satisfying the DAG idempotency requirement.

    Returns the number of rows processed.
    """
    if df.empty:
        return 0

    cols = list(df.columns)
    update_cols = list(update_cols) if update_cols is not None else [
        c for c in cols if c not in conflict_cols
    ]
    tmp = f"_tmp_{table}"
    engine = get_engine()

    col_list = ", ".join(f'"{c}"' for c in cols)
    conflict_list = ", ".join(f'"{c}"' for c in conflict_cols)

    with engine.begin() as conn:
        # Stage into a transaction-local temp table mirroring the frame.
        df.to_sql(tmp, conn, if_exists="replace", index=False,
                  method="multi", chunksize=1000)
        if update_cols:
            set_clause = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in update_cols)
            on_conflict = f"DO UPDATE SET {set_clause}"
        else:
            on_conflict = "DO NOTHING"
        conn.execute(
            text(
                f'INSERT INTO "{schema}"."{table}" ({col_list}) '
                f"SELECT {col_list} FROM \"{tmp}\" "
                f"ON CONFLICT ({conflict_list}) {on_conflict}"
            )
        )
        conn.execute(text(f'DROP TABLE IF EXISTS "{tmp}"'))
    return len(df)


def table_count(schema: str, table: str) -> int:
    """Return the row count of ``schema.table`` (0 if it does not exist)."""
    try:
        return int(fetch_df(f'SELECT COUNT(*) AS n FROM "{schema}"."{table}"')["n"].iloc[0])
    except Exception:
        return 0
