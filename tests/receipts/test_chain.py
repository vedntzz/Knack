import hashlib
import json
import threading
from pathlib import Path
from typing import Any

import pytest
from knack.cli import main as knack_main
from knack.contracts.models import MatchedCode, Root, Verdict
from knack.receipts.chain import (
    append_receipt,
    GENESIS,
    guard_receipt,
    receipts_path,
    verify_chain,
)

QUOTE = "Sorting by an alias never worked; drop both keys."
NOW = "2026-10-30T12:00:00+00:00"


def root(status: str = "Confirmed") -> Root:
    fields: dict[str, Any] = {"id": "root-75025", "title": "t", "quote": QUOTE}
    fields |= {"source_url": "https://github.com/apache/airflow/pull/75025"}
    fields |= {"decision": "d", "why": "w", "decided_by": "maria"}
    return Root.model_validate(fields | {"status": status})


def deny() -> Verdict:
    return Verdict(
        allowed=False,
        reason="Knack blocked this edit.",
        rule_id="no-alias-sort-keys",
        root_ids=["root-75025"],
        latency_ms=12.5,
    )


def allow(reason: str = "no rule matched") -> Verdict:
    return Verdict(allowed=True, reason=reason, latency_ms=3.25)


def fields(verdict: Verdict, file: str = "/w/dags.py") -> dict[str, Any]:
    named = ("apache/airflow", file, "no-alias-sort-keys")
    return guard_receipt(*named, root(), verdict, NOW)


def lines(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def rewrite(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in records))


def canonical_hash(record: dict[str, Any]) -> str:
    # The documented recipe: sorted-key compact JSON of every field but hash.
    body = {key: value for key, value in record.items() if key != "hash"}
    text = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@pytest.fixture
def three(tmp_path: Path) -> Path:
    # A deny, an allow, then a guard error, chained in that order.
    path = tmp_path / "knack" / "verdicts.jsonl"
    for verdict in (deny(), allow(), allow("guard-error: RuntimeError")):
        append_receipt(path, fields(verdict))
    return path


def test_a_receipt_carries_every_field(three: Path) -> None:
    first = lines(three)[0]
    assert set(first) == {
        "time",
        "repo",
        "file",
        "rule_id",
        "root_ids",
        "decision",
        "quote_sha256",
        "latency_ms",
        "prev",
        "hash",
    }
    assert (first["time"], first["repo"], first["file"]) == (
        NOW,
        "apache/airflow",
        "/w/dags.py",
    )
    assert (first["rule_id"], first["root_ids"]) == (
        "no-alias-sort-keys",
        ["root-75025"],
    )
    assert (first["decision"], first["latency_ms"]) == ("deny", 12.5)


def test_allow_and_guard_error_are_receipted_too(three: Path) -> None:
    assert [r["decision"] for r in lines(three)] == ["deny", "allow", "guard-error"]


def test_the_quote_is_hashed_never_stored(three: Path) -> None:
    expected = hashlib.sha256(QUOTE.encode("utf-8")).hexdigest()
    assert lines(three)[0]["quote_sha256"] == expected
    assert QUOTE not in three.read_text()


def test_no_root_means_no_root_ids_and_no_quote_hash() -> None:
    record = guard_receipt("a/b", "/w/x.py", "r", None, allow(), NOW)
    assert (record["root_ids"], record["quote_sha256"]) == ([], None)


def test_each_line_is_chained_to_the_one_before(three: Path) -> None:
    records = lines(three)
    assert [r["prev"] for r in records] == [GENESIS] + [r["hash"] for r in records[:2]]
    assert [r["hash"] for r in records] == [canonical_hash(r) for r in records]
    assert GENESIS == "0" * 64


def test_an_intact_chain_verifies(three: Path) -> None:
    report = verify_chain(three)
    assert (report.receipts, report.broken_line, report.problem) == (3, None, None)


def test_a_missing_file_is_an_empty_intact_chain(tmp_path: Path) -> None:
    report = verify_chain(tmp_path / "none.jsonl")
    assert (report.receipts, report.broken_line) == (0, None)


def test_an_edited_field_breaks_its_own_line(three: Path) -> None:
    records = lines(three)
    records[0]["decision"] = "allow"
    rewrite(three, records)
    report = verify_chain(three)
    assert (report.broken_line, report.receipts) == (1, 0)
    assert "hash" in str(report.problem)


