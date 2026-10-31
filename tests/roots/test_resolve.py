from pathlib import Path

import pytest
from knack.contracts.models import Verdict
from knack.receipts.chain import (
    append_receipt,
    guard_receipt,
    human_allow,
    load_receipts,
    Receipt,
    verify_chain,
)
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
