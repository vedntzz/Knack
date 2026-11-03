import threading
from datetime import datetime, timezone, tzinfo
from pathlib import Path

import pytest
from knack.contracts.models import Root, Verdict
from knack.day.when import moment
from knack.miss.cases import case_path, cases_dir, EditCase, load_cases
from knack.miss.provisional import load_provisional, save_provisional
from knack.receipts.chain import (
    append_receipt,
    append_resolution,
    guard_receipt,
    human_allow,
    load_receipts,
    Receipt,
    Resolution,
    resolution_receipt,
    ResolutionAction,
    settled_by,
    SettledError,
    verify_chain,
)
from knack.roots import resolve
from knack.roots.corrections import append_correction, Correction, recent_corrections
from knack.roots.resolve import resolve_deny, ResolveError
from registry_fixture import make_registry, raw_entries, root, status_on_disk

EDIT = "e" * 64
NOW = "2026-10-31T09:00:00+00:00"


@pytest.fixture
def registry(tmp_path: Path) -> Path:
    return make_registry(tmp_path / "reg")


@pytest.fixture
def log(tmp_path: Path) -> Path:
    return tmp_path / "home" / ".knack" / "corrections.jsonl"


@pytest.fixture
def receipts(tmp_path: Path) -> Path:
    return tmp_path / "home" / ".knack" / "verdicts.jsonl"


def verdict(allowed: bool) -> Verdict:
    if allowed:
        return Verdict(allowed=True, reason="no rule matched", latency_ms=1.0)
    return Verdict.model_validate(
        {"allowed": False, "reason": "blocked", "latency_ms": 2.0}
        | {"rule_id": "widgets-3", "root_ids": ["widgets-3-1"]}
    )


def receipted(
    receipts: Path, allowed: bool = False, edit: str | None = EDIT
) -> Receipt:
    # A guard receipt on rule 3, whose one root widgets-3-1 is Confirmed.
    named = (
        "acme/widgets",
        "/w/widgets/a.py",
        "widgets-3",
        root("widgets-3-1", "Confirmed"),
    )
    fields = guard_receipt(*named, verdict(allowed), NOW, "main", "s1", edit)
    return append_receipt(receipts, fields)


def logged(log: Path) -> list[Correction]:
    return [
        Correction.model_validate_json(line) for line in log.read_text().splitlines()
    ]


def test_allow_logs_a_correction_naming_the_deny(
    registry: Path, log: Path, receipts: Path
) -> None:
    deny = receipted(receipts)
    resolve_deny(
        receipts, deny.hash, "allow", "pinned client, ok here", "maria", log, registry
    )
    [record] = logged(log)
    assert (record.action, record.root_id, record.receipt_hash) == (
        "allow",
        "widgets-3-1",
        deny.hash,
    )
    assert (record.reason, record.by) == ("pinned client, ok here", "maria")
    assert record.before == record.after


def test_allow_appends_a_resolution_receipt_to_the_chain(
    registry: Path, log: Path, receipts: Path
) -> None:
    deny = receipted(receipts)
    resolve_deny(receipts, deny.hash, "allow", "ok here", "maria", log, registry)
    [_, resolved] = load_receipts(receipts)
    assert (resolved.decision, resolved.rule_id, resolved.edit_sha256) == (
        "allow",
        "widgets-3",
        EDIT,
    )
    assert resolved.resolution is not None
    assert (resolved.resolution.of, resolved.resolution.action) == (deny.hash, "allow")
    assert (resolved.resolution.by, resolved.resolution.reason) == ("maria", "ok here")
    assert verify_chain(receipts).broken_line is None


def test_allow_leaves_the_root_and_registry_alone(
    registry: Path, log: Path, receipts: Path
) -> None:
    before = registry.read_text()
    resolve_deny(
        receipts, receipted(receipts).hash, "allow", "ok", "maria", log, registry
    )
    assert registry.read_text() == before
    assert status_on_disk(registry, "widgets-3-1") == "Confirmed"


