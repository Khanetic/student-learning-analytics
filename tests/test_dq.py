"""Phase 2 tests for the data-quality layer."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from sla.dq import (
    DataQualityError,
    check_foreign_key,
    check_not_null,
    check_range,
    check_unique,
    validate,
)


@pytest.fixture
def df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "id": [1, 2, 3, 4],
            "score": [10.0, 55.0, 105.0, np.nan],
            "course_id": ["C01", "C02", "C99", "C01"],
        }
    )


def test_check_not_null_flags_missing(df: pd.DataFrame) -> None:
    v = check_not_null(df, "t", ["score"])
    assert len(v) == 1 and v[0].count == 1
    assert check_not_null(df, "t", ["id"]) == []


def test_check_range_flags_out_of_bounds(df: pd.DataFrame) -> None:
    v = check_range(df, "t", "score", 0, 100)
    assert len(v) == 1 and v[0].count == 1  # 105 is out, NaN ignored
    assert check_range(df, "t", "score", 0, 200) == []


def test_check_unique_flags_duplicates() -> None:
    d = pd.DataFrame({"k": [1, 1, 2]})
    v = check_unique(d, "t", ["k"])
    assert len(v) == 1 and v[0].count == 2
    assert check_unique(d, "t", ["k"]) and not check_unique(
        pd.DataFrame({"k": [1, 2, 3]}), "t", ["k"]
    )


def test_check_foreign_key_flags_orphans(df: pd.DataFrame) -> None:
    valid = {"C01", "C02"}
    v = check_foreign_key(df, "t", "course_id", valid, ref="dim_courses")
    assert len(v) == 1 and v[0].count == 1  # C99 orphan
    assert check_foreign_key(df, "t", "course_id", {"C01", "C02", "C99"}) == []


def test_validate_aggregates_and_reports(df: pd.DataFrame) -> None:
    report = validate(
        df,
        "t",
        not_null=["score"],
        unique=["id"],
        ranges={"score": (0, 100)},
        foreign_keys={"course_id": ({"C01", "C02"}, "dim_courses")},
    )
    assert not report.ok
    # not_null(1) + range(1) + foreign_key(1) = 3 violations, id is unique.
    assert len(report.violations) == 3
    assert "FAIL" in report.summary()


def test_validate_passes_clean_data() -> None:
    clean = pd.DataFrame({"id": [1, 2], "score": [50.0, 75.0]})
    report = validate(clean, "t", not_null=["id", "score"], unique=["id"],
                      ranges={"score": (0, 100)})
    assert report.ok
    report.raise_for_status()  # must not raise


def test_raise_for_status_raises_on_failure(df: pd.DataFrame) -> None:
    report = validate(df, "t", ranges={"score": (0, 100)})
    with pytest.raises(DataQualityError):
        report.raise_for_status()
