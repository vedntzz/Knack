import subprocess
from pathlib import Path
from typing import Any

import pytest
from knack.guard import runner
from knack.guard.runner import GuardRunnerError, RuleMatch, scan_file_with_rule

RULE = Path(__file__).parents[2] / "knack/guard/rules/no-alias-sort-keys.yml"
FIXTURES = Path(__file__).parent / "fixtures"


def test_pre_fix_returns_both_aliased_keys_with_source_lines() -> None:
    matches = scan_file_with_rule(FIXTURES / "pre_fix.py", RULE)
    assert [(m.line, m.matched_text) for m in matches] == [
        (23, '"state"'),
        (23, '"start_date"'),
    ]
    assert all(isinstance(m, RuleMatch) for m in matches)
    assert {m.rule_id for m in matches} == {"no-alias-sort-keys"}


def test_fixed_returns_no_matches() -> None:
    assert scan_file_with_rule(FIXTURES / "fixed.py", RULE) == []


def test_missing_binary_raises_runner_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner, "AST_GREP", Path("/nonexistent/ast-grep"))
    with pytest.raises(GuardRunnerError):
        scan_file_with_rule(FIXTURES / "pre_fix.py", RULE)


def test_timeout_raises_runner_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def hang(*args: Any, **kwargs: Any) -> None:
        raise subprocess.TimeoutExpired(cmd="ast-grep", timeout=2)

    monkeypatch.setattr(runner.subprocess, "run", hang)
    with pytest.raises(GuardRunnerError):
        scan_file_with_rule(FIXTURES / "pre_fix.py", RULE)


def fake_ast_grep(
    monkeypatch: pytest.MonkeyPatch, returncode: int, stdout: str
) -> None:
    # Replaces the subprocess call with a canned ast-grep result.
    def canned(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, returncode, stdout=stdout, stderr="")

    monkeypatch.setattr(runner.subprocess, "run", canned)


def test_malformed_json_raises_runner_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_ast_grep(monkeypatch, 0, "not json")
    with pytest.raises(GuardRunnerError):
        scan_file_with_rule(FIXTURES / "pre_fix.py", RULE)


def test_unexpected_exit_code_raises_runner_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ast_grep(monkeypatch, 2, "[]")
    with pytest.raises(GuardRunnerError):
        scan_file_with_rule(FIXTURES / "pre_fix.py", RULE)


def test_valid_json_in_wrong_shape_raises_runner_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ast_grep(monkeypatch, 0, '[{"unexpected": 1}]')
    with pytest.raises(GuardRunnerError):
        scan_file_with_rule(FIXTURES / "pre_fix.py", RULE)
