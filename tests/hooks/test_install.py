import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from knack import cli
from knack.home import user_home
from knack.hooks.install import (
    default_settings,
    HookInstallError,
    install_hook,
    pretool_command,
)
from test_adapters import event_for
from test_muse_conformance import undocumented_events
from test_pretool import (
    AIRFLOW_URL,
    deny_reason,
    hook_env,
    make_clone,
    SOURCE_URL,
    write_registry_file,
)

CLAUDE_MATCHER = "Write|Edit|MultiEdit"
MUSE_MATCHER = "write_file|edit_file|bash"
FOREIGN = {
    "matcher": "Write|Edit|MultiEdit",
    "hooks": [{"type": "command", "command": "lint"}],
}


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def pretool_entries(path: Path) -> list[dict[str, Any]]:
    return read(path)["hooks"]["PreToolUse"]


def write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_claude_code_install_writes_the_pretool_matcher(tmp_path: Path) -> None:
    settings = tmp_path / ".claude" / "settings.json"
    assert install_hook("claude-code", settings, "/py") is True
    [entry] = pretool_entries(settings)
    assert entry["matcher"] == CLAUDE_MATCHER
    assert entry["hooks"] == [{"type": "command", "command": pretool_command("/py")}]


def test_muse_install_writes_its_own_tool_names(tmp_path: Path) -> None:
    settings = tmp_path / "settings.json"
    install_hook("muse", settings, "/py")
    assert [e["matcher"] for e in pretool_entries(settings)] == [MUSE_MATCHER]
    assert read(settings)["schema_version"] == 1
    assert undocumented_events(settings) == []


def test_the_command_fails_open_and_runs_the_pretool_module() -> None:
    command = pretool_command("/my py/python")
    assert command.startswith("sh -c ")
    inner = shlex.split(command)[2]
    assert inner == "'/my py/python' -m knack.hooks.pretool || true"


def test_install_is_idempotent(tmp_path: Path) -> None:
    settings = tmp_path / "settings.json"
    install_hook("claude-code", settings, "/py")
    before = settings.read_text(encoding="utf-8")
    assert install_hook("claude-code", settings, "/py") is False
    assert settings.read_text(encoding="utf-8") == before


def test_reinstall_with_a_new_python_replaces_our_own_entry(tmp_path: Path) -> None:
    settings = tmp_path / "settings.json"
    install_hook("claude-code", settings, "/old/py")
    assert install_hook("claude-code", settings, "/new/py") is True
    [entry] = pretool_entries(settings)
    assert entry["hooks"][0]["command"] == pretool_command("/new/py")


def test_other_settings_and_other_matchers_are_kept(tmp_path: Path) -> None:
    settings = tmp_path / "settings.json"
    bash = {"matcher": "Bash", "hooks": [{"type": "command", "command": "audit"}]}
    write(settings, {"model": "x", "hooks": {"PreToolUse": [bash], "Stop": []}})
    install_hook("claude-code", settings, "/py")
    data = read(settings)
    assert data["model"] == "x" and data["hooks"]["Stop"] == []
    assert data["hooks"]["PreToolUse"][0] == bash
    assert len(data["hooks"]["PreToolUse"]) == 2


def test_a_foreign_entry_on_our_matcher_is_refused_untouched(tmp_path: Path) -> None:
    settings = tmp_path / "settings.json"
    write(settings, {"hooks": {"PreToolUse": [FOREIGN]}})
    before = settings.read_text(encoding="utf-8")
    with pytest.raises(HookInstallError, match="not knack's"):
        install_hook("claude-code", settings, "/py")
    assert settings.read_text(encoding="utf-8") == before


def test_unreadable_settings_are_refused_untouched(tmp_path: Path) -> None:
    settings = tmp_path / "settings.json"
    settings.write_text("{not json", encoding="utf-8")
    with pytest.raises(HookInstallError):
        install_hook("claude-code", settings, "/py")
    assert settings.read_text(encoding="utf-8") == "{not json"


def test_claude_code_settings_live_in_the_project_git_root(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "pkg").mkdir()
    path = default_settings("claude-code", tmp_path / "pkg")
    assert path == tmp_path.resolve() / ".claude" / "settings.json"


def test_muse_settings_live_in_the_user_config(tmp_path: Path) -> None:
    path = default_settings("muse", tmp_path)
    assert path == user_home() / ".config" / "muse" / "settings.json"


def test_cli_installs_for_claude_code(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    settings = tmp_path / "settings.json"
    argv = ["hooks", "install", "--agent", "claude-code", "--settings", str(settings)]
    assert cli.main(argv) == 0
    assert pretool_entries(settings)[0]["matcher"] == CLAUDE_MATCHER
    assert pretool_command(sys.executable) in settings.read_text(encoding="utf-8")
    assert "installed" in capsys.readouterr().out


def test_cli_says_when_already_installed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = [
        "hooks",
        "install",
        "--agent",
        "muse",
        "--settings",
        str(tmp_path / "s.json"),
    ]
    cli.main(argv)
    capsys.readouterr()
    assert cli.main(argv) == 0
    assert "already installed" in capsys.readouterr().out


def test_cli_refuses_a_foreign_entry_with_exit_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    settings = tmp_path / "settings.json"
    write(settings, {"hooks": {"PreToolUse": [FOREIGN]}})
    argv = ["hooks", "install", "--agent", "claude-code", "--settings", str(settings)]
    assert cli.main(argv) == 2
    assert "knack hooks:" in capsys.readouterr().err


def test_cli_rejects_an_unknown_agent() -> None:
    with pytest.raises(SystemExit) as raised:
        cli.main(["hooks", "install", "--agent", "cursor"])
    assert raised.value.code == 2


def test_the_installed_claude_code_command_denies_violating_py(tmp_path: Path) -> None:
    # End to end: what install wrote, run as Claude Code runs it, on a Write payload.
    clone = make_clone(tmp_path / "airflow", AIRFLOW_URL)
    settings = default_settings("claude-code", clone)
    install_hook("claude-code", settings, sys.executable)
    command = pretool_entries(settings)[0]["hooks"][0]["command"]
    event = json.dumps(event_for("Write", clone, str(clone / "dags.py")))
    env = hook_env(write_registry_file(tmp_path), tmp_path / "home")
    done = run_shell(command, event, clone, env)
    assert SOURCE_URL in deny_reason(json.loads(done.stdout))


def run_shell(
    command: str, stdin: str, cwd: Path, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    clean = {k: v for k, v in os.environ.items() if not k.startswith("KNACK_")}
    args = ["sh", "-c", command]
    return subprocess.run(
        args, input=stdin, capture_output=True, text=True, cwd=cwd, env=clean | env
    )
