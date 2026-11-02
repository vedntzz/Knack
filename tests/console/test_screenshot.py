import json
import os
import shutil
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from knack.home import user_home

REPO_ROOT = Path(__file__).parents[2]
HERE = Path(__file__).parent
SHOOT = HERE / "screenshot.mjs"
BASELINES = HERE / "baselines"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "console_75025"
DATA_REGISTRY = REPO_ROOT / "data" / "registry" / "airflow.json"
DATA_ROOTS = REPO_ROOT / "data" / "roots" / "airflow"
DENY = "08a2c39bcceddafae995781163b6e8ea17ab0f02c2cb4e48a65bf3cc3a097f3c"
# At most this share of pixels may differ from the baseline.
MOST_CHANGED = 0.001
# KNACK_SAVE_BASELINE=1 shoots the baselines instead of comparing against them.
SAVE_ENV = "KNACK_SAVE_BASELINE"
Entry = dict[str, Any]
SERVE = (
    "import sys, uvicorn; from pathlib import Path; "
    "from knack.console.app import create_app; r, g, port = sys.argv[1:]; "
    "app = create_app(Path(r), Path(r).with_name('warns.jsonl'), "
    "Path(r).with_name('rulings.jsonl'), lambda repo: Path(g)); "
    "uvicorn.run(app, host='127.0.0.1', port=int(port), log_level='warning')"
)


def playwright() -> str | None:
    # PLAYWRIGHT names playwright/index.mjs, as the mockup captures use; else npx's cache.
    named = os.environ.get("PLAYWRIGHT")
    cached = sorted(user_home().glob(".npm/_npx/*/node_modules/playwright/index.mjs"))
    return named or (str(cached[-1]) if cached else None)


def browsers() -> str:
    # Where playwright keeps its browsers: macOS's cache folder, else Linux's.
    caches = [
        user_home() / "Library/Caches/ms-playwright",
        user_home() / ".cache/ms-playwright",
    ]
    found = next((str(c) for c in caches if c.exists()), "")
    return os.environ.get("PLAYWRIGHT_BROWSERS_PATH", found)


# Found at import: every test runs in its own HOME, where neither cache is.
PLAYWRIGHT, BROWSERS = playwright(), browsers()


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def absolute(entry: Entry) -> Entry:
    return entry | {"rule": str((DATA_REGISTRY.parent / entry["rule"]).resolve())}


def fixture_registry(base: Path) -> Path:
    # The airflow registry, with its rule paths absolute and its roots copied beside it.
    shutil.copytree(DATA_ROOTS, base / "roots")
    data: Entry = json.loads(DATA_REGISTRY.read_text())
    rules: list[Entry] = list(map(absolute, data["rules"]))
    body = data | {"roots_dir": str(base / "roots"), "rules": rules}
    (base / "registry.json").write_text(json.dumps(body))
    return base / "registry.json"


def wait_for(port: int) -> None:
    for _ in range(200):
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.05)


def serve(base: Path, port: int) -> subprocess.Popen[bytes]:
    # Run from its own folder, so the verify row names knack/verdicts.jsonl on every run.
    shutil.copytree(FIXTURE, base / "knack")
    args = [str(base / "knack" / "verdicts.jsonl"), str(fixture_registry(base))]
    return subprocess.Popen([sys.executable, "-c", SERVE, *args, str(port)], cwd=base)


@pytest.fixture(scope="module")
def console(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    port = free_port()
    server = serve(tmp_path_factory.mktemp("screens").resolve(), port)
    wait_for(port)
    yield f"http://127.0.0.1:{port}"
    server.terminate()
    server.wait()


def node(*args: str) -> str:
    found = {"PLAYWRIGHT": PLAYWRIGHT or "", "PLAYWRIGHT_BROWSERS_PATH": BROWSERS}
    env, command = os.environ | found, ["node", str(SHOOT), *args]
    done = subprocess.run(command, env=env, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


@pytest.mark.skipif(PLAYWRIGHT is None, reason="playwright is not installed")
@pytest.mark.parametrize("width,height", [(1920, 1080), (1280, 720)])
def test_the_75025_page_looks_as_it_did_before(
    console: str, tmp_path: Path, width: int, height: int
) -> None:
    baseline = BASELINES / f"verdict-75025-{width}x{height}.png"
    shot = baseline if os.environ.get(SAVE_ENV) else tmp_path / baseline.name
    node("shoot", f"{console}/verdict/{DENY}", str(width), str(height), str(shot))
    assert float(node("diff", str(baseline), str(shot))) <= MOST_CHANGED
