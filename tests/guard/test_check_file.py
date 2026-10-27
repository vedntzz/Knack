from pathlib import Path
from typing import Any

import pytest
from knack.contracts.models import Root
from knack.guard import check
from knack.guard.check import check_file
from knack.guard.runner import GuardRunnerError

RULE_ID = "no-alias-sort-keys"
RULE = Path(__file__).parents[2] / "knack/guard/rules/no-alias-sort-keys.yml"
FIXTURES = Path(__file__).parent / "fixtures"


def make_confirmed_root() -> Root:
    # Test-only root; values are illustrative, not quoted from a real thread.
    return Root.model_validate(
        {
            "id": "root-001",
            "title": "Sort keys are column names",
            "decision": "Sort keys must be real column names, never aliases.",
            "why": "Aliased sort keys let callers sort on columns they cannot see.",
            "decided_by": "Alice Chen",
            "source_url": "https://github.com/example/repo/pull/42",
            "quote": "Do not alias sort keys; map them to columns explicitly.",
            "status": "Confirmed",
        }
    )


def raise_error(error: Exception) -> Any:
    # Builds a stand-in that raises the given error when called.
    def raiser(*args: Any, **kwargs: Any) -> Any:
        raise error

    return raiser


def test_pre_fix_with_confirmed_root_denies_with_latency(tmp_path: Path) -> None:
    log = tmp_path / "guard_errors.log"
    verdict = check_file(
        FIXTURES / "pre_fix.py", RULE, RULE_ID, make_confirmed_root(), log
    )
    assert verdict.allowed is False
    assert verdict.latency_ms > 0


def test_fixed_allows(tmp_path: Path) -> None:
    log = tmp_path / "guard_errors.log"
    verdict = check_file(
        FIXTURES / "fixed.py", RULE, RULE_ID, make_confirmed_root(), log
    )
    assert verdict.allowed is True


def test_runner_error_allows_as_guard_error_and_logs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log = tmp_path / ".knack" / "guard_errors.log"
    error = GuardRunnerError("ast-grep did not run")
    monkeypatch.setattr(check, "scan_file_with_rule", raise_error(error))
    verdict = check_file(
        FIXTURES / "pre_fix.py", RULE, RULE_ID, make_confirmed_root(), log
    )
    assert verdict.allowed is True
    assert verdict.reason.startswith("guard-error")
    assert "GuardRunnerError: ast-grep did not run" in log.read_text()


def test_unexpected_build_error_allows_as_guard_error_and_logs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log = tmp_path / ".knack" / "guard_errors.log"
    monkeypatch.setattr(check, "build_verdict", raise_error(ValueError("bad root")))
    verdict = check_file(
        FIXTURES / "pre_fix.py", RULE, RULE_ID, make_confirmed_root(), log
    )
    assert verdict.allowed is True
    assert verdict.reason.startswith("guard-error")
    assert "ValueError: bad root" in log.read_text()


def test_unwritable_log_still_allows_as_guard_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # A regular file where the log directory should be makes the write fail.
    blocker = tmp_path / "not_a_dir"
    blocker.write_text("")
    log = blocker / "guard_errors.log"
    monkeypatch.setattr(check, "build_verdict", raise_error(ValueError("bad root")))
    verdict = check_file(
        FIXTURES / "pre_fix.py", RULE, RULE_ID, make_confirmed_root(), log
    )
    assert verdict.allowed is True
    assert verdict.reason.startswith("guard-error")
