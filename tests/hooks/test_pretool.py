import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from knack.hooks import pretool_guard
from knack.hooks.pretool_guard import decide

HOOK_FIXTURES = Path(__file__).parent / "fixtures"
GUARD_FIXTURES = Path(__file__).parents[1] / "guard" / "fixtures"
RULE = Path(__file__).parents[2] / "knack/guard/rules/no-alias-sort-keys.yml"
ROOT_JSON = GUARD_FIXTURES / "replay" / "root_75025.json"
REPO_ROOT = Path(__file__).parents[2]
SOURCE_URL = "https://github.com/apache/airflow/pull/75025"
FIXED_DICT = (
    '{"last_run_state": DagRun.state, "last_run_start_date": DagRun.start_date}'
)
ALIAS_DICT = '{"state": DagRun.state, "start_date": DagRun.start_date, "last_run_state": DagRun.state, "last_run_start_date": DagRun.start_date}'


def load_event(name: str) -> dict[str, Any]:
    # Hook fixtures are verbatim captured PreToolUse payloads.
    return json.loads((HOOK_FIXTURES / name).read_text(encoding="utf-8"))


def make_registry() -> list[dict[str, Any]]:
    # Absolute paths keep unit tests independent of the event cwd.
    return [{"rule": str(RULE), "root": str(ROOT_JSON)}]


def read_guard_fixture(name: str) -> str:
    return (GUARD_FIXTURES / name).read_text(encoding="utf-8")


def violating_write_event(filename: str, cwd: Path) -> dict[str, Any]:
    # A new-file write carrying the replayed violating edit.
    event = load_event("write_event.json")
    content = read_guard_fixture("replay/run3_public_dags.py")
    event["tool_input"].update(path=filename, content=content)
    event["cwd"] = str(cwd)
    return event


def deny_reason(result: dict[str, Any] | None) -> str:
    # Unpacks the deny envelope the hook contract requires.
    assert result is not None
    output = result["hookSpecificOutput"]
    assert output["hookEventName"] == "PreToolUse"
    assert output["permissionDecision"] == "deny"
    return str(output["permissionDecisionReason"])


def hook_stdout_json(done: subprocess.CompletedProcess[bytes]) -> dict[str, Any]:
    # Empty stdout means the hook failed open; surface its stderr, not a JSONDecodeError.
    stderr = done.stderr.decode(errors="replace")
    assert done.stdout, f"hook failed open (exit {done.returncode}); stderr:\n{stderr}"
    return json.loads(done.stdout)


def raise_error(error: Exception) -> Any:
    # Builds a stand-in that raises the given error when called.
    def raiser(*args: Any, **kwargs: Any) -> Any:
        raise error

    return raiser


def run_pretool(
    stdin_text: str, cwd: Path = REPO_ROOT
) -> subprocess.CompletedProcess[bytes]:
    # Runs the hook entry point the way Muse Code invokes it.
    args = [sys.executable, "-m", "knack.hooks.pretool"]
    payload = stdin_text.encode()
    return subprocess.run(args, input=payload, capture_output=True, timeout=60, cwd=cwd)


def error_log(root: Path) -> str:
    # Reads the guard error log the hook writes under the repo root.
    return (root / ".knack" / "guard_errors.log").read_text(encoding="utf-8")


def test_write_violating_content_denies_with_citation(tmp_path: Path) -> None:
    event = violating_write_event("new_dags.py", tmp_path)
    reason = deny_reason(decide(event, make_registry(), tmp_path))
    assert SOURCE_URL in reason


def test_edit_reintroducing_alias_denies(tmp_path: Path) -> None:
    target = tmp_path / "dags.py"
    target.write_text(read_guard_fixture("fixed.py"), encoding="utf-8")
    event = load_event("edit_event.json")
    event["tool_input"].update(path="dags.py", find=FIXED_DICT, replace=ALIAS_DICT)
    event["cwd"] = str(tmp_path)
    reason = deny_reason(decide(event, make_registry(), tmp_path))
    assert '"state"' in reason


def test_write_fixed_content_allows(tmp_path: Path) -> None:
    event = load_event("write_event.json")
    event["tool_input"].update(path="dags.py", content=read_guard_fixture("fixed.py"))
    event["cwd"] = str(tmp_path)
    assert decide(event, make_registry(), tmp_path) is None


