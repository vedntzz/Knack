import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Callable

import pytest

SPIKES = Path(__file__).parents[2] / "spikes"
SpikeLoader = Callable[[str], ModuleType]


@pytest.fixture
def load_spike(monkeypatch: pytest.MonkeyPatch) -> SpikeLoader:
    # spikes import each other by bare name, so their folder goes on sys.path
    monkeypatch.setattr(sys, "path", [str(SPIKES), *sys.path])
    return load_spike_file


def load_spike_file(name: str) -> ModuleType:
    # KNACK_SPIKE_PATH swaps in another copy of batch_precision, e.g. the old main-only one
    override = os.environ.get("KNACK_SPIKE_PATH") if name == "batch_precision" else None
    spec = importlib.util.spec_from_file_location(
        name, override or SPIKES / f"{name}.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
