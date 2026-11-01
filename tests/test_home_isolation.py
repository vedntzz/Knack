import os
from pathlib import Path

import pytest
from knack.home import knack_home
from knack.hooks.scope import home_error_log, scoped_quietly


def mtimes(folder: Path) -> dict[str, int]:
    # Every path under folder with its mtime; a missing folder is empty.
    if not folder.exists():
        return {}
    paths = [folder, *folder.rglob("*")]
    return {str(p): p.stat().st_mtime_ns for p in paths}


def test_the_suite_never_runs_against_the_real_home(
    real_knack_home: Path, real_home: Path
) -> None:
    assert knack_home() != real_knack_home
    assert Path(os.environ["HOME"]) != real_home


def test_a_guard_error_leaves_the_real_knack_home_unchanged(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, real_knack_home: Path
) -> None:
    before = mtimes(real_knack_home)
    broken = tmp_path / "registry.json"
    broken.write_text("{nonsense")
    monkeypatch.setenv("KNACK_REGISTRY", str(broken))
    assert scoped_quietly({"cwd": str(tmp_path)}) is None
    assert "ValidationError" in home_error_log().read_text()
    assert mtimes(real_knack_home) == before
