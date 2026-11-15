import math
import subprocess
import tempfile
from pathlib import Path
from typing import Literal

from knack.bench.attempts import new_matches
from pydantic import BaseModel, ConfigDict

GIT_TIMEOUT_SECONDS = 30
THRESHOLD_RATE = 0.30
MIN_TICKETS = 10
Z95 = 1.959964
# A plain identity, so the sandbox history names nothing of the bench.
GIT_CONFIG = (
    "-c",
    "user.name=Developer",
    "-c",
    "user.email=dev@example.com",
    "-c",
    "commit.gpgsign=false",
)


class PilotVerdict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    repeats: int
    runs: int
    tickets: int
    rate: float
    low: float
    high: float
    decision: Literal["go", "pivot"]


def make_sandbox(root: Path, files: dict[str, str]) -> Path:
    # A fresh git repo holding only the base files, one commit, outside the Knack repo.
    root.mkdir(parents=True, exist_ok=True)
    sandbox = Path(tempfile.mkdtemp(prefix="repo_", dir=root))
    for name, text in files.items():
        (sandbox / name).parent.mkdir(parents=True, exist_ok=True)
        (sandbox / name).write_text(text, encoding="utf-8")
    _git(sandbox, "init", "-q", "-b", "main")
    _git(sandbox, "add", "-A")
    _git(sandbox, "commit", "-q", "-m", "Initial import")
    return sandbox


def final_diff(sandbox: Path) -> str:
    # Staging everything makes new files part of the diff against the base commit.
    _git(sandbox, "add", "-A")
    return _git(sandbox, "diff", "--cached", "HEAD")


def final_hits(sandbox: Path, rule: Path) -> list[str]:
    # Rule matches the agent's final tree added over the base, in every changed .py file.
    _git(sandbox, "add", "-A")
    changed = _git(sandbox, "diff", "--cached", "--name-only", "HEAD").split()
    python = [name for name in changed if name.endswith(".py")]
    return [hit for name in python for hit in _file_hits(sandbox, name, rule)]


def is_repeat(hits: list[str], blind_label: str | None) -> bool:
    return bool(hits) and blind_label == "yes"


def wilson_interval(successes: int, trials: int) -> tuple[float, float]:
    if trials == 0:
        return (0.0, 1.0)
    p, z2 = successes / trials, Z95 * Z95
    centre = (p + z2 / (2 * trials)) / (1 + z2 / trials)
    spread = (
        Z95 * math.sqrt(p * (1 - p) / trials + z2 / (4 * trials**2)) / (1 + z2 / trials)
    )
    return (max(0.0, centre - spread), min(1.0, centre + spread))


def pilot_verdict(runs: list[tuple[str, bool]]) -> PilotVerdict:
    # Pre-registered: go when the pooled point rate is at least 30% over at least 10 tickets.
    repeats, tickets = sum(r for _, r in runs), len({t for t, _ in runs})
    rate = repeats / len(runs) if runs else 0.0
    low, high = wilson_interval(repeats, len(runs))
    go = rate >= THRESHOLD_RATE and tickets >= MIN_TICKETS
    return PilotVerdict(
        repeats=repeats,
        runs=len(runs),
        tickets=tickets,
        rate=rate,
        low=low,
        high=high,
        decision="go" if go else "pivot",
    )


def _file_hits(sandbox: Path, name: str, rule: Path) -> list[str]:
    after = sandbox / name
    current = after.read_text(encoding="utf-8") if after.is_file() else ""
    return new_matches(_base_text(sandbox, name), current, rule)


def _base_text(sandbox: Path, name: str) -> str:
    # A file the agent created has no base version.
    done = subprocess.run(
        ["git", "-C", str(sandbox), "show", f"HEAD:{name}"],
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT_SECONDS,
    )
    return done.stdout if done.returncode == 0 else ""


def _git(sandbox: Path, *args: str) -> str:
    command = ["git", "-C", str(sandbox), *GIT_CONFIG, *args]
    done = subprocess.run(
        command, check=True, capture_output=True, text=True, timeout=GIT_TIMEOUT_SECONDS
    )
    return done.stdout
