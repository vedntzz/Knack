import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parents[1]
SCRIPT = REPO_ROOT / "scripts" / "reproduce.sh"
REPORT = REPO_ROOT / "bench" / "REPORT-1030c.md"
GRID = REPO_ROOT / "bench" / "PROOF-GRID.md"
# Sources a fresh clone does not have: ignored batch sources, caches, the home registry.
LOCAL_ONLY = ["/src/", ".knack/", "~", "$HOME/"]
SECTIONS = [
    "proof grid",
    "extraction",
    "held-out",
    "bench",
    "repeats",
    "breadth",
    "e2e",
]
# A number line: the number, then the command that printed it.
NUMBER_LINE = re.compile(r"^\S.*\d.*  \$ \S")
SYSTEM_PATH = "/usr/bin:/bin"
# The pattern reproduce.sh hands awk with -v, where gawk warns on any backslash escape.
OTHERS_LINE = re.compile(r"^OTHERS='(.*)'$", re.MULTILINE)


def run_reproduce(
    home: Path,
    python: str = sys.executable,
    alone: bool = True,
    path: str = SYSTEM_PATH,
) ->subprocess.CompletedProcess[str]:
    # alone: the suite's HOME is a temp dir, so another session's pytest cannot touch it.
    env = {"HOME": str(home), "PATH": path, "PYTHON": python}
    env |= {"KNACK_REPRODUCE_IGNORE_OTHERS": "1"} if alone else {}
    return subprocess.run(
        ["bash", str(SCRIPT)], capture_output=True, text=True, timeout=900, env=env
    )


def gawk_first_path(tmp_path: Path) -> str:
    # Puts gawk first as awk when installed; ubuntu CI's awk is gawk already.
    gawk = shutil.which("gawk")
    if gawk is None:
        return SYSTEM_PATH
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "awk").symlink_to(gawk)
    return f"{tmp_path / 'bin'}:{SYSTEM_PATH}"


def summary_lines(out: str) -> list[str]:
    return [line for line in out.splitlines() if line.startswith("PROOF:")]


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
        "roots: 22 (2 Confirmed, 0 Corroborated, 20 Inferred, 0 Uncorroborated, 0 Unknown)",
        "decisions hunted: 12 (every installed rule)",
        "repeat commits: 0 (0 human, 0 bot)",
        "e2e steps passed: 26/26",
    ]:
        (line,) = [line for line in out.splitlines() if line.startswith(wanted)]
        assert NUMBER_LINE.match(line), line
    # The bench tables appear verbatim, under the command that printed them.
    assert REPORT.read_text(encoding="utf-8").strip() in out
    # The grid prints first, verbatim as written to bench/PROOF-GRID.md.
    assert out.index(GRID.read_text(encoding="utf-8").strip()) < out.index(
        "== extraction =="
    )
    # A grid cell may say FAIL; a step that failed to run never may.
    assert "FAIL  $" not in out
    assert (
        summary_lines(out) == ["PROOF: PASS"] and out.splitlines()[-1] == "PROOF: PASS"
    )


def test_a_failed_step_ends_with_its_name_and_exit_1(tmp_path: Path) -> None:
    done = run_reproduce(tmp_path, python="/usr/bin/false")
    assert done.returncode == 1
    assert summary_lines(done.stdout) == ["PROOF: FAIL (proof grid)"]
    assert done.stdout.splitlines()[-1] == "PROOF: FAIL (proof grid)"


@pytest.mark.parametrize(
    "other",
    ["pytest -q", "python -m knack.hooks.pretool", "knack/.venv/bin/knack watch"],
)
def test_reproduce_refuses_to_start_beside_another_knack_or_pytest(
    tmp_path: Path, other: str
) -> None:
    # A stand-in whose argv[0] is the other run's whole command line.
    stand_in = subprocess.Popen(["bash", "-c", f"exec -a '{other}' sleep 60"])
    try:
        done = run_reproduce(tmp_path, alone=False)
    finally:
        stand_in.kill()
    assert done.returncode == 1
    assert "== proof grid ==" not in done.stdout
    assert done.stdout.splitlines() == [
        "PROOF: FAIL (another knack or pytest is running)"
    ]
    assert len(done.stderr.strip().splitlines()) == 1
    assert str(stand_in.pid) in done.stderr


def test_the_awk_pattern_has_no_backslash_escapes() -> None:
    (others,) = OTHERS_LINE.findall(SCRIPT.read_text(encoding="utf-8"))
    assert "\\" not in others


def test_refusal_stderr_carries_no_awk_warning(tmp_path: Path) -> None:
    stand_in = subprocess.Popen(["bash", "-c", "exec -a 'pytest -q' sleep 60"])
    try:
        done = run_reproduce(tmp_path, alone=False, path=gawk_first_path(tmp_path))
    finally:
        stand_in.kill()
    assert done.returncode == 1 and "awk:" not in done.stderr, done.stderr


def test_a_shell_whose_command_text_mentions_pytest_is_not_a_run(
    tmp_path: Path,
) -> None:
    # A shell -c wrapper is not the run; its python child, when there is one, is.
    wrapper = subprocess.Popen(["bash", "-c", "sleep 60; echo pytest -m knack"])
    try:
        done = run_reproduce(tmp_path, python="/usr/bin/false", alone=False)
    finally:
        wrapper.kill()
    assert summary_lines(done.stdout) == ["PROOF: FAIL (proof grid)"]


def test_reproduce_checks_the_committed_grid_and_never_writes_it() -> None:
    # A drifted grid fails the run instead of dirtying a stranger's clone.
    text = SCRIPT.read_text(encoding="utf-8")
    assert not re.search(r'(>|\bcp\b.*|\btee\b.*|\bmv\b.*)\s*"\$GRID"', text)
    assert 'diff -q "$WORK/grid.md" "$GRID" >/dev/null && same=yes' in text
