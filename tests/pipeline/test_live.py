import os
from pathlib import Path

import pytest
from knack.pipeline.clients import live_clients
from knack.pipeline.init import run_init
from knack.walk.registry import load_registry

LIVE_REPO = os.environ.get("KNACK_LIVE_REPO", "fastapi/fastapi")

pytestmark = pytest.mark.skipif(
    os.environ.get("KNACK_LIVE") != "1",
    reason="hits GitHub and Spark; set KNACK_LIVE=1 with GITHUB_TOKEN and MODEL_API_KEY",
)


def test_live_init_writes_a_loadable_registry(tmp_path: Path) -> None:
    lines = list[str]()
    path = run_init(LIVE_REPO, 3, tmp_path, *live_clients(), log=lines.append)
    registry = load_registry(path)
    print("\n".join(lines))
    assert registry.repo == LIVE_REPO and "[5/5] install" in lines[-1]
    assert all(entry.rule.exists() for entry in registry.rules)