def test_retire_drops_the_root_from_the_registry_and_logs_it(
    registry: Path, log: Path, receipts: Path
) -> None:
    deny = receipted(receipts)
    resolve_deny(
        receipts, deny.hash, "retire", "superseded by #12", "bo", log, registry
    )
    assert "3" not in raw_entries(registry)
    assert [(c.action, c.reason) for c in logged(log)] == [
        ("retire", "superseded by #12")
    ]
    resolution = load_receipts(receipts)[-1].resolution
    assert resolution is not None and resolution.action == "retire"


def test_retire_keeps_the_root_label_honest(
    registry: Path, log: Path, receipts: Path
) -> None:
    # The decision was real; it is retired, not relabelled as a bad extraction.
    resolve_deny(
        receipts, receipted(receipts).hash, "retire", "old", "bo", log, registry
    )
    assert status_on_disk(registry, "widgets-3-1") == "Confirmed"


def test_human_allow_finds_the_allowed_edit_for_its_rule_only(
    registry: Path, log: Path, receipts: Path
) -> None:
    deny = receipted(receipts)
    resolve_deny(receipts, deny.hash, "allow", "ok", "maria", log, registry)
    found = human_allow(receipts, "widgets-3", EDIT)
    assert found is not None and found.by == "maria"
    assert human_allow(receipts, "widgets-9", EDIT) is None
    assert human_allow(receipts, "widgets-3", "f" * 64) is None


def test_human_allow_ignores_a_retire(
    registry: Path, log: Path, receipts: Path
) -> None:
    deny = receipted(receipts)
    resolve_deny(receipts, deny.hash, "retire", "old", "bo", log, registry)
    assert human_allow(receipts, "widgets-3", EDIT) is None


def test_human_allow_on_a_missing_chain_is_none(tmp_path: Path) -> None:
    assert human_allow(tmp_path / "none.jsonl", "widgets-3", EDIT) is None


@pytest.mark.parametrize("reason", ["", "   "])
def test_resolve_needs_a_reason(
    registry: Path, log: Path, receipts: Path, reason: str
) -> None:
    deny = receipted(receipts)
    with pytest.raises(ResolveError, match="reason"):
        resolve_deny(receipts, deny.hash, "allow", reason, "maria", log, registry)
    assert not log.exists() and len(load_receipts(receipts)) == 1


def test_resolve_refuses_an_unknown_receipt(
    registry: Path, log: Path, receipts: Path
) -> None:
    receipted(receipts)
    with pytest.raises(ResolveError, match="no receipt"):
        resolve_deny(receipts, "0" * 64, "allow", "ok", "maria", log, registry)


def test_resolve_refuses_an_allow_receipt(
    registry: Path, log: Path, receipts: Path
) -> None:
    allow = receipted(receipts, allowed=True)
    with pytest.raises(ResolveError, match="not a deny"):
        resolve_deny(receipts, allow.hash, "allow", "ok", "maria", log, registry)
    assert not log.exists()


def test_resolve_refuses_a_deny_already_resolved(
    registry: Path, log: Path, receipts: Path
) -> None:
    deny = receipted(receipts)
    resolve_deny(receipts, deny.hash, "allow", "ok", "maria", log, registry)
    with pytest.raises(ResolveError, match="already resolved"):
        resolve_deny(receipts, deny.hash, "retire", "again", "bo", log, registry)
    assert len(logged(log)) == 1


def test_resolve_refuses_a_root_gone_from_the_registry(
    registry: Path, log: Path, receipts: Path
) -> None:
    deny = receipted(receipts)
    (registry.parent / "roots" / "widgets-3-1.json").unlink()
    with pytest.raises(ResolveError, match="widgets-3-1"):
        resolve_deny(receipts, deny.hash, "allow", "ok", "maria", log, registry)


def test_resolutions_never_feed_the_extract_few_shot(
    registry: Path, log: Path, receipts: Path
) -> None:
    # Allow and retire judge an edit or a decision's life, not an extraction.
    resolve_deny(
        receipts, receipted(receipts).hash, "allow", "ok", "maria", log, registry
    )
    assert recent_corrections(log) == []


def test_old_correction_lines_without_a_receipt_hash_still_load(log: Path) -> None:
    confirmed = root("widgets-4-1", "Confirmed")
    fields = {"root_id": "widgets-4-1", "action": "confirm", "before": confirmed}
    fields |= {"after": confirmed, "reason": None, "by": "m", "at": NOW}
    append_correction(Correction.model_validate(fields), log)
    line = log.read_text().replace(',"receipt_hash":null', "")
    log.write_text(line)
    [record] = recent_corrections(log)
    assert record.receipt_hash is None


