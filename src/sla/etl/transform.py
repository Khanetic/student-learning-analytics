"""Transform stage: staging -> core star schema, with a data-quality gate.

For each table we read the staged frame, re-run quality checks *including*
referential integrity against the already-loaded core dimensions, then upsert
into ``core``. Upserts (``ON CONFLICT DO UPDATE``) keep the DAG idempotent.
"""

from __future__ import annotations

import logging

import pandas as pd

from sla.db import STAGING_SCHEMA, fetch_df, upsert
from sla.dq import validate
from sla.etl.spec import SPEC_BY_NAME, TableSpec

log = logging.getLogger(__name__)

CORE_SCHEMA = "core"


def _read_staging(name: str) -> pd.DataFrame:
    """Load a staged table back into a DataFrame."""
    return fetch_df(f'SELECT * FROM {STAGING_SCHEMA}."{name}"')


def _core_id_set(core_table: str) -> set:
    """Distinct primary-key values currently in a core dimension/fact."""
    pk = SPEC_BY_NAME[core_table].pk[0]
    return set(fetch_df(f'SELECT DISTINCT "{pk}" FROM {CORE_SCHEMA}."{core_table}"')[pk])


def transform_table(name: str) -> int:
    """Validate (incl. foreign keys) and upsert one staged table into core."""
    spec: TableSpec = SPEC_BY_NAME[name]
    df = _read_staging(name)

    foreign_keys = {
        col: (_core_id_set(ref_table), ref_table)
        for col, ref_table in spec.foreign_keys.items()
    }
    report = validate(
        df,
        spec.name,
        not_null=spec.not_null or None,
        unique=spec.pk or None,
        ranges=spec.ranges or None,
        foreign_keys=foreign_keys or None,
    )
    log.info(report.summary())
    report.raise_for_status()

    rows = upsert(df, CORE_SCHEMA, spec.name, conflict_cols=spec.pk)
    log.info("Upserted %s rows into core.%s", rows, spec.name)
    return rows
