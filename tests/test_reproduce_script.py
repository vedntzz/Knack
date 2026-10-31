import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parents[1]
SCRIPT = REPO_ROOT / "scripts" / "reproduce.sh"
REPORT = REPO_ROOT / "bench" / "REPORT-1030c.md"
# Sources a fresh clone does not have: ignored batch sources, caches, the home registry.
LOCAL_ONLY = ["/src/", ".knack/", "~", "$HOME/"]
SECTIONS = ["extraction", "held-out", "bench", "breadth", "e2e"]
# A number line: the number, then the command that printed it.
NUMBER_LINE = re.compile(r"^\S.*\d.*  \$ \S")


def run_reproduce(home: Path) -> subprocess.CompletedProcess[str]:
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin", "PYTHON": sys.executable}
    return subprocess.run(
        ["bash", str(SCRIPT)], capture_output=True, text=True, timeout=900, env=env
    )


def committed_inputs() -> list[str]:
    # Every repo path the script names as an input.
    text = SCRIPT.read_text(encoding="utf-8")
    return sorted(set(re.findall(r"\b(?:data|bench|spikes)/[\w./-]+", text)))


def test_reproduce_reads_nothing_local_only() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert [s for s in LOCAL_ONLY if s in text] == []


def test_every_input_the_script_names_is_tracked_by_git() -> None:
    inputs = committed_inputs()
    assert inputs
    tracked = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "check-ignore", *inputs],
        capture_output=True,
        text=True,
    )
    assert tracked.stdout.split() == []
    assert [p for p in inputs if not (REPO_ROOT / p).exists()] == []


def test_every_heldout_file_is_committable() -> None:
    files = [p for p in (REPO_ROOT / "data" / "heldout").rglob("*") if p.is_file()]
    names = [str(p.relative_to(REPO_ROOT)) for p in files]
    ignored = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "check-ignore", *names],
        capture_output=True,
        text=True,
    )
    assert files and ignored.stdout.split() == []


def test_reproduce_prints_every_number_beside_its_command(tmp_path: Path) -> None:
    done = run_reproduce(tmp_path)
    assert done.returncode == 0, done.stdout + done.stderr
    out = done.stdout
    headers = [line for line in out.splitlines() if line.startswith("== ")]
    assert headers == [f"== {s} ==" for s in SECTIONS]
    for wanted in [
        "total decisions: 107",
        "generality (same-model held-out pass): 8/13 PRs",
        "cross-model held-out pass: 8/13 PRs",
        "bench report matches bench/REPORT-1030c.md: yes",
        "roots: 22 (2 Confirmed, 20 Inferred, 0 Unknown)",
        "e2e steps passed: 8/8",
    ]:
        (line,) = [line for line in out.splitlines() if line.startswith(wanted)]
        assert NUMBER_LINE.match(line), line
    # The bench tables appear verbatim, under the command that printed them.
    assert REPORT.read_text(encoding="utf-8").strip() in out
    assert "FAIL" not in out
