"""Data quality layer (Phase 2).

Pure, framework-free validation functions over pandas DataFrames so they are
trivially unit-testable and reused by the ingest and transform DAGs.
"""

from sla.dq.checks import (
    DataQualityError,
    DQReport,
    Violation,
    check_foreign_key,
    check_not_null,
    check_range,
    check_unique,
    validate,
)

__all__ = [
    "DataQualityError",
    "DQReport",
    "Violation",
    "check_foreign_key",
    "check_not_null",
    "check_range",
    "check_unique",
    "validate",
]
