import itertools
import os
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parents[1]
SCRIPT = REPO_ROOT / "scripts" / "e2e_console.sh"
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import e2e_console  # noqa: E402

# Every step the story drives, in order; each prints "ok  <step>" when its check passed.
STEPS = [
    "install",
    "console",
    "block",
    "events",
    "block page",
    "argue covered",
    "argue page",
    "argue uncovered",
    "argue links held",
    "resolve uphold",
    "held page",
    "corrected",
    "day page",
    "verify",
]
CONSOLE = ("127.0.0.1", 7655)


def run_e2e(home: Path, *args: str) -> subprocess.CompletedProcess[str]:
    # CI's shape: an empty HOME, a bare PATH, no credential of any kind.
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin", "PYTHON": sys.executable}
    home.mkdir(parents=True, exist_ok=True)
    command = ["bash", str(SCRIPT), *args]
    return subprocess.run(command, capture_output=True, text=True, timeout=300, env=env)


@pytest.fixture(scope="module")
def passed(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str]:
    home = tmp_path_factory.mktemp("e2e-console")
    done = run_e2e(home)
    assert done.returncode == 0, done.stdout + done.stderr
    return home, done.stdout


def step_lines(stdout: str) -> list[str]:
    return [line[4:] for line in stdout.splitlines() if line.startswith("ok  ")]


def test_every_step_passes_in_order_and_the_run_ends_with_pass(
    passed: tuple[Path, str],
) -> None:
    _, stdout = passed
    assert step_lines(stdout) == STEPS
    assert stdout.splitlines()[-1] == "E2E: PASS"


def test_a_second_run_prints_the_same_output(
    passed: tuple[Path, str], tmp_path: Path
) -> None:
    again = run_e2e(tmp_path)
    assert again.returncode == 0, again.stdout + again.stderr
    assert again.stdout == passed[1]


def test_the_run_never_writes_the_callers_home(passed: tuple[Path, str]) -> None:
    home, _ = passed
    assert sorted(p.name for p in home.iterdir()) == []


def test_the_run_names_fake_models_and_leaves_no_console_running(
    passed: tuple[Path, str],
) -> None:
    _, stdout = passed
    assert "Models: fake." in stdout
    assert not answers(CONSOLE)


def answers(address: tuple[str, int]) -> bool:
    with socket.socket() as probe:
        return probe.connect_ex(address) == 0


@pytest.fixture
def port_taken() -> Iterator[None]:
    # Another process holds the console's port, as a console left open would.
    with socket.socket() as held:
        held.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        held.bind(CONSOLE)
        held.listen()
        yield


@pytest.mark.usefixtures("port_taken")
def test_a_busy_console_port_fails_the_console_step_by_name(tmp_path: Path) -> None:
    done = run_e2e(tmp_path)
    assert done.returncode == 1
    assert done.stdout.splitlines()[-1] == "E2E: FAIL (console)"
    assert "7655" in done.stdout + done.stderr


def test_live_without_a_model_key_fails_before_anything_starts(tmp_path: Path) -> None:
    done = run_e2e(tmp_path, "--live")
    assert done.returncode == 1
    assert done.stdout.splitlines()[-1] == "E2E: FAIL (preflight)"
    assert "MODEL_API_KEY" in done.stdout + done.stderr
    assert "ok  install" not in done.stdout


def test_an_unknown_flag_fails_preflight(tmp_path: Path) -> None:
    done = run_e2e(tmp_path, "--fast")
    assert done.returncode == 1
    assert done.stdout.splitlines()[-1] == "E2E: FAIL (preflight)"


def test_script_sandboxes_home_and_never_names_the_real_one() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'export HOME="$WORK/home"' in text
    assert 'export KNACK_HOME="$HOME/.knack"' in text
    assert "~/.knack" not in text


def test_the_readme_console_section_names_the_script() -> None:
    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    start = text.index("\n## See it in the console\n")
    section = text[start : text.index("\n## ", start + 1)]
    assert "`bash scripts/e2e_console.sh`" in section


def start_e2e(home: Path, temp: Path) -> subprocess.Popen[str]:
    # Its own session, so every process the run starts shares its process group.
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin", "PYTHON": sys.executable}
    home.mkdir(parents=True, exist_ok=True)
    env["TMPDIR"] = str(temp)
    piped = {"stdout": subprocess.PIPE, "text": True, "env": env}
    return subprocess.Popen(["bash", str(SCRIPT)], start_new_session=True, **piped)


def wait_for_listener(temp: Path) -> None:
    # The block step's listener is connected to /events once it touches "listening".
    deadline = time.monotonic() + 60
    while not list(temp.glob("knack-e2e-console.*/listening")):
        assert time.monotonic() < deadline, "the listener never connected"
        time.sleep(0.005)


def left_running(group: int) -> list[str]:
    # Every process still in the run's process group, orphans included.
    listed = subprocess.run(["ps", "-ax", "-o", "pgid=,command="], capture_output=True, text=True)
    rows = [line.split(None, 1) for line in listed.stdout.splitlines()]
    return [row[1] for row in rows if len(row) == 2 and row[0] == str(group)]


def finished(run: subprocess.Popen[str]) -> str:
    # The run's stdout; a run still going after 30 s is a hang, killed so it leaves nothing.
    try:
        return run.communicate(timeout=30)[0]
    except subprocess.TimeoutExpired:
        os.killpg(run.pid, signal.SIGKILL)
        pytest.fail("the interrupted run hung:\n" + run.communicate()[0])


@pytest.mark.parametrize("sent", [signal.SIGTERM, signal.SIGINT])
def test_an_interrupted_run_exits_and_leaves_no_process_behind(
    tmp_path: Path, sent: signal.Signals
) -> None:
    temp = tmp_path / "tmp"
    temp.mkdir()
    run = start_e2e(tmp_path / "home", temp)
    wait_for_listener(temp)
    run.send_signal(sent)
    stdout = finished(run)
    assert run.returncode == 1, stdout
    assert stdout.splitlines()[-1] == "E2E: FAIL (interrupted)"
    assert left_running(run.pid) == []
    assert not answers(CONSOLE)
    assert list(temp.iterdir()) == []


def test_the_listener_gives_up_when_no_deny_comes() -> None:
    # Keepalives arrive forever; past its deadline the listener stops and heard nothing.
    keepalives = itertools.repeat(": still here\n")
    assert e2e_console.denied(keepalives, time.monotonic() - 1) == ""


def test_the_listener_reads_the_first_deny_before_its_deadline() -> None:
    lines = [": still here\n", "event: deny\n", "data: abc123\n"]
    assert e2e_console.denied(lines, time.monotonic() + 30) == "abc123"
