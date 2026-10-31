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


def test_deny_message_ends_with_how_to_dispute(tmp_path: Path) -> None:
    event = violating_write_event("new_dags.py", tmp_path)
    reason = deny_reason(decide(event, make_registry(tmp_path), tmp_path / "log"))
    assert reason.splitlines()[-1] == 'To dispute: knack argue "<your reason>"'


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


def receipt_lines(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_a_deny_is_receipted(tmp_path: Path) -> None:
    receipts = tmp_path / "verdicts.jsonl"
    event = violating_write_event("new_dags.py", tmp_path)
    deny_reason(decide(event, make_registry(tmp_path), tmp_path / "log", receipts))
    [receipt] = receipt_lines(receipts)
    assert (receipt["decision"], receipt["repo"]) == ("deny", "apache/airflow")
    assert (receipt["rule_id"], receipt["root_ids"]) == (
        "no-alias-sort-keys",
        ["root-75025"],
    )
    assert receipt["file"] == str(tmp_path.resolve() / "new_dags.py")
    assert receipt["latency_ms"] > 0 and len(receipt["quote_sha256"]) == 64


def test_an_allow_is_receipted(tmp_path: Path) -> None:
    receipts = tmp_path / "verdicts.jsonl"
    event = load_event("write_event.json")
    event["tool_input"].update(path="dags.py", content=read_guard_fixture("fixed.py"))
    event["cwd"] = str(tmp_path)
    assert decide(event, make_registry(tmp_path), tmp_path / "log", receipts) is None
    assert [r["decision"] for r in receipt_lines(receipts)] == ["allow"]


def test_an_advisory_allow_is_receipted_with_its_root(tmp_path: Path) -> None:
    receipts = tmp_path / "verdicts.jsonl"
    registry = make_registry(tmp_path, {"root-75025": "Inferred"})
    event = violating_write_event("new_dags.py", tmp_path)
    assert decide(event, registry, tmp_path / "log", receipts) is None
    [receipt] = receipt_lines(receipts)
    assert (receipt["decision"], receipt["root_ids"]) == ("allow", ["root-75025"])


def test_a_guard_error_is_receipted_by_rule_file_name(tmp_path: Path) -> None:
    receipts = tmp_path / "verdicts.jsonl"
    registry = make_registry(tmp_path)
    entry = RegistryEntry(rule=tmp_path / "missing.yml", root_ids=["root-75025"])
    registry = registry.model_copy(update={"rules": [entry]})
    event = violating_write_event("new_dags.py", tmp_path)
    assert decide(event, registry, tmp_path / "log", receipts) is None
    [receipt] = receipt_lines(receipts)
    assert (receipt["decision"], receipt["rule_id"]) == ("guard-error", "missing.yml")


def test_untouched_files_get_no_receipt(tmp_path: Path) -> None:
    receipts = tmp_path / "verdicts.jsonl"
    event = load_event("write_event.json")
    event["tool_input"].update(path="notes.txt", content="x")
    event["cwd"] = str(tmp_path)
    assert decide(event, make_registry(tmp_path), tmp_path / "log", receipts) is None
    assert not receipts.exists()


def test_a_failed_receipt_never_changes_the_verdict(tmp_path: Path) -> None:
    # The receipts path is a folder, so every append fails.
    receipts = tmp_path / "verdicts.jsonl"
    receipts.mkdir()
    event = violating_write_event("new_dags.py", tmp_path)
    reason = decide(event, make_registry(tmp_path), tmp_path / "log", receipts)
    assert SOURCE_URL in deny_reason(reason)
    assert "verdicts.jsonl" in (tmp_path / "log").read_text()


def test_a_crashing_receipt_never_changes_an_allow(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(pretool_guard, "append_receipt", raise_error(MemoryError("x")))
    event = load_event("write_event.json")
    event["tool_input"].update(path="dags.py", content=read_guard_fixture("fixed.py"))
    event["cwd"] = str(tmp_path)
    receipts = tmp_path / "verdicts.jsonl"
    assert decide(event, make_registry(tmp_path), tmp_path / "log", receipts) is None
    assert "MemoryError" in (tmp_path / "log").read_text()


def test_the_hook_receipts_into_home(tmp_path: Path) -> None:
    clone = make_clone(tmp_path / "airflow", AIRFLOW_URL)
    env = hook_env(write_registry_file(tmp_path), tmp_path / "home")
    done = run_pretool(json.dumps(violating_write_event("dags.py", clone)), clone, env)
    assert SOURCE_URL in deny_reason(hook_stdout_json(done))
    receipts = tmp_path / "home" / ".knack" / "verdicts.jsonl"
    assert [r["decision"] for r in receipt_lines(receipts)] == ["deny"]


PRE_FIX_LIST = '"next_dagrun", "state", "start_date"]'
# Fixtures from apache/airflow PR #75774 (Apache-2.0): base msgraph.py, its rule and
# Confirmed root, and the import edit the bench agent's fix opened with (blocked pre-KN-33).
MSGRAPH_BASE = HOOK_FIXTURES / "msgraph_75774_base.py.txt"
MSGRAPH_HEAD = HOOK_FIXTURES / "msgraph_75774_head.py.txt"


def edit_event_on(target: Path, find: str, replace: str) -> dict[str, Any]:
    event = load_event("edit_event.json")
    event["tool_input"].update(path=target.name, find=find, replace=replace)
    event["cwd"] = str(target.parent)
    return event


def write_event_on(target: Path, content: str) -> dict[str, Any]:
    event = load_event("write_event.json")
    event["tool_input"].update(path=target.name, content=content)
    event["cwd"] = str(target.parent)
    return event


def pre_fix_file(tmp_path: Path, text: str | None = None) -> Path:
    # A file that already holds the old violation before the agent touches it.
    target = tmp_path / "dags.py"
    target.write_text(text or read_guard_fixture("pre_fix.py"), encoding="utf-8")
    return target


def registry_75774(directory: Path) -> Registry:
    roots = directory / "roots"
    roots.mkdir()
    root = json.loads((HOOK_FIXTURES / "root_75774.json").read_text())
    (roots / f"{root['id']}.json").write_text(json.dumps(root), encoding="utf-8")
    entry = RegistryEntry(rule=HOOK_FIXTURES / "rule_75774.yml", root_ids=[root["id"]])
    return Registry(repo="apache/airflow", roots_dir=roots, rules=[entry])


def msgraph_file(tmp_path: Path) -> Path:
    target = tmp_path / "msgraph.py"
    target.write_text(MSGRAPH_BASE.read_text(encoding="utf-8"), encoding="utf-8")
    return target


def test_editing_a_file_with_an_old_violation_is_allowed(tmp_path: Path) -> None:
    event = edit_event_on(pre_fix_file(tmp_path), "def get_dags(", "def list_dags(")
    assert decide(event, make_registry(tmp_path), tmp_path / "log") is None


def test_rewriting_a_file_keeping_its_old_violation_is_allowed(tmp_path: Path) -> None:
    content = read_guard_fixture("pre_fix.py") + "\n# touched\n"
    event = write_event_on(pre_fix_file(tmp_path), content)
    assert decide(event, make_registry(tmp_path), tmp_path / "log") is None


def test_adding_a_new_violation_beside_an_old_one_is_denied(tmp_path: Path) -> None:
    # "state" is already there; only the added "start_date" is cited.
    text = read_guard_fixture("pre_fix.py").replace(
        PRE_FIX_LIST, '"next_dagrun", "state"]'
    )
    target = pre_fix_file(tmp_path, text)
    event = edit_event_on(target, '"state"]', '"state", "start_date"]')
    reason = deny_reason(decide(event, make_registry(tmp_path), tmp_path / "log"))
    assert '"start_date"' in reason and '"state" (line' not in reason


def test_the_75774_fix_opening_edit_passes(tmp_path: Path) -> None:
    edit = json.loads((HOOK_FIXTURES / "edit_75774_imports.json").read_text())
    event = edit_event_on(msgraph_file(tmp_path), edit["find"], edit["replace"])
    assert decide(event, registry_75774(tmp_path), tmp_path / "log") is None


def test_the_75774_upstream_fix_passes(tmp_path: Path) -> None:
    event = write_event_on(
        msgraph_file(tmp_path), MSGRAPH_HEAD.read_text(encoding="utf-8")
    )
    assert decide(event, registry_75774(tmp_path), tmp_path / "log") is None


def outside_write_event(clone: Path, path: str) -> dict[str, Any]:
    # The agent works in the clone; the path may land outside it.
    return violating_write_event(path, clone)


def test_write_outside_the_git_root_is_silent_and_unreceipted(tmp_path: Path) -> None:
    clone = make_clone(tmp_path / "airflow", AIRFLOW_URL)
    receipts, log = tmp_path / "verdicts.jsonl", tmp_path / "log"
    event = outside_write_event(clone, str(tmp_path / "scratch" / "dags.py"))
    assert decide(event, make_registry(tmp_path), log, receipts, clone) is None
    assert not receipts.exists() and not log.exists()


def test_relative_escape_from_the_git_root_is_silent(tmp_path: Path) -> None:
    clone = make_clone(tmp_path / "airflow", AIRFLOW_URL)
    receipts = tmp_path / "verdicts.jsonl"
    event = outside_write_event(clone, "../dags.py")
    assert (
        decide(event, make_registry(tmp_path), tmp_path / "log", receipts, clone)
        is None
    )
    assert not receipts.exists()


def test_edit_outside_the_git_root_never_reads_the_file(tmp_path: Path) -> None:
    # A missing file outside the clone is not an error to log: it is not ours.
    clone = make_clone(tmp_path / "airflow", AIRFLOW_URL)
    log = tmp_path / "log"
    event = edit_event_on(tmp_path / "gone" / "dags.py", FIXED_DICT, ALIAS_DICT)
    event["cwd"] = str(clone)
    event["tool_input"]["path"] = str(tmp_path / "gone" / "dags.py")
    assert (
        decide(event, make_registry(tmp_path), log, tmp_path / "r.jsonl", clone) is None
    )
    assert not log.exists()


def test_write_inside_the_git_root_still_denies_and_receipts(tmp_path: Path) -> None:
    clone = make_clone(tmp_path / "airflow", AIRFLOW_URL)
    receipts = tmp_path / "verdicts.jsonl"
    event = outside_write_event(clone, str(clone / "pkg" / "dags.py"))
    reason = decide(event, make_registry(tmp_path), tmp_path / "log", receipts, clone)
    assert SOURCE_URL in deny_reason(reason)
    assert [r["decision"] for r in receipt_lines(receipts)] == ["deny"]


def test_the_hook_allows_a_tmp_write_silently_via_subprocess(tmp_path: Path) -> None:
    clone = make_clone(tmp_path / "airflow", AIRFLOW_URL)
    env = hook_env(write_registry_file(tmp_path), tmp_path / "home")
    event = outside_write_event(clone, str(tmp_path / "scratch" / "dags.py"))
    done = run_pretool(json.dumps(event), clone, env)
    assert (done.returncode, done.stdout, done.stderr) == (0, b"", b"")
    assert not (tmp_path / "home" / ".knack").exists()
