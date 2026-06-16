"""Shared pytest fixtures."""

from __future__ import annotations

from datetime import date

import pytest

from sla.simulate.generate import SimConfig, generate_all


@pytest.fixture(scope="session")
def sim_config(tmp_path_factory: pytest.TempPathFactory) -> SimConfig:
    """A small, fast, deterministic simulation config writing to a temp dir."""
    out_dir = tmp_path_factory.mktemp("raw")
    return SimConfig(
        seed=42,
        n_students=20,
        sim_weeks=8,
        reference_date=date(2026, 6, 16),
        out_dir=out_dir,
    )


@pytest.fixture(scope="session")
def tables(sim_config: SimConfig) -> dict:
    """Generated tables for the test config (built once per session)."""
    return generate_all(sim_config)
