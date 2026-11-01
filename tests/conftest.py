import os
from pathlib import Path

import pytest

# Read once at import, before any test changes HOME or KNACK_HOME.
REAL_HOME = Path(os.environ["HOME"])
REAL_KNACK_HOME = Path(os.environ.get("KNACK_HOME") or REAL_HOME / ".knack")


@pytest.fixture(autouse=True)
def isolated_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> Path:
    # Every test gets its own HOME and KNACK_HOME; the user's are never touched.
    home = tmp_path_factory.mktemp("home")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("KNACK_HOME", str(home / ".knack"))
    return home


@pytest.fixture
def real_home() -> Path:
    return REAL_HOME


@pytest.fixture
def real_knack_home() -> Path:
    return REAL_KNACK_HOME
