from pathlib import Path

import pytest
from knack.roots.corrections import (
    append_correction,
    Correction,
    corrections_path,
    few_shot_block,
    recent_corrections,
)
from registry_fixture import root

AT = "2026-10-29T12:00:00+00:00"


def correction(n: int, action: str = "reject") -> Correction:
    before = root(f"widgets-{n}-1", "Inferred")
    status = "Unknown" if action == "reject" else "Confirmed"
    after = before.model_copy(update={"status": status})
    reason = f"reason {n}" if action == "reject" else None
    fields = {"root_id": before.id, "action": action, "before": before, "after": after}
    return Correction.model_validate({**fields, "reason": reason, "by": "bo", "at": AT})


def test_corrections_live_in_the_home_knack_folder(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("KNACK_HOME", raising=False)
    assert corrections_path() == tmp_path / ".knack" / "corrections.jsonl"


def test_recent_corrections_are_the_last_five_oldest_first(tmp_path: Path) -> None:
    log = tmp_path / "c.jsonl"
    for n in range(1, 8):
        append_correction(correction(n), log)
    assert [c.root_id for c in recent_corrections(log)] == [
        f"widgets-{n}-1" for n in range(3, 8)
    ]


def test_no_file_means_no_corrections(tmp_path: Path) -> None:
    assert recent_corrections(tmp_path / "missing.jsonl") == []


def test_a_damaged_line_is_skipped_not_fatal(tmp_path: Path) -> None:
    log = tmp_path / "c.jsonl"
    append_correction(correction(1), log)
    with log.open("a") as handle:
        handle.write("{not json\n")
    append_correction(correction(2), log)
    assert [c.root_id for c in recent_corrections(log)] == [
        "widgets-1-1",
        "widgets-2-1",
    ]


def test_no_corrections_means_no_block() -> None:
    assert few_shot_block([]) == ""


def test_rejected_extraction_is_shown_with_its_reason() -> None:
    block = few_shot_block([correction(4)])
    assert "REJECTED" in block and "reason 4" in block
    assert "quote of widgets-4-1" in block
    assert "alternative of widgets-4-1" in block
    assert "decision of widgets-4-1" in block


def test_confirmed_extraction_is_a_positive_example() -> None:
    block = few_shot_block([correction(5, "confirm")])
    assert "- CONFIRMED: " in block and "- REJECTED" not in block
    assert "quote of widgets-5-1" in block


def test_block_keeps_correction_order_and_ends_before_the_pr_text() -> None:
    block = few_shot_block([correction(1), correction(2, "confirm")])
    assert block.index("widgets-1-1") < block.index("widgets-2-1")
    assert block.endswith("\n\n")
