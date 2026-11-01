from pathlib import Path

import pytest
from knack import cli
from knack.contracts.models import DecisionStatus
from knack.roots.store import load_roots, write_root
from knack.walk.registry import (
    home_registry_dir,
    load_registry,
    Registry,
    RegistryEntry,
)
from registry_fixture import make_registry, raw_entries, root, status_on_disk


@pytest.fixture
def home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("KNACK_HOME", raising=False)
    return tmp_path / "home"


def home_registry() -> Path:
    return home_registry_dir("acme/widgets") / "registry.json"


def source_registry(
    out: Path, entries: dict[str, list[str]], statuses: dict[str, DecisionStatus]
) -> Path:
    # A hand-kept registry: rules and roots beside it, root files not named by id.
    for root_id, status in statuses.items():
        write_root(root(root_id, status), out / "roots" / f"{root_id[8:]}.json")
    (out / "rules").mkdir(parents=True)
    rules = [_source_entry(out, number, ids) for number, ids in entries.items()]
    registry = Registry(repo="acme/widgets", roots_dir=Path("roots"), rules=rules)
    (out / "team.json").write_text(registry.model_dump_json(indent=2) + "\n")
    return out / "team.json"


def _source_entry(out: Path, number: str, root_ids: list[str]) -> RegistryEntry:
    (out / "rules" / f"{number}.yml").write_text(f"id: imported-{number}\n")
    return RegistryEntry(rule=Path("rules") / f"{number}.yml", root_ids=root_ids)


def import_registry(path: Path) -> int:
    return cli.main(["import", "--registry", str(path)])


def test_import_into_an_empty_home_installs_rules_and_roots(
    home: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = source_registry(
        tmp_path / "src", {"5": ["widgets-5-1"]}, {"widgets-5-1": "Confirmed"}
    )
    assert import_registry(source) == 0
    [entry] = load_registry(home_registry()).rules
    assert entry.rule.read_text() == "id: imported-5\n"
    assert raw_entries(home_registry()) == {"5": ["widgets-5-1"]}
    assert status_on_disk(home_registry(), "widgets-5-1") == "Confirmed"
    assert str(home_registry()) in capsys.readouterr().out


def test_import_keeps_home_rules_and_appends_new_ones(
    home: Path, tmp_path: Path
) -> None:
    make_registry(home_registry().parent)
    source = source_registry(
        tmp_path / "src", {"5": ["widgets-5-1"]}, {"widgets-5-1": "Inferred"}
    )
    assert import_registry(source) == 0
    assert list(raw_entries(home_registry())) == ["9", "4", "3", "5"]


def test_a_rule_already_in_home_is_not_overwritten(home: Path, tmp_path: Path) -> None:
    make_registry(home_registry().parent)
    source = source_registry(
        tmp_path / "src", {"4": ["widgets-4-1"]}, {"widgets-4-1": "Inferred"}
    )
    assert import_registry(source) == 0
    assert raw_entries(home_registry())["4"] == ["widgets-4-1"]
    assert (home_registry().parent / "rules" / "4.yml").read_text() == "id: widgets-4\n"


def test_import_never_overwrites_a_reviewed_home_root(
    home: Path, tmp_path: Path
) -> None:
    # Home widgets-3-1 is Confirmed; the imported copy is only Inferred.
    make_registry(home_registry().parent)
    source = source_registry(
        tmp_path / "src", {"3": ["widgets-3-1"]}, {"widgets-3-1": "Inferred"}
    )
    assert import_registry(source) == 0
    assert status_on_disk(home_registry(), "widgets-3-1") == "Confirmed"


def test_a_reviewed_import_replaces_an_inferred_home_root(
    home: Path, tmp_path: Path
) -> None:
    make_registry(home_registry().parent)
    source = source_registry(
        tmp_path / "src", {"5": ["widgets-4-1"]}, {"widgets-4-1": "Confirmed"}
    )
    assert import_registry(source) == 0
    assert status_on_disk(home_registry(), "widgets-4-1") == "Confirmed"
    roots = load_roots(home_registry().parent / "roots")
    assert [r.id for r in roots].count("widgets-4-1") == 1


def test_import_never_resurrects_a_rejected_home_root(
    home: Path, tmp_path: Path
) -> None:
    make_registry(home_registry().parent)
    write_root(
        root("widgets-6-1", "Unknown"),
        home_registry().parent / "roots" / "widgets-6-1.json",
    )
    entries = {"6": ["widgets-6-1"], "7": ["widgets-6-1", "widgets-7-1"]}
    statuses: dict[str, DecisionStatus] = {
        "widgets-6-1": "Confirmed",
        "widgets-7-1": "Inferred",
    }
    assert import_registry(source_registry(tmp_path / "src", entries, statuses)) == 0
    assert status_on_disk(home_registry(), "widgets-6-1") == "Unknown"
    assert "6" not in raw_entries(home_registry())
    assert raw_entries(home_registry())["7"] == ["widgets-7-1"]


def test_importing_twice_changes_nothing(home: Path, tmp_path: Path) -> None:
    source = source_registry(
        tmp_path / "src", {"5": ["widgets-5-1"]}, {"widgets-5-1": "Inferred"}
    )
    import_registry(source)
    first = home_registry().read_text()
    assert import_registry(source) == 0
    assert home_registry().read_text() == first


def test_missing_source_registry_exits_2(
    home: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert import_registry(tmp_path / "nowhere.json") == 2
    assert "knack import: no registry at" in capsys.readouterr().err


def test_importing_the_home_registry_into_itself_exits_2(
    home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    make_registry(home_registry().parent)
    assert import_registry(home_registry()) == 2
    assert "already the home registry" in capsys.readouterr().err
