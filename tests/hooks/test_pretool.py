import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from knack.hooks import pretool_guard
from knack.hooks.pretool_guard import decide
from knack.walk.registry import Registry, RegistryEntry

HOOK_FIXTURES = Path(__file__).parent / "fixtures"
GUARD_FIXTURES = Path(__file__).parents[1] / "guard" / "fixtures"
RULE = Path(__file__).parents[2] / "knack/guard/rules/no-alias-sort-keys.yml"
ROOT_JSON = GUARD_FIXTURES / "replay" / "root_75025.json"
REPO_ROOT = Path(__file__).parents[2]
SOURCE_URL = "https://github.com/apache/airflow/pull/75025"
AIRFLOW_URL = "https://github.com/apache/airflow.git"
FIXED_DICT = (
    '{"last_run_state": DagRun.state, "last_run_start_date": DagRun.start_date}'
)
ALIAS_DICT = '{"state": DagRun.state, "start_date": DagRun.start_date, "last_run_state": DagRun.state, "last_run_start_date": DagRun.start_date}'


def load_event(name: str) -> dict[str, Any]:
    # Hook fixtures are verbatim captured PreToolUse payloads.
    return json.loads((HOOK_FIXTURES / name).read_text(encoding="utf-8"))


def write_root(roots: Path, root_id: str, status: str) -> None:
    # The 75025 root under a new id and status.
    root = {**json.loads(ROOT_JSON.read_text()), "id": root_id, "status": status}
    roots.mkdir(exist_ok=True)
    (roots / f"{root_id}.json").write_text(json.dumps(root), encoding="utf-8")


def make_registry(directory: Path, statuses: dict[str, str] | None = None) -> Registry:
    # The alias rule bound to one root per id, each at its given status.
    statuses = statuses or {"root-75025": "Confirmed"}
    for root_id, status in statuses.items():
        write_root(directory / "roots", root_id, status)
    entry = RegistryEntry(rule=RULE, root_ids=list(statuses))
    return Registry(repo="apache/airflow", roots_dir=directory / "roots", rules=[entry])


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


def make_clone(path: Path, origin: str) -> Path:
    # An empty git repo whose origin names the given remote.
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "remote", "add", "origin", origin])
    return path


def write_registry_file(directory: Path) -> Path:
    # Relative roots_dir proves it resolves from the registry file.
    write_root(directory / "roots", "root-75025", "Confirmed")
    rules = [{"rule": str(RULE), "root_ids": ["root-75025"]}]
    registry = {"repo": "apache/airflow", "roots_dir": "roots", "rules": rules}
    (directory / "guard.json").write_text(json.dumps(registry), encoding="utf-8")
    return directory / "guard.json"


