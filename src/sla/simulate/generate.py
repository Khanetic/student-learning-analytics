"""Simulated LMS data generator (Phase 1).

Produces a realistic, fully *deterministic* snapshot of learning-management-
system activity for a cohort of students and writes it to ``data/raw`` as both
CSV and JSON.

Realism comes from a single latent ``diligence`` score drawn per student that
drives every downstream behaviour (how often they log in, how long they stay,
how their quiz scores trend, whether they submit assignments on time). This
makes the learning indicators computed in later phases meaningful — diligent
students look engaged and improving, disengaged students naturally fall into
the *at-risk* band.

Run it as a module::

    python -m sla.simulate.generate
    python -m sla.simulate.generate --students 50 --weeks 12 --seed 42

Or via the installed console script::

    sla-simulate
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker

from sla.config import get_settings

# ---------------------------------------------------------------------------
# Reference data (the static "course catalogue" the simulation is built around)
# ---------------------------------------------------------------------------

#: A fixed anchor date so output is byte-for-byte reproducible regardless of
#: when the script is run. Overridable via ``--reference-date``.
DEFAULT_REFERENCE_DATE = date(2026, 6, 16)

PROGRAMS: list[str] = [
    "B.Sc. Computer Science",
    "B.Sc. Psychology",
    "M.Sc. Data Science",
    "B.Sc. Mathematics",
    "B.A. Educational Science",
]

#: device_type -> selection probability (must sum to 1.0).
DEVICE_WEIGHTS: dict[str, float] = {
    "desktop": 0.45,
    "laptop": 0.33,
    "tablet": 0.13,
    "mobile": 0.09,
}

RESOURCE_TYPES: list[str] = ["video", "reading", "slide_deck", "forum_thread", "exercise"]

#: The course catalogue. Each course expands into resources, quizzes and
#: assignments. ``code`` is used to build stable child IDs.
COURSE_CATALOG: list[dict] = [
    {"code": "CS101", "name": "Introduction to Programming", "credits": 6,
     "n_resources": 8, "n_quizzes": 5, "n_assignments": 4},
    {"code": "MA101", "name": "Calculus I", "credits": 9,
     "n_resources": 6, "n_quizzes": 6, "n_assignments": 3},
    {"code": "PSY110", "name": "Foundations of Psychology", "credits": 6,
     "n_resources": 7, "n_quizzes": 4, "n_assignments": 3},
    {"code": "DS200", "name": "Data Analysis with Python", "credits": 6,
     "n_resources": 9, "n_quizzes": 5, "n_assignments": 5},
    {"code": "ED150", "name": "Learning & Instruction", "credits": 5,
     "n_resources": 6, "n_quizzes": 3, "n_assignments": 4},
    {"code": "ST220", "name": "Statistics for Social Sciences", "credits": 6,
     "n_resources": 7, "n_quizzes": 5, "n_assignments": 3},
]


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SimConfig:
    """Resolved parameters for one simulation run."""

    seed: int
    n_students: int
    sim_weeks: int
    reference_date: date
    out_dir: Path

    @property
    def window_start(self) -> date:
        """First calendar day of the activity window."""
        return self.reference_date - timedelta(weeks=self.sim_weeks)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _datetime_columns(df: pd.DataFrame) -> list[str]:
    """Return the names of datetime-typed columns in ``df``."""
    return [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]


def _random_datetime_on(rng: np.random.Generator, day: date) -> datetime:
    """Pick a plausible study time on ``day`` (clustered around the evening)."""
    hour = int(np.clip(rng.normal(18.0, 4.0), 6, 23))
    minute = int(rng.integers(0, 60))
    second = int(rng.integers(0, 60))
    return datetime.combine(day, time(hour, minute, second))


def _day_sampling_weights(days: list[date]) -> np.ndarray:
    """Weight weekdays higher than weekends and recent days slightly higher."""
    n = len(days)
    weights = np.empty(n, dtype=float)
    for i, d in enumerate(days):
        weekday_factor = 1.0 if d.weekday() < 5 else 0.45
        recency_factor = 0.7 + 0.3 * (i / max(n - 1, 1))  # newer days weighted up
        weights[i] = weekday_factor * recency_factor
    return weights / weights.sum()


# ---------------------------------------------------------------------------
# Dimension builders
# ---------------------------------------------------------------------------


def build_courses() -> pd.DataFrame:
    """Build the course dimension from :data:`COURSE_CATALOG`."""
    rows = [
        {
            "course_id": f"C{idx + 1:02d}",
            "course_code": c["code"],
            "course_name": c["name"],
            "credits": c["credits"],
        }
        for idx, c in enumerate(COURSE_CATALOG)
    ]
    return pd.DataFrame(rows)


def build_resources(rng: np.random.Generator, courses: pd.DataFrame) -> pd.DataFrame:
    """Build the resource dimension (learning materials per course)."""
    rows: list[dict] = []
    for course in courses.itertuples(index=False):
        spec = next(c for c in COURSE_CATALOG if c["code"] == course.course_code)
        for seq in range(1, spec["n_resources"] + 1):
            rows.append(
                {
                    "resource_id": f"R{course.course_code}-{seq:02d}",
                    "course_id": course.course_id,
                    "title": f"{course.course_code} · Unit {seq}",
                    "resource_type": RESOURCE_TYPES[int(rng.integers(0, len(RESOURCE_TYPES)))],
                }
            )
    return pd.DataFrame(rows)


def build_students(
    rng: np.random.Generator, faker: Faker, cfg: SimConfig
) -> tuple[pd.DataFrame, np.ndarray]:
    """Build the student dimension.

    Returns the student DataFrame plus the per-student latent ``diligence``
    array (kept separate from the public data, used only to drive behaviour).
    """
    # Beta(2.2, 2.2) gives a believable centre-heavy spread in [0, 1].
    diligence = rng.beta(2.2, 2.2, size=cfg.n_students)
    rows: list[dict] = []
    for i in range(cfg.n_students):
        enroll_offset = int(rng.integers(60, 730))  # 2 months to 2 years ago
        rows.append(
            {
                "student_id": f"S{i + 1:04d}",
                "name": faker.name(),
                "program": PROGRAMS[int(rng.integers(0, len(PROGRAMS)))],
                "enrollment_date": cfg.reference_date - timedelta(days=enroll_offset),
            }
        )
    students = pd.DataFrame(rows)
    students["enrollment_date"] = pd.to_datetime(students["enrollment_date"])
    return students, diligence


def assign_enrollments(
    rng: np.random.Generator, students: pd.DataFrame, courses: pd.DataFrame
) -> dict[str, list[str]]:
    """Map each student to the 3–5 courses they are enrolled in."""
    course_ids = courses["course_id"].tolist()
    enrollments: dict[str, list[str]] = {}
    for sid in students["student_id"]:
        k = int(rng.integers(3, min(5, len(course_ids)) + 1))
        chosen = rng.choice(course_ids, size=k, replace=False)
        enrollments[sid] = sorted(chosen.tolist())
    return enrollments


# ---------------------------------------------------------------------------
# Fact builders
# ---------------------------------------------------------------------------


def build_sessions(
    rng: np.random.Generator, students: pd.DataFrame, diligence: np.ndarray, cfg: SimConfig
) -> pd.DataFrame:
    """Build login/logout sessions, count and length scaled by diligence."""
    span = (cfg.reference_date - cfg.window_start).days + 1
    window_days = [cfg.window_start + timedelta(days=d) for d in range(span)]
    day_weights = _day_sampling_weights(window_days)
    devices = list(DEVICE_WEIGHTS)
    device_p = np.array(list(DEVICE_WEIGHTS.values()))

    rows: list[dict] = []
    counter = 0
    for sid, dgl in zip(students["student_id"], diligence, strict=True):
        # Expected number of sessions over the whole window.
        n_sessions = int(rng.poisson(6 + dgl * 44))
        if n_sessions == 0:
            continue
        chosen_days = rng.choice(len(window_days), size=n_sessions, p=day_weights)
        for day_idx in chosen_days:
            login = _random_datetime_on(rng, window_days[int(day_idx)])
            base_minutes = 12 + dgl * 78
            duration = float(np.clip(rng.normal(base_minutes, base_minutes * 0.4), 4, 300))
            counter += 1
            rows.append(
                {
                    "session_id": f"SES{counter:06d}",
                    "student_id": sid,
                    "login_at": login,
                    "logout_at": login + timedelta(minutes=duration),
                    "duration_minutes": round(duration, 1),
                    "device_type": devices[int(rng.choice(len(devices), p=device_p))],
                }
            )
    df = pd.DataFrame(rows).sort_values(["student_id", "login_at"]).reset_index(drop=True)
    df["login_at"] = pd.to_datetime(df["login_at"])
    df["logout_at"] = pd.to_datetime(df["logout_at"])
    return df


def build_page_views(
    rng: np.random.Generator,
    sessions: pd.DataFrame,
    diligence_by_student: dict[str, float],
    enrollments: dict[str, list[str]],
    resources: pd.DataFrame,
) -> pd.DataFrame:
    """Build per-session page views over the student's enrolled resources."""
    res_by_course: dict[str, list[str]] = (
        resources.groupby("course_id")["resource_id"].apply(list).to_dict()
    )
    rows: list[dict] = []
    counter = 0
    for s in sessions.itertuples(index=False):
        dgl = diligence_by_student[s.student_id]
        enrolled = enrollments[s.student_id]
        # Candidate resources = those belonging to the student's courses.
        candidates = [rid for cid in enrolled for rid in res_by_course.get(cid, [])]
        if not candidates:
            continue
        n_views = 1 + int(rng.poisson(1 + dgl * 4))
        session_seconds = max((s.logout_at - s.login_at).total_seconds(), 60)
        for v in range(n_views):
            offset = session_seconds * (v / max(n_views, 1))
            time_spent = float(np.clip(rng.normal(90 + dgl * 240, 80), 10, 1800))
            counter += 1
            rows.append(
                {
                    "page_view_id": f"PV{counter:07d}",
                    "session_id": s.session_id,
                    "student_id": s.student_id,
                    "resource_id": candidates[int(rng.integers(0, len(candidates)))],
                    "viewed_at": s.login_at + timedelta(seconds=offset),
                    "time_spent_seconds": round(time_spent, 1),
                }
            )
    df = pd.DataFrame(rows)
    df["viewed_at"] = pd.to_datetime(df["viewed_at"])
    return df


