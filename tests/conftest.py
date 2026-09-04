from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.config import Settings
from backend.app.system import build_system


@pytest.fixture
def system(tmp_path: Path):
    return build_system(
        Settings(
            database_path=tmp_path / "test.db",
            intake_delay_seconds=0,
            agent_analysis_seconds=0,
            action_delay_seconds=0,
            technician_delay_seconds=0,
            verification_delay_seconds=0,
            simulation_enabled=True,
        )
    )