def test_a_rehashed_edit_breaks_the_next_line(three: Path) -> None:
    records = lines(three)
    records[0]["decision"] = "allow"
    records[0]["hash"] = canonical_hash(records[0])
    rewrite(three, records)
    report = verify_chain(three)
    assert (report.broken_line, report.receipts) == (2, 1)
    assert "prev" in str(report.problem)


def test_a_deleted_line_breaks_the_chain(three: Path) -> None:
    records = lines(three)
    rewrite(three, [records[0], records[2]])
    assert verify_chain(three).broken_line == 2


def test_reordered_lines_break_the_chain(three: Path) -> None:
    records = lines(three)
    rewrite(three, [records[1], records[0], records[2]])
    assert verify_chain(three).broken_line == 1


@pytest.mark.parametrize("junk", ["not json", "{}", ""])
def test_a_line_that_is_not_a_receipt_breaks_the_chain(three: Path, junk: str) -> None:
    text = three.read_text().splitlines()
    three.write_text("\n".join([text[0], junk, *text[1:]]) + "\n")
    report = verify_chain(three)
    assert (report.broken_line, report.problem) == (2, "not a receipt")


def test_appending_resumes_the_chain_in_a_later_process(three: Path) -> None:
    before = lines(three)[-1]["hash"]
    append_receipt(three, fields(deny()))
    assert lines(three)[-1]["prev"] == before
    assert verify_chain(three).receipts == 4


def test_concurrent_appends_keep_one_unbroken_chain(tmp_path: Path) -> None:
    path = tmp_path / "verdicts.jsonl"
    workers = [
        threading.Thread(
            target=append_receipt, args=(path, fields(allow(), f"/w/{n}.py"))
        )
        for n in range(24)
    ]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()
    report = verify_chain(path)
    assert (report.receipts, report.broken_line) == (24, None)


def test_receipts_live_in_the_home_knack_folder(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("KNACK_HOME", raising=False)
    assert receipts_path() == tmp_path / ".knack" / "verdicts.jsonl"


def test_cli_verify_passes_an_intact_chain(
    three: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert knack_main(["receipts", "verify", "--path", str(three)]) == 0
    assert "3 receipts" in capsys.readouterr().out


def test_cli_verify_fails_a_broken_chain_naming_the_line(
    three: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    records = lines(three)
    rewrite(three, records[1:])
    assert knack_main(["receipts", "verify", "--path", str(three)]) == 1
    assert "line 1" in capsys.readouterr().out


def test_cli_verify_defaults_to_the_home_receipts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("KNACK_HOME", raising=False)
    append_receipt(receipts_path(), fields(deny()))
    assert knack_main(["receipts", "verify"]) == 0
    assert "1 receipt" in capsys.readouterr().out


def test_cli_verify_on_an_unreadable_path_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert knack_main(["receipts", "verify", "--path", str(tmp_path)]) == 2
    assert "knack receipts" in capsys.readouterr().err


LATER = {"branch", "session_id", "matched"}


def matched_deny() -> Verdict:
    found = [MatchedCode(line=23, text='"state"')]
    return deny().model_copy(update={"matched": found})


def test_later_fields_are_kept_and_hashed_when_set(tmp_path: Path) -> None:
    path = tmp_path / "verdicts.jsonl"
    named = ("apache/airflow", "/w/dags.py", "no-alias-sort-keys")
    record = guard_receipt(
        *named, root(), matched_deny(), NOW, branch="fix-sort", session_id="s-1"
    )
    append_receipt(path, record)
    [line] = lines(path)
    assert (line["branch"], line["session_id"]) == ("fix-sort", "s-1")
    assert line["matched"] == [{"line": 23, "text": '"state"'}]
    assert line["hash"] == canonical_hash(line)
    assert verify_chain(path).broken_line is None


def test_unset_later_fields_are_left_off_the_line(three: Path) -> None:
    # Receipts written before these fields existed hash exactly as they did.
    assert not LATER & set(lines(three)[0])
    assert verify_chain(three).broken_line is None


def test_an_edited_branch_breaks_its_line(tmp_path: Path) -> None:
    path = tmp_path / "verdicts.jsonl"
    append_receipt(path, fields(deny()) | {"branch": "fix-sort"})
    records = lines(path)
    records[0]["branch"] = "main"
    rewrite(path, records)
    assert verify_chain(path).broken_line == 1