def build_quiz_attempts(
    rng: np.random.Generator,
    students: pd.DataFrame,
    diligence: np.ndarray,
    enrollments: dict[str, list[str]],
    courses: pd.DataFrame,
    cfg: SimConfig,
) -> pd.DataFrame:
    """Build quiz attempts with a per-student score trend driven by diligence.

    Diligent students improve across repeated attempts; disengaged students
    drift downward, which later surfaces as a negative ``quiz_trend``.
    """
    code_by_id = dict(zip(courses["course_id"], courses["course_code"], strict=True))
    window_days = (cfg.reference_date - cfg.window_start).days
    rows: list[dict] = []
    counter = 0
    for sid, dgl in zip(students["student_id"], diligence, strict=True):
        ability = float(np.clip(rng.normal(45 + dgl * 45, 8), 0, 100))
        slope = (dgl - 0.45) * 9  # >0 improving, <0 declining
        for cid in enrollments[sid]:
            spec = next(c for c in COURSE_CATALOG if c["code"] == code_by_id[cid])
            for q in range(1, spec["n_quizzes"] + 1):
                quiz_id = f"Q{code_by_id[cid]}-{q:02d}"
                n_attempts = 1 + int(rng.binomial(4, 0.3 + dgl * 0.4))
                for attempt in range(1, n_attempts + 1):
                    score = float(
                        np.clip(ability + slope * (attempt - 1) + rng.normal(0, 6), 0, 100)
                    )
                    day_offset = int(rng.integers(0, window_days + 1))
                    ts = _random_datetime_on(rng, cfg.window_start + timedelta(days=day_offset))
                    counter += 1
                    rows.append(
                        {
                            "attempt_id": f"QA{counter:07d}",
                            "student_id": sid,
                            "course_id": cid,
                            "quiz_id": quiz_id,
                            "attempt_number": attempt,
                            "score": round(score, 1),
                            "submitted_at": ts,
                        }
                    )
    df = (
        pd.DataFrame(rows)
        .sort_values(["student_id", "quiz_id", "attempt_number"])
        .reset_index(drop=True)
    )
    df["submitted_at"] = pd.to_datetime(df["submitted_at"])
    return df


