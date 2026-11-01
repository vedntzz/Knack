from pathlib import Path

import pytest
from day_world import DayWorld


@pytest.fixture
def world(tmp_path: Path) -> DayWorld:
    return DayWorld(tmp_path)
