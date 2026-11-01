import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from knack import cli
from knack.dispute.rulings import load_rulings
from knack.dispute.second import Second
from knack.miss.cases import cases_dir, EditCase, load_cases
from knack.miss.provisional import load_provisional
from knack.miss.selfcheck import load_checks
from knack.miss.sources import Places
from knack.receipts.chain import append_receipt, Receipt
from knack.receipts.edits import edits_dir, EditSnapshot, save_edit
from test_cli_argue import clone, home_of, QUOTE_75025, RESTATES_REJECTED, spark_says

__all__ = ["clone"]
# Taken before conftest's autouse fixture swaps it for a credential error.
LIVE_SECOND_PORTS = getattr(cli, "_second_ports")
OPEN_MODEL = "meta-models/muse-spark-open-1026"
NOT_COVERED = "The quotes say nothing about pinned clients."
OBJECTION = "A pinned client can only send sort=state; the alias is needed until March."
BEFORE, AFTER = "x = 1\n", "x = 1\nalias = 2\n"


class FakeJudge:
    # Spark Open with one fixed answer; records every prompt it was asked.
    def __init__(self, model: str, answer: str) -> None:
        self.model, self.answer, self.prompts = model, answer, list[str]()

    def ask(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.answer


def ruling(decision: str, reply: str, quotes: list[str]) -> str:
    return json.dumps({"decision": decision, "reply": reply, "cited_quotes": quotes})


def snapshot_receipt(clone: Path, rule_id: str = "airflow-75025") -> Receipt:
    # A deny on dags.py whose edit snapshot was kept, as the hook writes it.
    receipts = home_of(clone) / ".knack" / "verdicts.jsonl"
    edit = EditSnapshot(file=str(clone / "dags.py"), before=BEFORE, after=AFTER)
    digest = save_edit(edits_dir(receipts), edit)
    fields = {"time": datetime.now(timezone.utc).isoformat(), "repo": "apache/airflow"}
    fields |= {"file": str(clone / "dags.py"), "rule_id": rule_id, "root_ids": []}
    fields |= {"decision": "deny", "quote_sha256": None, "latency_ms": 1.0}
    return append_receipt(receipts, fields | {"edit_sha256": digest})


class Ports:
    # Fake Spark Open, wired in where argue builds its live one; there is no loop to wire.
    def __init__(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, answer: str
    ) -> None:
        self.registry = tmp_path / "reg" / "registry.json"
        self.open = FakeJudge(OPEN_MODEL, answer)
        self.checks = tmp_path / "reg" / "self_checks.jsonl"
        receipts = tmp_path / "home" / ".knack" / "verdicts.jsonl"
        places = Places(receipts, edits_dir(receipts), [], tmp_path / "tickets.jsonl")
        self.second = Second(self.open, places, self.registry, print)
        monkeypatch.setattr(cli, "_second_ports", self.ports)

    def ports(self, registry: Path) -> Second:
        return self.second

    def cases(self) -> list[EditCase]:
        return load_cases(cases_dir(self.registry), "airflow-75025")


def test_both_escalate_record_a_provisional_case_and_never_run_the_loop(
    clone: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    spark_says(monkeypatch, "escalate", NOT_COVERED, [])
    ports = Ports(tmp_path, monkeypatch, ruling("escalate", "Not covered.", []))
    denied = snapshot_receipt(clone)
    assert cli.main(["argue", OBJECTION]) == 0
    case = load_provisional(ports.registry, denied.hash)
    assert case is not None and ports.cases() == []
    assert (case.kind, case.rule_id, case.file) == (
        "must-pass",
        "airflow-75025",
        "dags.py",
    )
    assert (case.before, case.after) == (BEFORE, AFTER)
    assert denied.hash in case.source and "auto" in case.source
    assert [a.model for a in case.answers] == ["muse-spark-1.3", OPEN_MODEL]
    out = capsys.readouterr().out
    assert "provisional" in out and f"knack resolve {denied.hash} allow" in out
    assert "recompil" not in out and "kept airflow-75025" not in out


def test_the_agreement_is_logged_with_the_provisional_cases_key(
    clone: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spark_says(monkeypatch, "escalate", NOT_COVERED, [])
    ports = Ports(tmp_path, monkeypatch, ruling("escalate", "Not covered.", []))
    denied = snapshot_receipt(clone)
    cli.main(["argue", OBJECTION])
    [check] = load_checks(ports.checks)
    case = load_provisional(ports.registry, denied.hash)
    assert case is not None and (check.trigger, check.case_key) == ("argue", case.key)


def test_an_objection_never_builds_a_compiler_or_a_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Only Spark Open is needed; GitHub and the compiler are never even constructed.
    def refuse(*args: object) -> object:
        raise AssertionError("argue must not build the miss loop")

    monkeypatch.setattr(cli, "live_clients", refuse)
    monkeypatch.setattr(cli, "record_and_recompile", refuse)

    def partner(name: str) -> FakeJudge:
        return FakeJudge(OPEN_MODEL, "")

    monkeypatch.setattr(cli, "partner_client", partner)
    second: Second = LIVE_SECOND_PORTS(tmp_path / "reg" / "registry.json")
    assert second.judge.model == OPEN_MODEL


def test_spark_open_holding_is_logged_only(
    clone: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spark_says(monkeypatch, "escalate", NOT_COVERED, [])
    held = ruling("hold", "Covered.", ["rather than aliasing them"])
    ports = Ports(tmp_path, monkeypatch, held)
    snapshot_receipt(clone)
    assert cli.main(["argue", OBJECTION]) == 0
    assert ports.cases() == [] and not (ports.registry.parent / "provisional").exists()
    [check] = load_checks(ports.checks)
    assert (check.trigger, check.case_key) == ("argue", None)
    assert [a.answer for a in check.answers][1] == held


def test_spark_open_is_asked_independently_of_sparks_reply(
    clone: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spark_says(monkeypatch, "escalate", NOT_COVERED, [])
    ports = Ports(tmp_path, monkeypatch, ruling("escalate", "Not covered.", []))
    snapshot_receipt(clone)
    cli.main(["argue", OBJECTION])
    [prompt] = ports.open.prompts
    assert OBJECTION in prompt and QUOTE_75025 in prompt
    assert NOT_COVERED not in prompt and "escalate" in prompt


def test_a_hold_is_never_put_to_spark_open(
    clone: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spark_says(
        monkeypatch, "hold", "We chose not to alias.", ["rather than aliasing them"]
    )
    ports = Ports(tmp_path, monkeypatch, ruling("escalate", "x", []))
    snapshot_receipt(clone)
    assert cli.main(["argue", RESTATES_REJECTED]) == 0
    assert ports.open.prompts == []


def test_an_escalation_spark_did_not_choose_is_never_put_to_spark_open(
    clone: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Spark held with a fabricated quote; the escalation is knack's, not Spark's.
    spark_says(monkeypatch, "hold", "Never alias.", ["Aliasing is forbidden."])
    ports = Ports(tmp_path, monkeypatch, ruling("escalate", "x", []))
    snapshot_receipt(clone)
    assert cli.main(["argue", RESTATES_REJECTED]) == 0
    assert ports.open.prompts == []


def test_a_deny_without_an_edit_snapshot_asks_nobody_and_says_so(
    clone: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from test_cli_argue import receipt

    spark_says(monkeypatch, "escalate", NOT_COVERED, [])
    ports = Ports(tmp_path, monkeypatch, ruling("escalate", "x", []))
    receipt(home_of(clone), clone / "dags.py", "airflow-75025")
    assert cli.main(["argue", OBJECTION]) == 0
    assert ports.open.prompts == []
    assert "no edit snapshot" in capsys.readouterr().err


def test_missing_keys_skip_the_second_opinion_but_keep_the_ruling(
    clone: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    spark_says(monkeypatch, "escalate", NOT_COVERED, [])
    snapshot_receipt(clone)
    assert cli.main(["argue", OBJECTION]) == 0
    assert "BASETEN_API_KEY is not set" in capsys.readouterr().err
    [recorded] = load_rulings(home_of(clone) / ".knack" / "rulings.jsonl")
    assert recorded.decision == "escalate"
