import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parents[1]
SCRIPT = REPO_ROOT / "scripts" / "e2e.sh"
STEPS = [
    "knack init",
    "knack confirm",
    "alias edit denied",
    "correct fix allowed",
    "argue holds",
    "receipts verify",
    "real HOME untouched",
]


def run_e2e() -> subprocess.CompletedProcess[str]:
    # The script makes its own temp HOME; it gets this interpreter, nothing else.
    env = {**os.environ, "PYTHON": sys.executable}
    return subprocess.run(
        ["bash", str(SCRIPT)], capture_output=True, text=True, timeout=600, env=env
    )


def test_e2e_passes_every_step_and_exits_0() -> None:
    done = run_e2e()
    assert done.returncode == 0, done.stdout + done.stderr
    assert [f"PASS {step}" for step in STEPS] == [
        line for line in done.stdout.splitlines() if line.startswith("PASS ")
    ]
    assert "FAIL" not in done.stdout
