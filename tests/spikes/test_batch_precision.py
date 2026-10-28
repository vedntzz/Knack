import importlib.util
import os
from pathlib import Path

import pytest

SPIKE = Path(__file__).parents[2] / "spikes/batch_precision.py"


def load_spike():
    # KNACK_SPIKE_PATH swaps in another copy of the script, e.g. the old main-only one
    path = Path(os.environ.get("KNACK_SPIKE_PATH", SPIKE))
    spec = importlib.util.spec_from_file_location("batch_precision", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def recorded_clones(monkeypatch):
    # fake subprocess.run so no clone touches the network
    spike, calls = load_spike(), []
    monkeypatch.setattr(spike.subprocess, "run", lambda argv, **_: calls.append(argv))
    return spike, calls


def test_ref_gets_its_own_clone_folder(recorded_clones):
    spike, _ = recorded_clones
    assert spike.clone_dir("v2-10-stable") == Path("/tmp/airflow-v2-10-stable")


def test_clone_checks_out_the_requested_ref(recorded_clones, tmp_path):
    spike, calls = recorded_clones
    spike.shallow_clone("v2-10-stable", tmp_path / "airflow-v2-10-stable")
    assert calls[0][calls[0].index("--branch") + 1] == "v2-10-stable"
    assert calls[0][-1] == str(tmp_path / "airflow-v2-10-stable")
