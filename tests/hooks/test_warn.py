import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from knack.hooks import warn_guard

Json = dict[str, "Json"] | list["Json"] | str | int | float | bool | None
FORBIDDEN_RULE = "id: no-forbidden\nlanguage: python\nseverity: error\nrule:\n  pattern: forbidden()\n"


def write_repo(root: Path) -> Path:
    # A repo whose a.py helper() holds the call the rule matches.
    repo = root / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("def helper():\n    forbidden()\n")
    return repo


def write_registry(root: Path) -> Path:
    # The rule path is relative to prove registry-relative resolution.
    (root / "rules").mkdir()
    (root / "rules" / "no-forbidden.yml").write_text(FORBIDDEN_RULE)
    registry = root / "registry" / "team.json"
    registry.parent.mkdir()
    entry = [{"rule": "../rules/no-forbidden.yml", "root_ids": ["r-1"]}]
    registry.write_text(json.dumps(entry))
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


def set_home_env(
    monkeypatch: pytest.MonkeyPatch, home: Path, registry: Path, roots: Path
) -> None:
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("KNACK_WALK_REGISTRY", str(registry))
    monkeypatch.setenv("KNACK_ROOTS_DIR", str(roots))


def harness(root: Path, status: str) -> tuple[Path, Path, Path]:
    # Repo, registry and roots wired so a.py helper() cites r-1.
    return write_repo(root), write_registry(root), write_roots(root, status)


def warn_env(registry: Path, roots: Path) -> dict[str, str]:
    return {"KNACK_WALK_REGISTRY": str(registry), "KNACK_ROOTS_DIR": str(roots)}


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
    repo, registry, roots = harness(tmp_path, "Confirmed")
    event = json.dumps(warn_event("Clean up a.py please", repo))
    done = run_warn(event, repo, warn_env(registry, roots))
    assert done.returncode == 0
    context = warn_context(single_line_json(done.stdout))
    assert "decision r-1" in context and "rejected r-1" in context
    assert "quote r-1" in context and "https://example.test/pull/42" in context


def test_inferred_only_root_stays_silent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, registry, roots = harness(tmp_path, "Inferred")
    monkeypatch.setenv("KNACK_WALK_REGISTRY", str(registry))
    monkeypatch.setenv("KNACK_ROOTS_DIR", str(roots))
    event = json.dumps(warn_event("Clean up a.py please", repo))
    assert warn_guard.run_hook(event) is None


def test_no_roots_stays_silent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = write_repo(tmp_path)
    registry = write_registry(tmp_path)
    roots = empty_roots(tmp_path)
    monkeypatch.setenv("KNACK_WALK_REGISTRY", str(registry))
    monkeypatch.setenv("KNACK_ROOTS_DIR", str(roots))
    event = json.dumps(warn_event("Clean up a.py please", repo))
    assert warn_guard.run_hook(event) is None


def test_malformed_stdin_exits_zero_without_output(tmp_path: Path) -> None:
    done = run_warn("not json{{{", tmp_path)
    assert (done.returncode, done.stdout) == (0, b"")


def test_missing_registry_env_exits_zero_with_stderr_note(tmp_path: Path) -> None:
    repo = write_repo(tmp_path)
    done = run_warn(json.dumps(warn_event("Clean up a.py please", repo)), repo)
    assert (done.returncode, done.stdout) == (0, b"")
    assert b"KNACK_WALK_REGISTRY" in done.stderr


def test_output_never_contains_a_decision_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, registry, roots = harness(tmp_path, "Confirmed")
    monkeypatch.setenv("KNACK_WALK_REGISTRY", str(registry))
    monkeypatch.setenv("KNACK_ROOTS_DIR", str(roots))
    event = json.dumps(warn_event("Clean up a.py please", repo))
    result = warn_guard.run_hook(event)
    assert result is not None and "decision" not in all_keys(result)


def test_walk_failure_logs_to_home_not_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, roots = write_repo(tmp_path), write_roots(tmp_path, "Confirmed")
    registry = bad_registry(tmp_path)
    set_home_env(monkeypatch, tmp_path / "home", registry, roots)
    event = json.dumps(warn_event("Clean up a.py please", repo))
    assert warn_guard.run_hook(event) is None
    assert not (repo / ".knack").exists()
    assert "ValidationError" in home_log(tmp_path).read_text()


def test_broken_registry_stays_silent_on_stdout(tmp_path: Path) -> None:
    repo = write_repo(tmp_path)
    roots = write_roots(tmp_path, "Confirmed")
    registry = bad_registry(tmp_path)
    event = json.dumps(warn_event("Clean up a.py please", repo))
    done = run_warn(event, repo, warn_env(registry, roots))
    assert (done.returncode, done.stdout) == (0, b"")


def test_inferred_stays_silent_on_stdout(tmp_path: Path) -> None:
    repo, registry, roots = harness(tmp_path, "Inferred")
    event = json.dumps(warn_event("Clean up a.py please", repo))
    done = run_warn(event, repo, warn_env(registry, roots))
    assert (done.returncode, done.stdout) == (0, b"")
