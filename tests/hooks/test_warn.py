import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from knack.hooks import warn_guard
from knack.index import cache

Json = dict[str, "Json"] | list["Json"] | str | int | float | bool | None
FORBIDDEN_RULE = "id: no-forbidden\nlanguage: python\nseverity: error\nrule:\n  pattern: forbidden()\n"
AIRFLOW_URL = "https://github.com/apache/airflow.git"


def write_repo(root: Path, origin: str = AIRFLOW_URL) -> Path:
    # A clone whose pkg/a.py helper() holds the call the rule matches.
    repo = root / "repo"
    (repo / "pkg").mkdir(parents=True)
    (repo / "pkg" / "a.py").write_text("def helper():\n    forbidden()\n")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", origin])
    return repo


def write_registry(root: Path) -> Path:
    # Rule and roots paths are relative to prove registry-relative resolution.
    (root / "rules").mkdir()
    (root / "rules" / "no-forbidden.yml").write_text(FORBIDDEN_RULE)
    registry = root / "registry" / "team.json"
    registry.parent.mkdir()
    rules = [{"rule": "../rules/no-forbidden.yml", "root_ids": ["r-1"]}]
    body = {"repo": "apache/airflow", "roots_dir": "../roots", "rules": rules}
    registry.write_text(json.dumps(body))
    return registry


def root_dict(status: str) -> dict[str, Any]:
    return {
        "id": "r-1",
        "title": "title r-1",
        "decision": "decision r-1",
        "why": "why r-1",
        "decided_by": "owner r-1",
        "source_url": "https://example.test/pull/42",
        "quote": "quote r-1",
        "status": status,
        "rejected_alternative": "rejected r-1",
    }


def write_roots(root: Path, status: str) -> Path:
    # A roots dir holding only r-1 at the given status.
    roots = root / "roots"
    roots.mkdir()
    (roots / "r-1.json").write_text(json.dumps(root_dict(status)))
    return roots


def empty_roots(root: Path) -> Path:
    # An existing roots dir with no root files at all.
    roots = root / "roots"
    roots.mkdir()
    return roots


def bad_registry(root: Path) -> Path:
    # A registry file whose JSON never parses.
    registry = root / "registry" / "team.json"
    registry.parent.mkdir()
    registry.write_text("{invalid")
    return registry


def home_log(root: Path) -> Path:
    return root / "home" / ".knack" / "guard_errors.log"


def set_env(monkeypatch: pytest.MonkeyPatch, root: Path, registry: Path) -> None:
    # Home lives under tmp so the index cache and log never touch the real one.
    monkeypatch.setenv("HOME", str(root / "home"))
    monkeypatch.setenv("KNACK_REGISTRY", str(registry))


def harness(root: Path, status: str) -> tuple[Path, Path, Path]:
    # Repo, registry and roots wired so a.py helper() cites r-1.
    return write_repo(root), write_registry(root), write_roots(root, status)


def warn_env(root: Path, registry: Path) -> dict[str, str]:
    return {"KNACK_REGISTRY": str(registry), "HOME": str(root / "home")}


def warn_event(prompt: str, cwd: Path) -> dict[str, Any]:
    # Minimal verbatim-shape UserPromptSubmit payload.
    return {"hook_event_name": "UserPromptSubmit", "prompt": prompt, "cwd": str(cwd)}