def run_pretool(
    stdin_text: str, cwd: Path, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[bytes]:
    # Runs the hook entry point the way Muse Code invokes it; KNACK_* only if given.
    args = [sys.executable, "-m", "knack.hooks.pretool"]
    clean = {k: v for k, v in os.environ.items() if not k.startswith("KNACK_")}
    payload = stdin_text.encode()
    return subprocess.run(
        args,
        input=payload,
        capture_output=True,
        timeout=60,
        cwd=cwd,
        env={**clean, **(env or {})},
    )


def hook_env(registry: Path, home: Path) -> dict[str, str]:
    return {"KNACK_REGISTRY": str(registry), "HOME": str(home)}


def home_log(home: Path) -> str:
    return (home / ".knack" / "guard_errors.log").read_text(encoding="utf-8")


def test_write_violating_content_denies_with_citation(tmp_path: Path) -> None:
    event = violating_write_event("new_dags.py", tmp_path)
    reason = deny_reason(decide(event, make_registry(tmp_path), tmp_path / "log"))
    assert SOURCE_URL in reason


def test_edit_reintroducing_alias_denies(tmp_path: Path) -> None:
    target = tmp_path / "dags.py"
    target.write_text(read_guard_fixture("fixed.py"), encoding="utf-8")
    event = load_event("edit_event.json")
    event["tool_input"].update(path="dags.py", find=FIXED_DICT, replace=ALIAS_DICT)
    event["cwd"] = str(tmp_path)
    reason = deny_reason(decide(event, make_registry(tmp_path), tmp_path / "log"))
    assert '"state"' in reason


def test_write_fixed_content_allows(tmp_path: Path) -> None:
    event = load_event("write_event.json")
    event["tool_input"].update(path="dags.py", content=read_guard_fixture("fixed.py"))
    event["cwd"] = str(tmp_path)
    assert decide(event, make_registry(tmp_path), tmp_path / "log") is None


def test_non_python_file_allows(tmp_path: Path) -> None:
    event = load_event("write_event.json")
    content = read_guard_fixture("replay/run3_public_dags.py")
    event["tool_input"].update(path="notes.txt", content=content)
    event["cwd"] = str(tmp_path)
    assert decide(event, make_registry(tmp_path), tmp_path / "log") is None


def test_unknown_tool_allows(tmp_path: Path) -> None:
    event = load_event("write_event.json")
    event["tool_name"] = "bash"
    event["cwd"] = str(tmp_path)
    assert decide(event, make_registry(tmp_path), tmp_path / "log") is None


def test_inferred_root_in_registry_never_denies(tmp_path: Path) -> None:
    registry = make_registry(tmp_path, {"root-75025": "Inferred"})
    event = violating_write_event("new_dags.py", tmp_path)
    assert decide(event, registry, tmp_path / "log") is None


def test_unknown_root_in_registry_never_denies(tmp_path: Path) -> None:
    registry = make_registry(tmp_path, {"root-75025": "Unknown"})
    event = violating_write_event("new_dags.py", tmp_path)
    assert decide(event, registry, tmp_path / "log") is None


def test_confirmed_root_beside_inferred_one_denies(tmp_path: Path) -> None:
    statuses = {"a-inferred": "Inferred", "b-confirmed": "Confirmed"}
    event = violating_write_event("new_dags.py", tmp_path)
    reason = decide(event, make_registry(tmp_path, statuses), tmp_path / "log")
    assert SOURCE_URL in deny_reason(reason)


def test_root_id_missing_from_store_allows(tmp_path: Path) -> None:
    registry = make_registry(tmp_path)
    entry = RegistryEntry(rule=RULE, root_ids=["not-in-store"])
    registry = registry.model_copy(update={"rules": [entry]})
    event = violating_write_event("new_dags.py", tmp_path)
    assert decide(event, registry, tmp_path / "log") is None


def test_guard_error_allows_and_is_logged(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(pretool_guard, "check_file", raise_error(RuntimeError("boom")))
    event = violating_write_event("new_dags.py", tmp_path)
    assert decide(event, make_registry(tmp_path), tmp_path / "log") is None
    assert "boom" in (tmp_path / "log").read_text()


def test_broken_registry_entry_is_logged(tmp_path: Path) -> None:
    registry = make_registry(tmp_path)
    entry = RegistryEntry(rule=tmp_path / "missing.yml", root_ids=["root-75025"])
    registry = registry.model_copy(update={"rules": [entry]})
    event = violating_write_event("new_dags.py", tmp_path)
    assert decide(event, registry, tmp_path / "log") is None
    assert "missing.yml" in (tmp_path / "log").read_text()


def test_malformed_event_is_logged(tmp_path: Path) -> None:
    event = {"tool_name": "write_file", "cwd": str(tmp_path)}
    assert decide(event, make_registry(tmp_path), tmp_path / "log") is None
    assert "KeyError" in (tmp_path / "log").read_text()


def test_edit_never_writes_target_file(tmp_path: Path) -> None:
    target = tmp_path / "dags.py"
    target.write_text(read_guard_fixture("fixed.py"), encoding="utf-8")
    event = load_event("edit_event.json")
    event["tool_input"].update(path="dags.py", find=FIXED_DICT, replace=ALIAS_DICT)
    event["cwd"] = str(tmp_path)
    decide(event, make_registry(tmp_path), tmp_path / "log")
    assert target.read_text(encoding="utf-8") == read_guard_fixture("fixed.py")


def test_matching_origin_denies_via_subprocess(tmp_path: Path) -> None:
    clone = make_clone(tmp_path / "airflow", AIRFLOW_URL)
    env = hook_env(write_registry_file(tmp_path), tmp_path / "home")
    done = run_pretool(json.dumps(violating_write_event("dags.py", clone)), clone, env)
    assert done.returncode == 0
    assert SOURCE_URL in deny_reason(hook_stdout_json(done))


def test_ssh_origin_of_same_repo_denies(tmp_path: Path) -> None:
    clone = make_clone(tmp_path / "airflow", "git@github.com:apache/airflow.git")
    env = hook_env(write_registry_file(tmp_path), tmp_path / "home")
    done = run_pretool(json.dumps(violating_write_event("dags.py", clone)), clone, env)
    assert SOURCE_URL in deny_reason(hook_stdout_json(done))


def test_mismatched_origin_stays_silent(tmp_path: Path) -> None:
    clone = make_clone(tmp_path / "other", "https://github.com/someone/other.git")
    env = hook_env(write_registry_file(tmp_path), tmp_path / "home")
    done = run_pretool(json.dumps(violating_write_event("dags.py", clone)), clone, env)
    assert (done.returncode, done.stdout, done.stderr) == (0, b"", b"")


def test_outside_any_git_repo_stays_silent(tmp_path: Path) -> None:
    (tmp_path / "plain").mkdir()
    env = hook_env(write_registry_file(tmp_path), tmp_path / "home")
    event = json.dumps(violating_write_event("dags.py", tmp_path / "plain"))
    done = run_pretool(event, tmp_path / "plain", env)
    assert (done.returncode, done.stdout) == (0, b"")


def test_subdirectory_of_matching_clone_denies(tmp_path: Path) -> None:
    clone = make_clone(tmp_path / "airflow", AIRFLOW_URL)
    (clone / "pkg").mkdir()
    env = hook_env(write_registry_file(tmp_path), tmp_path / "home")
    event = json.dumps(violating_write_event("dags.py", clone / "pkg"))
    done = run_pretool(event, tmp_path, env)
    assert SOURCE_URL in deny_reason(hook_stdout_json(done))


def test_bad_stdin_exits_zero_without_output(tmp_path: Path) -> None:
    done = run_pretool("not json{{{", tmp_path)
    assert (done.returncode, done.stdout) == (0, b"")


def write_home_registry(home: Path) -> Path:
    # The registry knack init or import puts in home for apache/airflow.
    directory = home / ".knack" / "registries" / "apache-airflow"
    directory.mkdir(parents=True)
    return write_registry_file(directory).rename(directory / "registry.json")


def test_unset_registry_env_guards_with_the_clone_home_registry(tmp_path: Path) -> None:
    write_home_registry(tmp_path / "home")
    clone = make_clone(tmp_path / "airflow", AIRFLOW_URL)
    event = json.dumps(violating_write_event("dags.py", clone))
    done = run_pretool(event, clone, {"HOME": str(tmp_path / "home")})
    assert SOURCE_URL in deny_reason(hook_stdout_json(done))


def test_unset_registry_env_without_a_home_registry_is_silent(tmp_path: Path) -> None:
    clone = make_clone(tmp_path / "airflow", AIRFLOW_URL)
    event = json.dumps(violating_write_event("dags.py", clone))
    done = run_pretool(event, clone, {"HOME": str(tmp_path / "home")})
    assert (done.returncode, done.stdout, done.stderr) == (0, b"", b"")
    assert not (tmp_path / "home" / ".knack").exists()


def test_unset_registry_env_outside_a_clone_is_silent(tmp_path: Path) -> None:
    write_home_registry(tmp_path / "home")
    event = json.dumps(violating_write_event("dags.py", tmp_path))
    done = run_pretool(event, tmp_path, {"HOME": str(tmp_path / "home")})
    assert (done.returncode, done.stdout, done.stderr) == (0, b"", b"")


def test_missing_registry_file_fails_open_and_logs_to_home(tmp_path: Path) -> None:
    clone = make_clone(tmp_path / "airflow", AIRFLOW_URL)
    env = hook_env(tmp_path / "nope.json", tmp_path / "home")
    done = run_pretool(json.dumps(violating_write_event("dags.py", clone)), clone, env)
    assert (done.returncode, done.stdout) == (0, b"")
    assert "nope.json" in home_log(tmp_path / "home")


# Blocks pydantic, then runs the hook module as Muse Code would.
BROKEN_IMPORT_RUNNER = (
    "import runpy, sys; sys.modules['pydantic'] = None; "
    "runpy.run_module('knack.hooks.pretool', run_name='__main__')"
)


def test_import_failure_reports_to_stderr_and_exits_zero() -> None:
    args = [sys.executable, "-c", BROKEN_IMPORT_RUNNER]
    done = subprocess.run(args, input=b"{}", capture_output=True, cwd=REPO_ROOT)
    assert (done.returncode, done.stdout) == (0, b"")
    assert b"knack guard-error: ModuleNotFoundError: import of pydantic" in done.stderr
