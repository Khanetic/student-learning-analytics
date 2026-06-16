"""Declarative table specifications driving ingest and transform.

Keeping the contract for every table in one place means the ingest and
transform DAGs, the data-quality checks, and the star-schema loads all stay in
sync from a single source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TableSpec:
    """Everything the ETL needs to know about one table.

    Attributes:
        name:         table name (matches raw file stem and core/dim table).
        date_cols:    columns to parse as timestamps when reading raw CSV.
        pk:           primary-key columns (used for uniqueness + upsert conflict).
        not_null:     columns that must never be null.
        ranges:       ``{column: (low, high)}`` inclusive numeric bounds.
        foreign_keys: ``{column: core_table}`` referential checks (transform).
        is_dimension: dimensions load before facts.
    """

    name: str
    date_cols: tuple[str, ...] = ()
    pk: tuple[str, ...] = ()
    not_null: tuple[str, ...] = ()
    ranges: dict[str, tuple[float, float]] = field(default_factory=dict)
    foreign_keys: dict[str, str] = field(default_factory=dict)
    is_dimension: bool = False


# Ordered so dimensions precede facts (transform relies on this order for FK
# validation against already-loaded core dimensions).
TABLE_SPECS: tuple[TableSpec, ...] = (
    TableSpec(
        name="dim_students",
        date_cols=("enrollment_date",),
        pk=("student_id",),
        not_null=("student_id", "name", "program", "enrollment_date"),
        is_dimension=True,
    ),
    TableSpec(
        name="dim_courses",
        pk=("course_id",),
        not_null=("course_id", "course_code", "course_name", "credits"),
        ranges={"credits": (1, 60)},
        is_dimension=True,
    ),
    TableSpec(
        name="dim_resources",
        pk=("resource_id",),
        not_null=("resource_id", "course_id", "title", "resource_type"),
        foreign_keys={"course_id": "dim_courses"},
        is_dimension=True,
    ),
    TableSpec(
        name="fact_sessions",
        date_cols=("login_at", "logout_at"),
        pk=("session_id",),
        not_null=("session_id", "student_id", "login_at", "logout_at", "duration_minutes"),
        ranges={"duration_minutes": (0, 1440)},
        foreign_keys={"student_id": "dim_students"},
    ),
    TableSpec(
        name="fact_page_views",
        date_cols=("viewed_at",),
        pk=("page_view_id",),
        not_null=("page_view_id", "session_id", "student_id", "resource_id", "viewed_at"),
        ranges={"time_spent_seconds": (0, 36000)},
        foreign_keys={
            "student_id": "dim_students",
            "session_id": "fact_sessions",
            "resource_id": "dim_resources",
        },
    ),
    TableSpec(
        name="fact_quiz_attempts",
        date_cols=("submitted_at",),
        pk=("attempt_id",),
        not_null=("attempt_id", "student_id", "course_id", "quiz_id",
                  "attempt_number", "score", "submitted_at"),
        ranges={"score": (0, 100), "attempt_number": (1, 50)},
        foreign_keys={"student_id": "dim_students", "course_id": "dim_courses"},
    ),
    TableSpec(
        name="fact_assignment_submissions",
        date_cols=("due_at", "submitted_at"),
        pk=("submission_id",),
        not_null=("submission_id", "student_id", "course_id", "assignment_id", "due_at"),
        ranges={"grade": (0, 100)},
        foreign_keys={"student_id": "dim_students", "course_id": "dim_courses"},
    ),
)

SPEC_BY_NAME: dict[str, TableSpec] = {s.name: s for s in TABLE_SPECS}
DIMENSION_NAMES: tuple[str, ...] = tuple(s.name for s in TABLE_SPECS if s.is_dimension)
FACT_NAMES: tuple[str, ...] = tuple(s.name for s in TABLE_SPECS if not s.is_dimension)
