import json
from datetime import datetime
from pathlib import Path

import pytest
from knack.contracts.models import DecisionStatus
from knack.roots.correct import confirm_root, CorrectionError, reject_root
from knack.roots.corrections import Correction
from knack.roots.store import write_root
from registry_fixture import make_registry, raw_entries, root, status_on_disk


@pytest.fixture
def registry(tmp_path: Path) -> Path:
    return make_registry(tmp_path / "reg")


@pytest.fixture
def log(tmp_path: Path) -> Path:
    return tmp_path / "home" / ".knack" / "corrections.jsonl"


def logged(log: Path) -> list[Correction]:
    lines = log.read_text().splitlines()
    return [Correction.model_validate_json(line) for line in lines]


def test_confirm_flips_inferred_root_to_confirmed(registry: Path, log: Path) -> None:
    confirm_root(registry, "widgets-4-1", "maria", log)
    assert status_on_disk(registry, "widgets-4-1") == "Confirmed"


def test_confirm_leaves_the_registry_rules_alone(registry: Path, log: Path) -> None:
    before = registry.read_text()
    confirm_root(registry, "widgets-4-1", "maria", log)
    assert registry.read_text() == before


def test_confirm_appends_a_full_correction(registry: Path, log: Path) -> None:
    confirm_root(registry, "widgets-4-1", "maria", log)
    [record] = logged(log)
    assert (record.root_id, record.action, record.by) == (
        "widgets-4-1",
        "confirm",
        "maria",
    )
    assert (record.before.status, record.after.status) == ("Inferred", "Confirmed")
    assert record.reason is None and datetime.fromisoformat(record.at).tzinfo


def test_confirm_finds_a_root_whatever_its_file_is_named(
    registry: Path, log: Path
) -> None:
    roots = registry.parent / "roots"
    (roots / "widgets-4-1.json").rename(roots / "4.json")
    confirm_root(registry, "widgets-4-1", "maria", log)
    assert json.loads((roots / "4.json").read_text())["status"] == "Confirmed"


def test_reject_sets_unknown_and_drops_a_rule_it_alone_backs(
    registry: Path, log: Path
) -> None:
    reject_root(registry, "widgets-4-1", "not a decision", "maria", log)
    assert status_on_disk(registry, "widgets-4-1") == "Unknown"
    assert "4" not in raw_entries(registry)


def test_reject_keeps_a_shared_rule_for_its_other_roots(
    registry: Path, log: Path
) -> None:
    reject_root(registry, "widgets-9-1", "misread", "maria", log)
    assert raw_entries(registry)["9"] == ["widgets-9-2"]


def test_reject_keeps_registry_paths_relative(registry: Path, log: Path) -> None:
    reject_root(registry, "widgets-4-1", "misread", "maria", log)
    data = json.loads(registry.read_text())
    assert data["roots_dir"] == "roots"
    assert [e["rule"] for e in data["rules"]] == ["rules/9.yml", "rules/3.yml"]


def test_reject_appends_reason_and_both_states(registry: Path, log: Path) -> None:
    reject_root(registry, "widgets-3-1", "we reverted this", "bo", log)
    [record] = logged(log)
    assert (record.action, record.reason, record.by) == (
        "reject",
        "we reverted this",
        "bo",
    )
    assert (record.before.status, record.after.status) == ("Confirmed", "Unknown")


def test_corrections_accumulate_in_order(registry: Path, log: Path) -> None:
    confirm_root(registry, "widgets-9-1", "maria", log)
    reject_root(registry, "widgets-9-2", "dup", "maria", log)
    assert [r.root_id for r in logged(log)] == ["widgets-9-1", "widgets-9-2"]


def test_unknown_root_id_raises_and_logs_nothing(registry: Path, log: Path) -> None:
    with pytest.raises(CorrectionError, match="widgets-99-1"):
        confirm_root(registry, "widgets-99-1", "maria", log)
    assert not log.exists()


@pytest.mark.parametrize("status", ["Corroborated", "Uncorroborated"])
def test_confirm_promotes_a_corroboration_label(
    registry: Path, log: Path, status: DecisionStatus
) -> None:
    write_root(
        root("widgets-4-1", status), registry.parent / "roots" / "widgets-4-1.json"
    )
    record = confirm_root(registry, "widgets-4-1", "maria", log)
    assert (record.before.status, record.after.status) == (status, "Confirmed")
    assert status_on_disk(registry, "widgets-4-1") == "Confirmed"


def test_confirm_refuses_an_already_confirmed_root(registry: Path, log: Path) -> None:
    with pytest.raises(CorrectionError, match="Confirmed"):
        confirm_root(registry, "widgets-3-1", "maria", log)


def test_confirm_refuses_a_rejected_root(registry: Path, log: Path) -> None:
    reject_root(registry, "widgets-4-1", "misread", "maria", log)
    with pytest.raises(CorrectionError, match="Unknown"):
        confirm_root(registry, "widgets-4-1", "maria", log)


def test_reject_refuses_an_already_rejected_root(registry: Path, log: Path) -> None:
    reject_root(registry, "widgets-4-1", "misread", "maria", log)
    with pytest.raises(CorrectionError, match="Unknown"):
        reject_root(registry, "widgets-4-1", "again", "maria", log)


def test_reject_needs_a_reason(registry: Path, log: Path) -> None:
    with pytest.raises(CorrectionError, match="reason"):
        reject_root(registry, "widgets-4-1", "  ", "maria", log)
    assert status_on_disk(registry, "widgets-4-1") == "Inferred"