def provisional_case(deny: Receipt) -> EditCase:
    # What argue keeps when Spark and Spark Open both escalate on this deny.
    fields = {"kind": "must-pass", "rule_id": "widgets-3", "file": "a.py"}
    fields |= {"before": "x = 1\n", "after": "x = 2\n"}
    return EditCase.model_validate(fields | {"source": f"receipt {deny.hash} (auto)"})


def test_a_provisional_case_is_not_a_case_the_loop_sees(
    registry: Path, receipts: Path
) -> None:
    deny = receipted(receipts)
    save_provisional(registry, deny.hash, provisional_case(deny))
    assert load_cases(cases_dir(registry), "widgets-3") == []


def test_allow_promotes_the_provisional_case_to_must_pass(
    registry: Path, log: Path, receipts: Path
) -> None:
    deny = receipted(receipts)
    save_provisional(registry, deny.hash, provisional_case(deny))
    named = (receipts, deny.hash, "allow", "pinned client", "maria", log, registry)
    done = resolve_deny(*named)
    [case] = load_cases(cases_dir(registry), "widgets-3")
    assert (case.kind, case.file, case.after) == ("must-pass", "a.py", "x = 2\n")
    assert "maria" in case.note and "pinned client" in case.note
    assert done.promoted == case_path(cases_dir(registry), case)
    assert load_provisional(registry, deny.hash) is None


def test_retire_never_promotes_the_provisional_case(
    registry: Path, log: Path, receipts: Path
) -> None:
    deny = receipted(receipts)
    save_provisional(registry, deny.hash, provisional_case(deny))
    done = resolve_deny(
        receipts, deny.hash, "retire", "superseded", "bo", log, registry
    )
    assert done.promoted is None
    assert load_cases(cases_dir(registry), "widgets-3") == []
    assert load_provisional(registry, deny.hash) is not None


def test_allow_without_a_provisional_case_promotes_nothing(
    registry: Path, log: Path, receipts: Path
) -> None:
    deny = receipted(receipts)
    done = resolve_deny(receipts, deny.hash, "allow", "ok", "maria", log, registry)
    assert done.promoted is None
    assert load_cases(cases_dir(registry), "widgets-3") == []


def test_another_denys_provisional_case_is_left_alone(
    registry: Path, log: Path, receipts: Path
) -> None:
    deny, other = receipted(receipts), receipted(receipts, edit="f" * 64)
    save_provisional(registry, other.hash, provisional_case(other))
    resolve_deny(receipts, deny.hash, "allow", "ok", "maria", log, registry)
    assert load_cases(cases_dir(registry), "widgets-3") == []
    assert load_provisional(registry, other.hash) is not None


# The audit's case: the guard stamped the block in microseconds, resolve ran later that second.
BLOCKED_AT = "2026-11-02T04:26:13.551487+00:00"
RESOLVED_AT = datetime(2026, 11, 2, 4, 26, 13, 900000, tzinfo=timezone.utc)


class ResolveClock(datetime):
    # Freezes resolve's clock just after the block, in the same whole second.
    @classmethod
    def now(cls, tz: tzinfo | None = None) -> "ResolveClock":
        at = RESOLVED_AT.astimezone(tz)
        return cls.fromtimestamp(at.timestamp(), tz)


def blocked_in_microseconds(receipts: Path) -> Receipt:
    named = (
        "acme/widgets",
        "/w/widgets/a.py",
        "widgets-3",
        root("widgets-3-1", "Confirmed"),
    )
    fields = guard_receipt(*named, verdict(False), BLOCKED_AT, "main", "s1", EDIT)
    return append_receipt(receipts, fields)


