"""Reusable data-quality checks.

Each check returns a list of :class:`Violation` objects (never raises), so the
caller decides whether a violation is fatal. :func:`validate` aggregates a set
of checks for one table into a :class:`DQReport`; the DAGs call
``report.raise_for_status()`` to fail a task on bad data.

Checks cover the three failure modes the project must catch:
* **missing values** — :func:`check_not_null`
* **out-of-range values** — :func:`check_range` (e.g. scores outside 0–100)
* **duplicate records** — :func:`check_unique`

plus referential integrity via :func:`check_foreign_key`.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

import pandas as pd


class DataQualityError(RuntimeError):
    """Raised when a :class:`DQReport` contains blocking violations."""


@dataclass(frozen=True)
class Violation:
    """A single failed data-quality expectation."""

    check: str
    table: str
    column: str
    detail: str
    count: int

    def __str__(self) -> str:
        return (
            f"[{self.check}] {self.table}.{self.column}: {self.detail} "
            f"({self.count} row(s))"
        )


@dataclass
class DQReport:
    """Aggregated result of validating one table."""

    table: str
    rows: int
    violations: list[Violation] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when no violations were recorded."""
        return not self.violations

    def extend(self, violations: Iterable[Violation]) -> None:
        """Append violations from a check."""
        self.violations.extend(violations)

    def summary(self) -> str:
        """Human-readable one-liner for logging."""
        status = "PASS" if self.ok else f"FAIL ({len(self.violations)})"
        return f"DQ {self.table}: {status}, {self.rows} rows"

    def raise_for_status(self) -> None:
        """Raise :class:`DataQualityError` if any violation exists."""
        if not self.ok:
            details = "\n  - ".join(str(v) for v in self.violations)
            raise DataQualityError(f"Data quality failed for {self.table}:\n  - {details}")


# --- individual checks -----------------------------------------------------


def check_not_null(df: pd.DataFrame, table: str, columns: Sequence[str]) -> list[Violation]:
    """Flag columns containing null/NaN values."""
    out: list[Violation] = []
    for col in columns:
        n = int(df[col].isna().sum())
        if n:
            out.append(Violation("not_null", table, col, "missing values", n))
    return out


def check_range(
    df: pd.DataFrame,
    table: str,
    column: str,
    low: float,
    high: float,
    *,
    inclusive: bool = True,
) -> list[Violation]:
    """Flag numeric values falling outside ``[low, high]`` (nulls ignored)."""
    series = pd.to_numeric(df[column], errors="coerce").dropna()
    if inclusive:
        bad = series[(series < low) | (series > high)]
    else:
        bad = series[(series <= low) | (series >= high)]
    if len(bad):
        return [
            Violation(
                "range", table, column,
                f"values outside [{low}, {high}]", int(len(bad)),
            )
        ]
    return []


def check_unique(df: pd.DataFrame, table: str, columns: Sequence[str]) -> list[Violation]:
    """Flag duplicate records over the given key columns."""
    dupes = df.duplicated(subset=list(columns), keep=False)
    n = int(dupes.sum())
    if n:
        key = ", ".join(columns)
        return [Violation("unique", table, key, "duplicate records", n)]
    return []


def check_foreign_key(
    df: pd.DataFrame,
    table: str,
    column: str,
    valid_values: Iterable,
    *,
    ref: str = "",
) -> list[Violation]:
    """Flag values in ``column`` not present in ``valid_values`` (nulls ignored)."""
    valid = set(valid_values)
    present = df[column].dropna()
    orphan = present[~present.isin(valid)]
    if len(orphan):
        detail = f"orphan references{f' to {ref}' if ref else ''}"
        return [Violation("foreign_key", table, column, detail, int(len(orphan)))]
    return []


# --- aggregator ------------------------------------------------------------


def validate(
    df: pd.DataFrame,
    table: str,
    *,
    not_null: Sequence[str] | None = None,
    unique: Sequence[str] | None = None,
    ranges: dict[str, tuple[float, float]] | None = None,
    foreign_keys: dict[str, tuple[Iterable, str]] | None = None,
) -> DQReport:
    """Run a declarative set of checks against ``df`` and collect a report.

    Parameters mirror the failure modes:
        not_null:     columns that must not contain nulls
        unique:       key columns that together must be unique
        ranges:       ``{column: (low, high)}`` numeric bounds (inclusive)
        foreign_keys: ``{column: (valid_values, ref_name)}``
    """
    report = DQReport(table=table, rows=len(df))
    if not_null:
        report.extend(check_not_null(df, table, not_null))
    if unique:
        report.extend(check_unique(df, table, unique))
    if ranges:
        for col, (low, high) in ranges.items():
            report.extend(check_range(df, table, col, low, high))
    if foreign_keys:
        for col, (valid, ref) in foreign_keys.items():
            report.extend(check_foreign_key(df, table, col, valid, ref=ref))
    return report
