from functools import partial
from pathlib import Path

import pytest
from gate_fakes import FakeGitHub, FakeSpark
from knack.pipeline.models import Alternative, Decision, Extraction
from knack.roots.correct import confirm_root, reject_root
from knack.roots.corrections import append_correction, Correction
from knack.roots.gate import Gate, gated, still_extracted
from registry_fixture import make_registry, raw_entries, root, status_on_disk

AT = "2026-10-29T12:00:00+00:00"


@pytest.fixture
def registry(tmp_path: Path) -> Path:
    return make_registry(tmp_path / "reg")


@pytest.fixture
def log(tmp_path: Path) -> Path:
    return tmp_path / "home" / ".knack" / "corrections.jsonl"


def extraction(alternative: str, quote: str, verbatim: bool = True) -> Extraction:
    said = Alternative(alternative=alternative, quote=quote, verbatim=verbatim)
    decision = Decision(decision="d", rejected_alternatives=[said])
    return Extraction(number=3, title="PR 3", decisions=[decision])


def test_same_alternative_and_verbatim_quote_is_still_extracted() -> None:
    confirmed = root("widgets-3-1", "Confirmed")
    found = extraction("alternative of widgets-3-1", "quote of widgets-3-1")
    assert still_extracted(confirmed, found)


def test_case_and_spacing_of_the_alternative_do_not_matter() -> None:
    confirmed = root("widgets-3-1", "Confirmed")
    found = extraction("  Alternative  OF widgets-3-1 ", "quote of widgets-3-1")
    assert still_extracted(confirmed, found)


def test_a_reworded_alternative_with_the_same_quote_survives() -> None:
    confirmed = root("widgets-3-1", "Confirmed")
    found = extraction("aliasing it instead", "quote of widgets-3-1")
    assert still_extracted(confirmed, found)


def test_a_reworded_alternative_whose_quote_holds_the_old_one_survives() -> None:
    # The model may cut the quote longer; whole-word overlap still counts.
    confirmed = root("widgets-3-1", "Confirmed")
    found = extraction("aliasing it instead", "As bo said, quote of widgets-3-1.")
    assert still_extracted(confirmed, found)


def test_the_same_alternative_with_a_new_verbatim_quote_survives() -> None:
    confirmed = root("widgets-3-1", "Confirmed")
    found = extraction("alternative of widgets-3-1", "a different quote")
    assert still_extracted(confirmed, found)


def test_a_reworded_alternative_with_another_quote_is_lost() -> None:
    confirmed = root("widgets-3-1", "Confirmed")
    found = extraction("aliasing it instead", "a different quote entirely here")
    assert not still_extracted(confirmed, found)


def test_an_overlap_under_four_words_does_not_count() -> None:
    confirmed = root("widgets-3-1", "Confirmed")
    found = extraction("aliasing it instead", "of widgets-3")
    assert not still_extracted(confirmed, found)


def test_a_quote_that_is_not_verbatim_does_not_count() -> None:
    confirmed = root("widgets-3-1", "Confirmed")
    found = extraction("alternative of widgets-3-1", "quote of widgets-3-1", False)
    assert not still_extracted(confirmed, found)


def test_a_reworded_alternative_needs_its_quote_verbatim() -> None:
    confirmed = root("widgets-3-1", "Confirmed")
    found = extraction("aliasing it instead", "quote of widgets-3-1", False)
    assert not still_extracted(confirmed, found)


def reject(log: Path, reason: str = "misread") -> partial[Correction]:
    return partial(reject_root, root_id="widgets-4-1", reason=reason, by="bo", log=log)


def confirm(log: Path) -> partial[Correction]:
    return partial(confirm_root, root_id="widgets-4-1", by="maria", log=log)


def test_a_correction_that_keeps_every_confirmed_root_stays(
    registry: Path, log: Path
) -> None:
    outcome = gated(registry, reject(log), Gate(FakeGitHub(), FakeSpark()), log)
    assert outcome.lost == [] and not outcome.rolled_back
    assert status_on_disk(registry, "widgets-4-1") == "Unknown"
    assert "4" not in raw_entries(registry)
    assert len(log.read_text().splitlines()) == 1


