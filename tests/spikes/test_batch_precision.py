import importlib.util
import os
from pathlib import Path
from types import ModuleType

import pytest

SPIKE = Path(__file__).parents[2] / "spikes/batch_precision.py"
RecordedClones = tuple[ModuleType, list[list[str]]]


def load_spike() -> ModuleType:
    # KNACK_SPIKE_PATH swaps in another copy of the script, e.g. the old main-only one
    path = Path(os.environ.get("KNACK_SPIKE_PATH", SPIKE))
    spec = importlib.util.spec_from_file_location("batch_precision", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def recorded_clones(monkeypatch: pytest.MonkeyPatch) -> RecordedClones:
    # fake subprocess.run so no clone touches the network
    spike, calls = load_spike(), list[list[str]]()

    def record(argv: list[str], **_: object) -> None:
        calls.append(argv)

    monkeypatch.setattr(spike.subprocess, "run", record)
    return spike, calls


def test_ref_gets_its_own_clone_folder(recorded_clones: RecordedClones) -> None:
    spike, _ = recorded_clones
    assert spike.clone_dir("v2-10-stable") == Path("/tmp/airflow-v2-10-stable")


def test_clone_checks_out_the_requested_ref(
    recorded_clones: RecordedClones, tmp_path: Path
) -> None:
    spike, calls = recorded_clones
    spike.shallow_clone("v2-10-stable", tmp_path / "airflow-v2-10-stable")
    assert calls[0][calls[0].index("--branch") + 1] == "v2-10-stable"
    assert calls[0][-1] == str(tmp_path / "airflow-v2-10-stable")
