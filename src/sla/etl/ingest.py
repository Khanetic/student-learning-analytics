"""Ingest stage: raw files -> validate -> staging tables.

Idempotent by construction — staging tables are truncated and reloaded, so
re-running the ingest DAG produces the same result.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from sla.config import get_settings
from sla.db import load_staging
from sla.dq import validate
from sla.etl.spec import SPEC_BY_NAME, TableSpec

log = logging.getLogger(__name__)


def read_raw(spec: TableSpec, raw_dir: Path) -> pd.DataFrame:
    """Read a raw CSV for ``spec``, parsing declared date columns."""
    path = raw_dir / f"{spec.name}.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"Raw file missing: {path}. Run `python -m sla.simulate.generate` first."
        )
    return pd.read_csv(path, parse_dates=list(spec.date_cols))


def validate_raw(spec: TableSpec, df: pd.DataFrame):
    """Run ingest-time data-quality checks (missing, range, duplicate)."""
    return validate(
        df,
        spec.name,
        not_null=spec.not_null or None,
        unique=spec.pk or None,
        ranges=spec.ranges or None,
    )


def ingest_table(name: str, raw_dir: Path | None = None) -> int:
    """Read, validate and stage a single table. Raises on data-quality failure."""
    spec = SPEC_BY_NAME[name]
    raw_dir = raw_dir or get_settings().raw_dir
    df = read_raw(spec, raw_dir)

    report = validate_raw(spec, df)
    log.info(report.summary())
    report.raise_for_status()

    rows = load_staging(df, spec.name)
    log.info("Staged %s rows into staging.%s", rows, spec.name)
    return rows
