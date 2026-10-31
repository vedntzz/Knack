import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parents[1]
SCRIPT = REPO_ROOT / "scripts" / "e2e.sh"
STEPS = [
    "fixture clone",
    "knack init",
    "knack confirm",
    "alias edit denied",
    "correct fix allowed",
    "argue holds",
    "receipts verify",
    "real HOME untouched",
]


SCRIPTS = [SCRIPT, REPO_ROOT / "scripts" / "e2e_fakes.py"]
FIXTURES = REPO_ROOT / "scripts" / "fixtures"
# Untracked or machine-local sources a CI checkout does not have.
LOCAL_ONLY = ["spikes/", ".knack/cache"]


def run_e2e(home: Path) -> subprocess.CompletedProcess[str]:
    # CI's shape: an empty HOME, a bare PATH, only the interpreter passed in.
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin", "PYTHON": sys.executable}
    return subprocess.run(
        ["bash", str(SCRIPT)], capture_output=True, text=True, timeout=600, env=env
    )


def ignored(paths: list[Path]) -> list[str]:
    # The paths git would leave out of a commit.
    names = [str(p.relative_to(REPO_ROOT)) for p in paths]
    done = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "check-ignore", *names],
        capture_output=True,
        text=True,
    )
    return done.stdout.split()


def test_e2e_reads_nothing_local_only() -> None:
    for script in SCRIPTS:
        text = script.read_text(encoding="utf-8")
        assert [s for s in LOCAL_ONLY if s in text] == [], script.name


def test_every_e2e_fixture_is_committable() -> None:
    files = [p for p in FIXTURES.rglob("*") if p.is_file()]
    assert files and ignored(files) == []


def test_e2e_passes_every_step_and_exits_0(tmp_path: Path) -> None:
    done = run_e2e(tmp_path)
    assert done.returncode == 0, done.stdout + done.stderr
    assert [f"PASS {step}" for step in STEPS] == [
        line for line in done.stdout.splitlines() if line.startswith("PASS ")
    ]
    assert "FAIL" not in done.stdout