def run_warn(
    stdin_text: str, cwd: Path, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[bytes]:
    # Strips KNACK_* env unless given, so ambient config never leaks in.
    args = [sys.executable, "-m", "knack.hooks.warn"]
    clean = {k: v for k, v in os.environ.items() if not k.startswith("KNACK_")}
    full_env = {**clean, **(env or {})}
    payload = stdin_text.encode()
    return subprocess.run(
        args, input=payload, capture_output=True, timeout=120, cwd=cwd, env=full_env
    )


def single_line_json(raw: bytes) -> dict[str, Any]:
    # Stdout must be exactly one JSON line: the proven injectable shape.
    assert raw.endswith(b"\n") and not raw.endswith(b"\n\n")
    parsed = json.loads(raw)
    assert raw == (json.dumps(parsed) + "\n").encode()
    return parsed


def warn_context(parsed: dict[str, Any]) -> str:
    # Unpacks the nested envelope the hook contract requires.
    assert set(parsed) == {"hookSpecificOutput"}
    inner = parsed["hookSpecificOutput"]
    assert set(inner) == {"hookEventName", "additionalContext"}
    assert inner["hookEventName"] == "UserPromptSubmit"
    return str(inner["additionalContext"])


def all_keys(node: Json) -> set[str]:
    # Collects every JSON key recursively; string values are never keys.
    if isinstance(node, dict):
        return set(node) | {k for v in node.values() for k in all_keys(v)}
    if isinstance(node, list):
        return {k for item in node for k in all_keys(item)}
    return set()


def test_named_file_with_confirmed_root_emits_exact_nested_json(
    tmp_path: Path,
) -> None:
    repo, registry, _ = harness(tmp_path, "Confirmed")
    event = json.dumps(warn_event("Clean up pkg/a.py please", repo))
    done = run_warn(event, repo, warn_env(tmp_path, registry))
    assert done.returncode == 0
    context = warn_context(single_line_json(done.stdout))
    assert "decision r-1" in context and "rejected r-1" in context
    assert "quote r-1" in context and "https://example.test/pull/42" in context


def test_subdirectory_session_indexes_from_git_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, registry, _ = harness(tmp_path, "Confirmed")
    set_env(monkeypatch, tmp_path, registry)
    event = json.dumps(warn_event("Clean up pkg/a.py please", repo / "pkg"))
    result = warn_guard.run_hook(event)
    assert result is not None and "decision r-1" in warn_context(result)


def test_mismatched_origin_stays_silent_without_indexing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = write_repo(tmp_path, "https://github.com/someone/other.git")
    registry, _ = write_registry(tmp_path), write_roots(tmp_path, "Confirmed")
    set_env(monkeypatch, tmp_path, registry)
    monkeypatch.setattr(cache, "build_index", raise_on_call)
    assert (
        warn_guard.run_hook(json.dumps(warn_event("Clean up pkg/a.py", repo))) is None
    )


def test_mismatched_origin_is_silent_on_stdout_and_stderr(tmp_path: Path) -> None:
    repo = write_repo(tmp_path, "https://github.com/someone/other.git")
    registry, _ = write_registry(tmp_path), write_roots(tmp_path, "Confirmed")
    event = json.dumps(warn_event("Clean up pkg/a.py please", repo))
    done = run_warn(event, repo, warn_env(tmp_path, registry))
    assert (done.returncode, done.stdout, done.stderr) == (0, b"", b"")


def test_outside_any_git_repo_stays_silent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry, _ = write_registry(tmp_path), write_roots(tmp_path, "Confirmed")
    set_env(monkeypatch, tmp_path, registry)
    assert warn_guard.run_hook(json.dumps(warn_event("a.py", tmp_path))) is None


def test_inferred_only_root_stays_silent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, registry, _ = harness(tmp_path, "Inferred")
    set_env(monkeypatch, tmp_path, registry)
    event = json.dumps(warn_event("Clean up pkg/a.py please", repo))
    assert warn_guard.run_hook(event) is None


def test_no_roots_stays_silent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = write_repo(tmp_path)
    registry, _ = write_registry(tmp_path), empty_roots(tmp_path)
    set_env(monkeypatch, tmp_path, registry)
    event = json.dumps(warn_event("Clean up pkg/a.py please", repo))
    assert warn_guard.run_hook(event) is None


def test_malformed_stdin_exits_zero_without_output(tmp_path: Path) -> None:
    done = run_warn("not json{{{", tmp_path)
    assert (done.returncode, done.stdout) == (0, b"")


def write_home_registry(root: Path, status: str) -> Path:
    # The registry knack init or import puts in home for apache/airflow.
    home = root / "home" / ".knack" / "registries" / "apache-airflow"
    (home / "rules").mkdir(parents=True)
    (home / "rules" / "no-forbidden.yml").write_text(FORBIDDEN_RULE)
    write_roots(home, status)
    rules = [{"rule": "rules/no-forbidden.yml", "root_ids": ["r-1"]}]
    body = {"repo": "apache/airflow", "roots_dir": "roots", "rules": rules}
    (home / "registry.json").write_text(json.dumps(body))
    return home / "registry.json"


def test_missing_registry_env_warns_from_the_clone_home_registry(
    tmp_path: Path,
) -> None:
    repo = write_repo(tmp_path)
    write_home_registry(tmp_path, "Confirmed")
    event = json.dumps(warn_event("Clean up pkg/a.py please", repo))
    done = run_warn(event, repo, {"HOME": str(tmp_path / "home")})
    assert "quote r-1" in warn_context(single_line_json(done.stdout))


def test_missing_registry_env_without_a_home_registry_is_silent(
    tmp_path: Path,
) -> None:
    repo = write_repo(tmp_path)
    event = json.dumps(warn_event("Clean up pkg/a.py please", repo))
    done = run_warn(event, repo, {"HOME": str(tmp_path / "home")})
    assert (done.returncode, done.stdout, done.stderr) == (0, b"", b"")


def test_output_never_contains_a_decision_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, registry, _ = harness(tmp_path, "Confirmed")
    set_env(monkeypatch, tmp_path, registry)
    event = json.dumps(warn_event("Clean up pkg/a.py please", repo))
    result = warn_guard.run_hook(event)
    assert result is not None and "decision" not in all_keys(result)


def test_walk_failure_logs_to_home_not_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _ = write_repo(tmp_path), write_roots(tmp_path, "Confirmed")
    set_env(monkeypatch, tmp_path, bad_registry(tmp_path))
    event = json.dumps(warn_event("Clean up pkg/a.py please", repo))
    assert warn_guard.run_hook(event) is None
    assert not (repo / ".knack").exists()
    assert "ValidationError" in home_log(tmp_path).read_text()


def test_broken_registry_stays_silent_on_stdout(tmp_path: Path) -> None:
    repo, _ = write_repo(tmp_path), write_roots(tmp_path, "Confirmed")
    event = json.dumps(warn_event("Clean up pkg/a.py please", repo))
    done = run_warn(event, repo, warn_env(tmp_path, bad_registry(tmp_path)))
    assert (done.returncode, done.stdout) == (0, b"")


def test_inferred_stays_silent_on_stdout(tmp_path: Path) -> None:
    repo, registry, _ = harness(tmp_path, "Inferred")
    event = json.dumps(warn_event("Clean up pkg/a.py please", repo))
    done = run_warn(event, repo, warn_env(tmp_path, registry))
    assert (done.returncode, done.stdout) == (0, b"")


def raise_on_call(*args: Any, **kwargs: Any) -> Any:
    raise AssertionError("indexed a repo whose origin does not match")


def warns_file(root: Path) -> Path:
    return root / "home" / ".knack" / "warns.jsonl"


def test_an_injected_warning_is_recorded_for_the_console(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, registry, _ = harness(tmp_path, "Confirmed")
    set_env(monkeypatch, tmp_path, registry)
    event = warn_event("Clean up pkg/a.py please", repo) | {"session_id": "s-1"}
    result = warn_guard.run_hook(json.dumps(event))
    assert result is not None
    [record] = [
        json.loads(line) for line in warns_file(tmp_path).read_text().splitlines()
    ]
    assert record["context"] == warn_context(result)
    assert (record["session_id"], record["repo"]) == ("s-1", "apache/airflow")
    assert record["root"] == str(repo.resolve()) and record["time"]


def test_silence_records_no_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, registry, _ = harness(tmp_path, "Inferred")
    set_env(monkeypatch, tmp_path, registry)
    warn_guard.run_hook(json.dumps(warn_event("Clean up pkg/a.py please", repo)))
    assert not warns_file(tmp_path).exists()


def test_a_failed_warning_record_never_changes_the_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, registry, _ = harness(tmp_path, "Confirmed")
    set_env(monkeypatch, tmp_path, registry)
    warns_file(tmp_path).mkdir(parents=True)
    result = warn_guard.run_hook(json.dumps(warn_event("Clean up pkg/a.py", repo)))
    assert result is not None and "decision r-1" in warn_context(result)
    assert "warns.jsonl" in home_log(tmp_path).read_text()