def test_non_python_file_allows(tmp_path: Path) -> None:
    event = load_event("write_event.json")
    content = read_guard_fixture("replay/run3_public_dags.py")
    event["tool_input"].update(path="notes.txt", content=content)
    event["cwd"] = str(tmp_path)
    assert decide(event, make_registry(), tmp_path) is None


def test_unknown_tool_allows(tmp_path: Path) -> None:
    event = load_event("write_event.json")
    event["tool_name"] = "bash"
    event["cwd"] = str(tmp_path)
    assert decide(event, make_registry(), tmp_path) is None


def test_guard_error_allows(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(pretool_guard, "check_file", raise_error(RuntimeError("boom")))
    event = violating_write_event("new_dags.py", tmp_path)
    assert decide(event, make_registry(), tmp_path) is None


def test_bad_stdin_exits_zero_without_output() -> None:
    done = run_pretool("not json{{{")
    assert done.returncode == 0
    assert done.stdout == b""


def test_deny_via_subprocess_emits_valid_json() -> None:
    event = violating_write_event("new_dags.py", REPO_ROOT)
    done = run_pretool(json.dumps(event))
    assert done.returncode == 0
    reason = deny_reason(hook_stdout_json(done))
    assert SOURCE_URL in reason


def test_hook_run_from_other_directory_still_denies(tmp_path: Path) -> None:
    event = violating_write_event("new_dags.py", REPO_ROOT)
    done = run_pretool(json.dumps(event), cwd=tmp_path)
    assert done.returncode == 0
    assert SOURCE_URL in deny_reason(hook_stdout_json(done))


def test_registry_resolves_from_repo_root_when_event_cwd_is_subdir() -> None:
    event = violating_write_event("new_dags.py", REPO_ROOT / "tests")
    done = run_pretool(json.dumps(event))
    assert SOURCE_URL in deny_reason(hook_stdout_json(done))


def test_missing_guard_json_fails_open_with_stderr_report(tmp_path: Path) -> None:
    event = violating_write_event("new_dags.py", tmp_path)
    done = run_pretool(json.dumps(event), cwd=tmp_path)
    assert (done.returncode, done.stdout) == (0, b"")
    assert b".knack/guard.json" in done.stderr


def test_broken_registry_entry_is_logged(tmp_path: Path) -> None:
    event = violating_write_event("new_dags.py", tmp_path)
    registry = [{"rule": "missing.yml", "root": str(ROOT_JSON)}]
    assert decide(event, registry, tmp_path) is None
    assert "missing.yml" in error_log(tmp_path)


def test_malformed_event_is_logged(tmp_path: Path) -> None:
    event = {"tool_name": "write_file", "cwd": str(tmp_path)}
    assert decide(event, make_registry(), tmp_path) is None
    assert "KeyError" in error_log(tmp_path)


def test_guard_error_is_logged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(pretool_guard, "check_file", raise_error(RuntimeError("boom")))
    decide(violating_write_event("new_dags.py", tmp_path), make_registry(), tmp_path)
    assert "boom" in error_log(tmp_path)


def test_edit_never_writes_target_file(tmp_path: Path) -> None:
    target = tmp_path / "dags.py"
    target.write_text(read_guard_fixture("fixed.py"), encoding="utf-8")
    event = load_event("edit_event.json")
    event["tool_input"].update(path="dags.py", find=FIXED_DICT, replace=ALIAS_DICT)
    event["cwd"] = str(tmp_path)
    decide(event, make_registry(), tmp_path)
    assert target.read_text(encoding="utf-8") == read_guard_fixture("fixed.py")


HOOK_COMMAND = (
    'sh -c \'cd "$(git rev-parse --show-toplevel)"'
    " && .venv/bin/python -m knack.hooks.pretool || true'"
)
# Blocks pydantic, then runs the hook module as Muse Code would.
BROKEN_IMPORT_RUNNER = (
    "import runpy, sys; sys.modules['pydantic'] = None; "
    "runpy.run_module('knack.hooks.pretool', run_name='__main__')"
)


def configured_command() -> str:
    # Reads the single PreToolUse command from .muse/hooks.json.
    config = json.loads((REPO_ROOT / ".muse" / "hooks.json").read_text())
    return config["hooks"]["PreToolUse"][0]["hooks"][0]["command"]


def test_import_failure_reports_to_stderr_and_exits_zero() -> None:
    args = [sys.executable, "-c", BROKEN_IMPORT_RUNNER]
    done = subprocess.run(args, input=b"{}", capture_output=True, cwd=REPO_ROOT)
    assert (done.returncode, done.stdout) == (0, b"")
    assert b"knack guard-error: ModuleNotFoundError: import of pydantic" in done.stderr


def test_hook_command_is_machine_independent() -> None:
    assert configured_command() == HOOK_COMMAND


def test_hook_command_passes_stdin_through_sh_from_subdir() -> None:
    payload = json.dumps(violating_write_event("new_dags.py", REPO_ROOT)).encode()
    done = subprocess.run(
        configured_command(),
        shell=True,
        input=payload,
        capture_output=True,
        timeout=60,
        cwd=REPO_ROOT / "tests",
    )
    assert SOURCE_URL in deny_reason(hook_stdout_json(done))


def test_hook_command_outside_git_repo_exits_zero_silently(tmp_path: Path) -> None:
    payload = json.dumps(violating_write_event("new_dags.py", tmp_path)).encode()
    done = subprocess.run(
        configured_command(),
        shell=True,
        input=payload,
        capture_output=True,
        timeout=60,
        cwd=tmp_path,
    )
    assert (done.returncode, done.stdout) == (0, b"")


def write_registry(directory: Path) -> Path:
    # A registry outside any repo, with absolute rule and root paths.
    registry = directory / ".knack" / "guard.json"
    registry.parent.mkdir(parents=True)
    registry.write_text(json.dumps(make_registry()), encoding="utf-8")
    return registry


def run_pretool_with_registry(
    stdin_text: str, registry: str, cwd: Path
) -> subprocess.CompletedProcess[bytes]:
    # Runs the hook with KNACK_REGISTRY pointing at the given file.
    args = [sys.executable, "-m", "knack.hooks.pretool"]
    env = {**os.environ, "KNACK_REGISTRY": registry}
    payload = stdin_text.encode()
    return subprocess.run(
        args, input=payload, capture_output=True, timeout=60, cwd=cwd, env=env
    )


def test_env_registry_denies_outside_any_repo(tmp_path: Path) -> None:
    registry = write_registry(tmp_path / "home")
    event = violating_write_event("new_dags.py", tmp_path)
    done = run_pretool_with_registry(json.dumps(event), str(registry), tmp_path)
    assert SOURCE_URL in deny_reason(hook_stdout_json(done))


def test_env_registry_overrides_repo_guard_json(tmp_path: Path) -> None:
    registry = tmp_path / "empty.json"
    registry.write_text("[]", encoding="utf-8")
    event = violating_write_event("new_dags.py", REPO_ROOT)
    done = run_pretool_with_registry(json.dumps(event), str(registry), REPO_ROOT)
    assert (done.returncode, done.stdout) == (0, b"")


def test_env_registry_missing_file_fails_open_with_stderr(tmp_path: Path) -> None:
    missing = str(tmp_path / "nope.json")
    event = violating_write_event("new_dags.py", REPO_ROOT)
    done = run_pretool_with_registry(json.dumps(event), missing, REPO_ROOT)
    assert (done.returncode, done.stdout) == (0, b"")
    assert missing.encode() in done.stderr


def test_env_registry_relative_paths_resolve_from_its_home(tmp_path: Path) -> None:
    home = tmp_path / "home"
    registry = write_registry(home)
    entry = {"rule": str(RULE), "root": "roots/r.json"}
    registry.write_text(json.dumps([entry]), encoding="utf-8")
    (home / "roots").mkdir()
    (home / "roots" / "r.json").write_text(ROOT_JSON.read_text(), encoding="utf-8")
    event = violating_write_event("new_dags.py", tmp_path)
    done = run_pretool_with_registry(json.dumps(event), str(registry), tmp_path)
    assert SOURCE_URL in deny_reason(hook_stdout_json(done))


def test_unset_env_keeps_repo_walk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KNACK_REGISTRY", raising=False)
    event = violating_write_event("new_dags.py", REPO_ROOT / "tests")
    assert SOURCE_URL in deny_reason(pretool_guard.run_hook(json.dumps(event)))


def test_empty_env_keeps_repo_walk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KNACK_REGISTRY", "")
    event = violating_write_event("new_dags.py", REPO_ROOT / "tests")
    assert SOURCE_URL in deny_reason(pretool_guard.run_hook(json.dumps(event)))
