from pathlib import Path

import pytest
from knack import cli
from knack.roots.corrections import Correction
from registry_fixture import make_registry, raw_entries, status_on_disk


@pytest.fixture
def home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    return tmp_path / "home"


def logged(home: Path) -> list[Correction]:
    lines = (home / ".knack" / "corrections.jsonl").read_text().splitlines()
    return [Correction.model_validate_json(line) for line in lines]


def test_confirm_flips_the_root_and_logs_to_home(
    home: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = make_registry(tmp_path / "reg")
    args = ["confirm", "widgets-4-1", "--registry", str(registry), "--by", "maria"]
    assert cli.main(args) == 0
    assert status_on_disk(registry, "widgets-4-1") == "Confirmed"
    assert [(c.action, c.by) for c in logged(home)] == [("confirm", "maria")]
    assert "widgets-4-1: Inferred -> Confirmed" in capsys.readouterr().out


def test_reject_unknowns_the_root_drops_its_rule_and_logs_the_reason(
    home: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = make_registry(tmp_path / "reg")
    args = ["reject", "widgets-4-1", "--registry", str(registry), "--reason", "misread"]
    assert cli.main([*args, "--by", "bo"]) == 0
    assert status_on_disk(registry, "widgets-4-1") == "Unknown"
    assert "4" not in raw_entries(registry)
    assert [(c.action, c.reason) for c in logged(home)] == [("reject", "misread")]
    assert "widgets-4-1: Inferred -> Unknown" in capsys.readouterr().out


def test_reject_without_reason_is_a_usage_error(home: Path, tmp_path: Path) -> None:
    registry = make_registry(tmp_path / "reg")
    with pytest.raises(SystemExit) as raised:
        cli.main(["reject", "widgets-4-1", "--registry", str(registry)])
    assert raised.value.code == 2


def test_registry_is_required(home: Path) -> None:
    with pytest.raises(SystemExit) as raised:
        cli.main(["confirm", "widgets-4-1"])
    assert raised.value.code == 2


def test_unknown_root_exits_2_with_a_reason(
    home: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = make_registry(tmp_path / "reg")
    assert cli.main(["confirm", "widgets-99-1", "--registry", str(registry)]) == 2
    assert "knack confirm: no root widgets-99-1" in capsys.readouterr().err


def test_missing_registry_exits_2(
    home: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "nowhere" / "registry.json"
    assert cli.main(["confirm", "widgets-4-1", "--registry", str(missing)]) == 2
    assert "no registry at" in capsys.readouterr().err