def build_assignment_submissions(
    rng: np.random.Generator,
    students: pd.DataFrame,
    diligence: np.ndarray,
    enrollments: dict[str, list[str]],
    courses: pd.DataFrame,
    cfg: SimConfig,
) -> pd.DataFrame:
    """Build one row per assigned assignment.

    ``submitted_at``/``grade`` are null when the student never submitted, and
    ``on_time`` is False for missing or late work — this gives later phases a
    realistic submission-rate signal.
    """
    code_by_id = dict(zip(courses["course_id"], courses["course_code"], strict=True))
    window_days = (cfg.reference_date - cfg.window_start).days
    rows: list[dict] = []
    counter = 0
    for sid, dgl in zip(students["student_id"], diligence, strict=True):
        ability = float(np.clip(rng.normal(45 + dgl * 45, 8), 0, 100))
        p_submit = float(np.clip(0.4 + dgl * 0.58, 0.05, 0.99))
        p_late = float(np.clip(0.35 - dgl * 0.28, 0.02, 0.5))
        for cid in enrollments[sid]:
            spec = next(c for c in COURSE_CATALOG if c["code"] == code_by_id[cid])
            for a in range(1, spec["n_assignments"] + 1):
                # Spread due dates evenly across the window.
                due_offset = int(window_days * a / (spec["n_assignments"] + 1))
                due_at = datetime.combine(
                    cfg.window_start + timedelta(days=due_offset), time(23, 59, 0)
                )
                submitted = rng.random() < p_submit
                submitted_at = None
                grade = None
                on_time = False
                if submitted:
                    late = rng.random() < p_late
                    if late:
                        delta = timedelta(days=float(rng.uniform(0.2, 4)))
                        submitted_at = due_at + delta
                    else:
                        delta = timedelta(days=float(rng.uniform(0.2, 5)))
                        submitted_at = due_at - delta
                    on_time = not late
                    grade = round(float(np.clip(rng.normal(ability, 8), 0, 100)), 1)
                counter += 1
                rows.append(
                    {
                        "submission_id": f"AS{counter:07d}",
                        "student_id": sid,
                        "course_id": cid,
                        "assignment_id": f"A{code_by_id[cid]}-{a:02d}",
                        "due_at": due_at,
                        "submitted_at": submitted_at,
                        "grade": grade,
                        "on_time": on_time,
                    }
                )
    df = pd.DataFrame(rows)
    df["due_at"] = pd.to_datetime(df["due_at"])
    df["submitted_at"] = pd.to_datetime(df["submitted_at"])
    return df