def test_a_learn_receipt_sorts_after_the_block_it_resolves(
    registry: Path, log: Path, receipts: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(resolve, "datetime", ResolveClock)
    deny = blocked_in_microseconds(receipts)
    resolve_deny(receipts, deny.hash, "allow", "ok here", "maria", log, registry)
    block, learn = load_receipts(receipts)
    learned, blocked = moment(learn.time), moment(block.time)
    assert learned is not None and blocked is not None and learned > blocked
    assert sorted([learn, block], key=lambda r: moment(r.time) or RESOLVED_AT) == [
        block,
        learn,
    ]


def test_resolve_stamps_with_the_guards_microsecond_precision(
    registry: Path, log: Path, receipts: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(resolve, "datetime", ResolveClock)
    deny = blocked_in_microseconds(receipts)
    resolve_deny(receipts, deny.hash, "allow", "ok here", "maria", log, registry)
    [record] = logged(log)
    assert record.at == "2026-11-02T04:26:13.900000+00:00"
    assert load_receipts(receipts)[-1].time == record.at


def upheld(registry: Path, log: Path, receipts: Path) -> tuple[Receipt, Receipt]:
    # A person reviewed the held case and confirmed the decision stands.
    deny = receipted(receipts)
    named = (receipts, deny.hash, "uphold", "the decision stands", "maria", log)
    return deny, resolve_deny(*named, registry).receipt


def test_uphold_appends_a_resolution_receipt_chained_to_the_block(
    registry: Path, log: Path, receipts: Path
) -> None:
    deny, receipt = upheld(registry, log, receipts)
    assert load_receipts(receipts) == [deny, receipt]
    assert receipt.prev == deny.hash
    assert receipt.resolution == Resolution(
        of=deny.hash, action="uphold", by="maria", reason="the decision stands"
    )
    assert (receipt.rule_id, receipt.edit_sha256) == ("widgets-3", EDIT)
    assert verify_chain(receipts).broken_line is None


def test_an_uphold_receipt_records_the_edit_as_still_denied(
    registry: Path, log: Path, receipts: Path
) -> None:
    _, receipt = upheld(registry, log, receipts)
    assert receipt.decision == "deny"


def test_uphold_logs_a_correction_and_leaves_the_rule_alone(
    registry: Path, log: Path, receipts: Path
) -> None:
    before = registry.read_text()
    deny, _ = upheld(registry, log, receipts)
    [record] = logged(log)
    assert (record.action, record.receipt_hash, record.by) == (
        "uphold",
        deny.hash,
        "maria",
    )
    assert record.before == record.after
    assert registry.read_text() == before
    assert status_on_disk(registry, "widgets-3-1") == "Confirmed"


def test_uphold_creates_no_exception_for_the_edit(
    registry: Path, log: Path, receipts: Path
) -> None:
    upheld(registry, log, receipts)
    assert human_allow(receipts, "widgets-3", EDIT) is None


def test_uphold_closes_the_held_case_without_making_it_a_case(
    registry: Path, log: Path, receipts: Path
) -> None:
    deny = receipted(receipts)
    held = save_provisional(registry, deny.hash, provisional_case(deny))
    named = (receipts, deny.hash, "uphold", "stands", "maria", log, registry)
    done = resolve_deny(*named)
    assert load_provisional(registry, deny.hash) is None
    assert load_cases(cases_dir(registry), "widgets-3") == []
    assert (done.promoted, done.closed) == (None, held)


def test_uphold_without_a_held_case_closes_nothing(
    registry: Path, log: Path, receipts: Path
) -> None:
    deny = receipted(receipts)
    done = resolve_deny(receipts, deny.hash, "uphold", "stands", "maria", log, registry)
    assert (done.promoted, done.closed) == (None, None)


def test_allow_and_retire_close_no_held_case(
    registry: Path, log: Path, receipts: Path
) -> None:
    deny = receipted(receipts)
    done = resolve_deny(receipts, deny.hash, "retire", "old", "bo", log, registry)
    assert done.closed is None


def test_an_upheld_deny_is_resolved_and_cannot_be_resolved_again(
    registry: Path, log: Path, receipts: Path
) -> None:
    deny, _ = upheld(registry, log, receipts)
    with pytest.raises(ResolveError, match="already resolved: uphold by maria"):
        resolve_deny(receipts, deny.hash, "allow", "now ok", "bo", log, registry)
    assert human_allow(receipts, "widgets-3", EDIT) is None


def test_an_uphold_receipt_is_not_itself_a_deny_to_resolve(
    registry: Path, log: Path, receipts: Path
) -> None:
    _, receipt = upheld(registry, log, receipts)
    with pytest.raises(ResolveError, match="not a deny"):
        resolve_deny(receipts, receipt.hash, "allow", "ok", "bo", log, registry)


def test_uphold_never_feeds_the_extract_few_shot(
    registry: Path, log: Path, receipts: Path
) -> None:
    upheld(registry, log, receipts)
    assert recent_corrections(log) == []


def late_allow(receipts: Path, deny: Receipt) -> Receipt:
    # An allow that reached the chain after the deny was settled, as a lost race left one.
    late = Resolution(of=deny.hash, action="allow", by="bo", reason="late")
    return append_receipt(receipts, resolution_receipt(deny, late, NOW))


def test_a_deny_is_settled_by_its_first_resolution(
    registry: Path, log: Path, receipts: Path
) -> None:
    deny, _ = upheld(registry, log, receipts)
    late_allow(receipts, deny)
    done = settled_by(load_receipts(receipts), deny.hash)
    assert done is not None and (done.action, done.by) == ("uphold", "maria")


def test_an_unresolved_deny_is_not_settled_by_another_denys_resolution(
    registry: Path, log: Path, receipts: Path
) -> None:
    deny, other = receipted(receipts), receipted(receipts, edit="f" * 64)
    resolve_deny(receipts, other.hash, "allow", "ok", "maria", log, registry)
    assert settled_by(load_receipts(receipts), deny.hash) is None


def test_the_guard_ignores_an_allow_recorded_after_an_uphold(
    registry: Path, log: Path, receipts: Path
) -> None:
    deny, _ = upheld(registry, log, receipts)
    late_allow(receipts, deny)
    assert human_allow(receipts, "widgets-3", EDIT) is None


def test_appending_a_resolution_refuses_a_settled_deny_under_the_lock(
    registry: Path, log: Path, receipts: Path
) -> None:
    deny, _ = upheld(registry, log, receipts)
    late = Resolution(of=deny.hash, action="allow", by="bo", reason="late")
    with pytest.raises(SettledError, match="already resolved: uphold by maria"):
        append_resolution(receipts, deny, late, NOW)
    assert len(load_receipts(receipts)) == 2


def raced(
    receipts: Path, deny: Receipt, log: Path, registry: Path
) -> list[tuple[str, str]]:
    # maria allows and bob upholds the same deny at once; each records ok or refused.
    outcomes: list[tuple[str, str]] = []
    tries = [("allow", "maria"), ("uphold", "bob")]
    args = [(receipts, deny, log, registry, a, by, outcomes) for a, by in tries]
    runs = [threading.Thread(target=one_resolve, args=a) for a in args]
    _ = [run.start() for run in runs] + [run.join() for run in runs]
    return sorted(outcomes)


def one_resolve(
    receipts: Path,
    deny: Receipt,
    log: Path,
    registry: Path,
    action: ResolutionAction,
    by: str,
    outcomes: list[tuple[str, str]],
) -> None:
    try:
        resolve_deny(receipts, deny.hash, action, "why", by, log, registry)
        outcomes.append(("ok", by))
    except ResolveError:
        outcomes.append(("refused", by))


def both_pass_the_open_check(monkeypatch: pytest.MonkeyPatch) -> None:
    # Each resolve waits for the other after its own open check, before writing anything.
    gate = threading.Barrier(2, timeout=5)
    real = resolve._correction  # pyright: ignore[reportPrivateUsage]

    def waited(root: Root, resolution: Resolution) -> Correction:
        gate.wait()
        return real(root, resolution)

    monkeypatch.setattr(resolve, "_correction", waited)


def test_two_concurrent_resolves_of_one_deny_exactly_one_succeeds(
    registry: Path, log: Path, receipts: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deny = receipted(receipts)
    both_pass_the_open_check(monkeypatch)
    outcomes = raced(receipts, deny, log, registry)
    assert [kind for kind, _ in outcomes] == ["ok", "refused"]
    assert len([r for r in load_receipts(receipts) if r.resolution]) == 1
    assert len(logged(log)) == 1 and verify_chain(receipts).broken_line is None
