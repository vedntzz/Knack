from pathlib import Path

import pytest
from knack.dispute.rulings import (
    append_ruling,
    load_rulings,
    RulingRecord,
    rulings_for,
    rulings_path,
)

DENY_A = "a" * 64
DENY_B = "b" * 64


def record(receipt_hash: str = DENY_A, objection: str = "Alias it.") -> RulingRecord:
    return RulingRecord(
        time="2026-10-31T12:00:00+00:00",
        receipt_hash=receipt_hash,
        objection=objection,
        decision="hold",
        reply="We chose not to alias.",
        cited_quotes=["rather than aliasing them"],
        model="muse-spark-1.3",
    )


def test_rulings_live_beside_the_receipts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("KNACK_HOME", raising=False)
    assert rulings_path() == tmp_path / ".knack" / "rulings.jsonl"


def test_appended_rulings_load_back_in_order(tmp_path: Path) -> None:
    path = tmp_path / "deep" / "rulings.jsonl"
    first, second = record(objection="first"), record(objection="second")
    append_ruling(path, first)
    append_ruling(path, second)
    assert load_rulings(path) == [first, second]
    assert len(path.read_text().splitlines()) == 2


def test_a_missing_file_has_no_rulings(tmp_path: Path) -> None:
    assert load_rulings(tmp_path / "rulings.jsonl") == []


def test_torn_and_foreign_lines_are_skipped(tmp_path: Path) -> None:
    path = tmp_path / "rulings.jsonl"
    append_ruling(path, record())
    with path.open("a") as handle:
        handle.write('{"not": "a ruling"}\n{"torn\n')
    assert load_rulings(path) == [record()]


def test_rulings_for_keeps_only_that_denys(tmp_path: Path) -> None:
    path = tmp_path / "rulings.jsonl"
    append_ruling(path, record(DENY_A, "one"))
    append_ruling(path, record(DENY_B, "other deny"))
    append_ruling(path, record(DENY_A, "two"))
    found = rulings_for(path, DENY_A)
    assert [r.objection for r in found] == ["one", "two"]


def test_a_ruling_with_no_model_is_allowed(tmp_path: Path) -> None:
    # An escalation decided without asking Spark names no model.
    unasked = record().model_copy(update={"decision": "escalate", "model": None})
    append_ruling(tmp_path / "r.jsonl", unasked)
    assert load_rulings(tmp_path / "r.jsonl")[0].model is None
