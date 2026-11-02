from pathlib import Path

import pytest
from knack import cli
from knack.guard.check import GUARD_ERROR_REASON
from knack.hooks import pretool_guard
from knack.hooks.pretool_guard import decide
from knack.receipts.chain import load_receipts
from test_pretool import make_registry, raise_error, violating_write_event

README = Path(__file__).parents[2] / "README.md"
FAIL_OPEN_LINE = "If Knack itself fails, the agent proceeds and the failure is logged"


def crashed_guard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    # A violating edit under a Confirmed root, with the guard's check crashing.
    monkeypatch.setattr(pretool_guard, "check_file", raise_error(RuntimeError("boom")))
    receipts = tmp_path / "verdicts.jsonl"
    event = violating_write_event("new_dags.py", tmp_path)
    assert decide(event, make_registry(tmp_path), tmp_path / "log", receipts) is None
    return receipts


def test_a_guard_crash_lets_the_edit_through_and_logs_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    crashed_guard(tmp_path, monkeypatch)
    assert "RuntimeError: boom" in (tmp_path / "log").read_text()


def test_a_guard_crash_writes_a_guard_error_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    [receipt] = load_receipts(crashed_guard(tmp_path, monkeypatch))
    assert receipt.decision == "guard-error"
    assert GUARD_ERROR_REASON == "guard-error"


def test_knack_receipts_verify_accepts_the_guard_error_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    receipts = crashed_guard(tmp_path, monkeypatch)
    assert cli.main(["receipts", "verify", "--path", str(receipts)]) == 0
    assert capsys.readouterr().out == f"{receipts}: 1 receipt, chain intact\n"


def test_the_readme_states_fail_open_in_one_line() -> None:
    lines = README.read_text(encoding="utf-8").splitlines()
    assert [line for line in lines if FAIL_OPEN_LINE.lower() in line.lower()] != []
