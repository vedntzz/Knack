import io
import json
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import (
    clean_tree,
    FakeGitHub,
    FakeSpark,
    git,
    make_repo,
    merge_pr,
    STRUCTURAL,
)
from knack.watch import hook
from knack.watch.install import install_post_merge
from knack.watch.state import read_seen, write_seen
from test_watch_run import head, write_registry

Spawned = list[tuple[list[str], Path, Path]]
# Verbatim PostToolBatch stdin from muse exec; ptb_shell.json is its bash call batch.
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def repo(tmp_path: Path, isolated_git: None, monkeypatch: pytest.MonkeyPatch) -> Path:
    # A merged clone with its baseline before the merge; HOME is a temp dir.
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    repo = make_repo(tmp_path / "widgets")
    write_registry(tmp_path / "reg")
    write_seen(tmp_path / "reg", head(repo))
    return repo


@pytest.fixture
def spawned(monkeypatch: pytest.MonkeyPatch) -> Spawned:
    calls: Spawned = []

    def spawn(argv: list[str], cwd: Path, log: Path) -> None:
        calls.append((argv, cwd, log))

    monkeypatch.setattr(hook, "spawn_background", spawn)
    return calls


@pytest.fixture
def checked(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    # Records every git check while still running the real one.
    calls: list[Path] = []
    real = hook.pending_root

    def recording(cwd: Path, registry_path: Path) -> Path | None:
        calls.append(cwd)
        return real(cwd, registry_path)

    monkeypatch.setattr(hook, "pending_root", recording)
    return calls


def captured(name: str, cwd: Path, tools: list[str] | None = None) -> str:
    # A captured payload pointed at cwd, its tool names optionally replaced.
    event = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    event["cwd"] = str(cwd)
    template = event["tool_calls"][0]
    if tools is not None:
        event["tool_calls"] = [{**template, "tool_name": tool} for tool in tools]
    return json.dumps(event)


def registry(repo: Path) -> Path:
    return repo.parent / "reg" / "registry.json"


def post_merge(repo: Path) -> int:
    return hook.main(["post-merge", "--registry", str(registry(repo))])


def tool_batch(repo: Path, stdin_text: str) -> int:
    args = ["tool-batch", "--registry", str(registry(repo))]
    return hook.main(args, io.StringIO(stdin_text))


def test_post_merge_runs_in_the_foreground_with_the_log(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    pair = (FakeGitHub(clean_tree(repo.parent)), FakeSpark([STRUCTURAL]))
    monkeypatch.setattr(hook, "live_clients", lambda: pair)
    monkeypatch.chdir(repo)
    merge_pr(repo)
    assert post_merge(repo) == 0
    out = capsys.readouterr().out
    assert "knack watch acme/widgets: 1 merged PR: #9" in out and "[5/5] install" in out


def test_post_merge_without_tokens_explains_and_exits_0(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(repo)
    before = read_seen(repo.parent / "reg")
    merge_pr(repo)
    assert post_merge(repo) == 0
    assert "knack watch: GITHUB_TOKEN is not set" in capsys.readouterr().err
    assert read_seen(repo.parent / "reg") == before


def test_tool_batch_with_a_pending_merge_starts_a_background_run(
    repo: Path, spawned: Spawned, capsys: pytest.CaptureFixture[str]
) -> None:
    merge_pr(repo)
    assert tool_batch(repo, captured("ptb_shell.json", repo / "pkg")) == 0
    argv, cwd, log = spawned[0]
    assert argv[1:] == [
        "-m",
        "knack.watch.hook",
        "post-merge",
        "--registry",
        str(registry(repo)),
    ]
    assert cwd == repo and log == repo.parent / "reg" / "watch.log"
    assert capsys.readouterr() == ("", "")


def test_tool_batch_with_nothing_new_returns_without_spawning(
    repo: Path, spawned: Spawned, capsys: pytest.CaptureFixture[str]
) -> None:
    assert tool_batch(repo, captured("ptb_shell.json", repo)) == 0
    assert spawned == [] and capsys.readouterr() == ("", "")


@pytest.mark.parametrize("name", ["ptb_write_file.json", "ptb_reminder.json"])
def test_batches_without_a_shell_call_never_touch_git(
    repo: Path, spawned: Spawned, checked: list[Path], name: str
) -> None:
    merge_pr(repo)
    assert tool_batch(repo, captured(name, repo)) == 0
    assert checked == [] and spawned == []


@pytest.mark.parametrize("tool", ["shell", "bash", "bash_input", "code_exec"])
def test_every_shell_type_tool_triggers_the_check(
    repo: Path, spawned: Spawned, checked: list[Path], tool: str
) -> None:
    merge_pr(repo)
    assert tool_batch(repo, captured("ptb_write_file.json", repo, [tool])) == 0
    assert checked == [repo] and len(spawned) == 1


def test_one_shell_call_among_others_is_enough(
    repo: Path, spawned: Spawned, checked: list[Path]
) -> None:
    tools = ["write_file", "shell", "submit_reminder_decision"]
    assert tool_batch(repo, captured("ptb_write_file.json", repo, tools)) == 0
    assert checked == [repo]


@pytest.mark.parametrize("payload", [{}, {"tool_calls": None}, {"tool_calls": [1]}])
def test_payload_without_usable_tool_calls_is_skipped(
    repo: Path, spawned: Spawned, checked: list[Path], payload: dict[str, object]
) -> None:
    merge_pr(repo)
    assert tool_batch(repo, json.dumps({**payload, "cwd": str(repo)})) == 0
    assert checked == [] and spawned == []


def test_tool_batch_never_fails_the_agent(
    repo: Path, spawned: Spawned, capsys: pytest.CaptureFixture[str]
) -> None:
    assert tool_batch(repo, "not json") == 0
    assert spawned == [] and capsys.readouterr().out == ""
    assert (repo.parent / "home" / ".knack" / "guard_errors.log").exists()


def test_a_real_git_merge_fires_the_installed_hook(repo: Path) -> None:
    install_post_merge(repo, registry(repo), sys.executable)
    output = merge_pr(repo)
    assert "knack watch: GITHUB_TOKEN is not set" in output
    assert (
        git(repo, "log", "-1", "--format=%s").strip() == "Read blobs one at a time (#9)"
    )


def test_spawn_background_detaches_and_writes_the_log(tmp_path: Path) -> None:
    log = tmp_path / "reg" / "watch.log"
    hook.spawn_background([sys.executable, "-c", "print('hello')"], tmp_path, log)
    for _ in range(50):
        if log.exists() and "hello" in log.read_text():
            break
        subprocess.run([sys.executable, "-c", "import time; time.sleep(0.1)"])
    assert "hello" in log.read_text()
