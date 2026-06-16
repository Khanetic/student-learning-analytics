"""Phase 1 tests for the simulated LMS data generator.

These guard the contract later phases rely on: stable row counts, referential
integrity between tables, value ranges, and full determinism.
"""

from __future__ import annotations

import pandas as pd

from sla.simulate.generate import SimConfig, generate_all, write_tables

EXPECTED_TABLES = {
    "dim_courses",
    "dim_resources",
    "dim_students",
    "fact_sessions",
    "fact_page_views",
    "fact_quiz_attempts",
    "fact_assignment_submissions",
}


def test_all_tables_present_and_non_empty(tables: dict[str, pd.DataFrame]) -> None:
    assert set(tables) == EXPECTED_TABLES
    for name, df in tables.items():
        assert len(df) > 0, f"{name} is empty"


def test_student_count_and_unique_ids(tables, sim_config: SimConfig) -> None:
    students = tables["dim_students"]
    assert len(students) == sim_config.n_students
    assert students["student_id"].is_unique
    assert students["program"].notna().all()
    assert students["enrollment_date"].notna().all()


def test_primary_keys_unique(tables) -> None:
    pk = {
        "dim_courses": "course_id",
        "dim_resources": "resource_id",
        "fact_sessions": "session_id",
        "fact_page_views": "page_view_id",
        "fact_quiz_attempts": "attempt_id",
        "fact_assignment_submissions": "submission_id",
    }
    for table, key in pk.items():
        assert tables[table][key].is_unique, f"{table}.{key} not unique"


def test_referential_integrity(tables) -> None:
    student_ids = set(tables["dim_students"]["student_id"])
    course_ids = set(tables["dim_courses"]["course_id"])
    resource_ids = set(tables["dim_resources"]["resource_id"])
    session_ids = set(tables["fact_sessions"]["session_id"])

    assert set(tables["fact_sessions"]["student_id"]) <= student_ids
    assert set(tables["fact_page_views"]["student_id"]) <= student_ids
    assert set(tables["fact_page_views"]["session_id"]) <= session_ids
    assert set(tables["fact_page_views"]["resource_id"]) <= resource_ids
    assert set(tables["fact_quiz_attempts"]["student_id"]) <= student_ids
    assert set(tables["fact_quiz_attempts"]["course_id"]) <= course_ids
    assert set(tables["fact_assignment_submissions"]["student_id"]) <= student_ids
    assert set(tables["fact_assignment_submissions"]["course_id"]) <= course_ids
    assert set(tables["dim_resources"]["course_id"]) <= course_ids


def test_score_and_grade_ranges(tables) -> None:
    scores = tables["fact_quiz_attempts"]["score"]
    assert scores.between(0, 100).all()

    grades = tables["fact_assignment_submissions"]["grade"].dropna()
    assert grades.between(0, 100).all()


def test_session_times_consistent(tables) -> None:
    sessions = tables["fact_sessions"]
    assert (sessions["logout_at"] > sessions["login_at"]).all()
    assert (sessions["duration_minutes"] > 0).all()


def test_attempt_numbers_sequential(tables) -> None:
    qa = tables["fact_quiz_attempts"]
    for (_, _), grp in qa.groupby(["student_id", "quiz_id"]):
        expected = list(range(1, len(grp) + 1))
        assert grp.sort_values("attempt_number")["attempt_number"].tolist() == expected


def test_submission_on_time_logic(tables) -> None:
    sub = tables["fact_assignment_submissions"]
    # Missing submissions are never on time.
    missing = sub[sub["submitted_at"].isna()]
    assert not missing["on_time"].any()
    # On-time submissions arrive on or before the due date.
    ontime = sub[sub["on_time"]]
    assert (ontime["submitted_at"] <= ontime["due_at"]).all()


def test_determinism(sim_config: SimConfig) -> None:
    a = generate_all(sim_config)
    b = generate_all(sim_config)
    for name in EXPECTED_TABLES:
        pd.testing.assert_frame_equal(a[name], b[name])


def test_write_tables_creates_csv_and_json(sim_config, tables) -> None:
    write_tables(tables, sim_config)
    for name in EXPECTED_TABLES:
        assert (sim_config.out_dir / f"{name}.csv").exists()
        assert (sim_config.out_dir / f"{name}.json").exists()
    assert (sim_config.out_dir / "manifest.json").exists()