def test_only_prs_with_a_confirmed_root_are_re_extracted(
    registry: Path, log: Path
) -> None:
    # widgets-3-1 is the fixture's one Confirmed root; rejecting 4-1 leaves just it.
    github = FakeGitHub()
    gated(registry, reject(log), Gate(github, FakeSpark()), log)
    assert github.read == [3]


def test_the_root_just_confirmed_is_re_extracted_too(registry: Path, log: Path) -> None:
    github = FakeGitHub()
    gated(registry, confirm(log), Gate(github, FakeSpark()), log)
    assert sorted(github.read) == [3, 4]


def test_re_extraction_uses_the_few_shot_block_with_the_new_correction(
    registry: Path, log: Path
) -> None:
    spark = FakeSpark()
    gated(registry, reject(log, "not a team decision"), Gate(FakeGitHub(), spark), log)
    [prompt] = spark.prompts
    assert "REJECTED (reason: not a team decision)" in prompt
    assert prompt.index("PAST CORRECTIONS") < prompt.index("PR TEXT:")


def forgets_on_reject() -> Gate:
    return Gate(FakeGitHub(), FakeSpark(forget_on="REJECTED"))


def test_a_reject_that_loses_a_confirmed_root_is_rolled_back(
    registry: Path, log: Path
) -> None:
    registry_before = registry.read_text()
    outcome = gated(registry, reject(log), forgets_on_reject(), log)
    assert outcome.rolled_back and [r.id for r in outcome.lost] == ["widgets-3-1"]
    assert status_on_disk(registry, "widgets-4-1") == "Inferred"
    assert registry.read_text() == registry_before
    assert log.read_text() == ""


def test_a_confirm_that_loses_a_confirmed_root_is_rolled_back(
    registry: Path, log: Path
) -> None:
    spark = FakeSpark(forget_on='CONFIRMED: decision "decision of widgets-4-1"')
    outcome = gated(registry, confirm(log), Gate(FakeGitHub(), spark), log)
    assert sorted(r.id for r in outcome.lost) == ["widgets-3-1", "widgets-4-1"]
    assert status_on_disk(registry, "widgets-4-1") == "Inferred"


def test_rollback_removes_only_the_new_correction_from_the_log(
    registry: Path, log: Path
) -> None:
    earlier = root("widgets-7-1", "Inferred")
    fields = {"root_id": earlier.id, "action": "confirm", "before": earlier}
    fields |= {"after": earlier.model_copy(update={"status": "Confirmed"})}
    old = Correction.model_validate({**fields, "reason": None, "by": "x", "at": AT})
    append_correction(old, log)
    gated(registry, reject(log), forgets_on_reject(), log)
    assert log.read_text() == old.model_dump_json() + "\n"


def test_a_pr_that_can_no_longer_be_read_counts_as_lost(
    registry: Path, log: Path
) -> None:
    spark = FakeSpark(babble=True)
    outcome = gated(registry, reject(log), Gate(FakeGitHub(), spark), log)
    assert [r.id for r in outcome.lost] == ["widgets-3-1"]
    assert status_on_disk(registry, "widgets-4-1") == "Inferred"


def test_no_gate_applies_the_correction_without_re_extracting(
    registry: Path, log: Path
) -> None:
    outcome = gated(registry, reject(log), None, log)
    assert outcome.lost == []
    assert status_on_disk(registry, "widgets-4-1") == "Unknown"


def test_the_gate_reports_how_many_prs_it_reads(registry: Path, log: Path) -> None:
    lines = list[str]()
    gate = Gate(FakeGitHub(), FakeSpark(), log=lines.append)
    gated(registry, reject(log), gate, log)
    assert lines == ["gate: re-extracting 1 PR(s) with Confirmed roots"]