# ---------------------------------------------------------------------------
# Orchestration & output
# ---------------------------------------------------------------------------


def generate_all(cfg: SimConfig) -> dict[str, pd.DataFrame]:
    """Generate every table for a run and return them keyed by table name."""
    rng = np.random.default_rng(cfg.seed)
    faker = Faker()
    Faker.seed(cfg.seed)

    courses = build_courses()
    resources = build_resources(rng, courses)
    students, diligence = build_students(rng, faker, cfg)
    enrollments = assign_enrollments(rng, students, courses)
    diligence_by_student = dict(zip(students["student_id"], diligence, strict=True))

    sessions = build_sessions(rng, students, diligence, cfg)
    page_views = build_page_views(rng, sessions, diligence_by_student, enrollments, resources)
    quiz_attempts = build_quiz_attempts(rng, students, diligence, enrollments, courses, cfg)
    submissions = build_assignment_submissions(
        rng, students, diligence, enrollments, courses, cfg
    )

    return {
        "dim_courses": courses,
        "dim_resources": resources,
        "dim_students": students,
        "fact_sessions": sessions,
        "fact_page_views": page_views,
        "fact_quiz_attempts": quiz_attempts,
        "fact_assignment_submissions": submissions,
    }


def write_tables(tables: dict[str, pd.DataFrame], cfg: SimConfig) -> None:
    """Write each table to ``out_dir`` as CSV and JSON, plus a manifest."""
    cfg.out_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, object] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "reference_date": cfg.reference_date.isoformat(),
        "window_start": cfg.window_start.isoformat(),
        "seed": cfg.seed,
        "n_students": cfg.n_students,
        "sim_weeks": cfg.sim_weeks,
        "tables": {},
    }
    for name, df in tables.items():
        csv_path = cfg.out_dir / f"{name}.csv"
        json_path = cfg.out_dir / f"{name}.json"
        df.to_csv(csv_path, index=False)
        df.to_json(json_path, orient="records", date_format="iso", indent=2)
        manifest["tables"][name] = {  # type: ignore[index]
            "rows": int(len(df)),
            "columns": list(df.columns),
        }
    (cfg.out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))


def _resolve_config(args: argparse.Namespace) -> SimConfig:
    """Merge CLI args over environment-driven defaults from :mod:`sla.config`."""
    settings = get_settings()
    out_dir = Path(args.out) if args.out else settings.raw_dir
    return SimConfig(
        seed=args.seed if args.seed is not None else settings.seed,
        n_students=args.students if args.students is not None else settings.n_students,
        sim_weeks=args.weeks if args.weeks is not None else settings.sim_weeks,
        reference_date=(
            date.fromisoformat(args.reference_date)
            if args.reference_date
            else DEFAULT_REFERENCE_DATE
        ),
        out_dir=out_dir,
    )


def main(argv: list[str] | None = None) -> None:
    """CLI entry point: generate the dataset and write it to disk."""
    parser = argparse.ArgumentParser(description="Generate simulated LMS data.")
    parser.add_argument("--students", type=int, default=None, help="number of students")
    parser.add_argument("--weeks", type=int, default=None, help="activity window length in weeks")
    parser.add_argument("--seed", type=int, default=None, help="random seed")
    parser.add_argument(
        "--reference-date", type=str, default=None, help="window end date (YYYY-MM-DD)"
    )
    parser.add_argument("--out", type=str, default=None, help="output directory")
    args = parser.parse_args(argv)

    cfg = _resolve_config(args)
    tables = generate_all(cfg)
    write_tables(tables, cfg)

    print(f"Simulated LMS data written to {cfg.out_dir}")
    for name, df in tables.items():
        print(f"  {name:<28} {len(df):>7,} rows")


if __name__ == "__main__":
    main()
