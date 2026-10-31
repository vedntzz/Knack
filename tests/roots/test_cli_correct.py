import subprocess
from pathlib import Path

import pytest
from gate_fakes import FakeGitHub, FakeSpark
from knack import cli
from knack.pipeline.clients import MissingCredentials
from knack.roots.corrections import Correction
from knack.roots.pin import rule_sha
from knack.walk.registry import home_registry_dir
from registry_fixture import make_registry, raw_entries, status_on_disk


@pytest.fixture
def home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    return tmp_path / "home"


@pytest.fixture(autouse=True)
def sparks(monkeypatch: pytest.MonkeyPatch) -> list[FakeSpark]:
    # The gate is on by default; every test reads through fakes, never the network.
    built = list[FakeSpark]()

    def clients(extractor: str = "spark") -> tuple[FakeGitHub, FakeSpark]:
        built.append(FakeSpark(forget_on="FORGET"))
        return FakeGitHub(), built[-1]

    monkeypatch.setattr(cli, "live_clients", clients)
    return built


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
    out = capsys.readouterr().out
    assert "widgets-4-1: Inferred -> Confirmed" in out
    sha = rule_sha(registry.parent / "rules" / "4.yml")
    assert f"pinned to rule {sha[:12]}" in out


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


def clone_of(path: Path, origin: str) -> Path:
    # A bare git init with an origin remote is all the default needs.
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(
        ["git", "-C", str(path), "remote", "add", "origin", origin], check=True
    )
    return path


def test_confirm_defaults_to_the_home_registry_of_this_clone(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = make_registry(home_registry_dir("acme/widgets"))
    clone = clone_of(tmp_path / "widgets", "git@github.com:Acme/widgets.git")
    # Run from a subfolder: the clone is found from anywhere inside it.
    (clone / "pkg").mkdir()
    monkeypatch.chdir(clone / "pkg")
    assert cli.main(["confirm", "widgets-4-1", "--by", "maria"]) == 0
    assert status_on_disk(registry, "widgets-4-1") == "Confirmed"


def test_reject_defaults_to_the_home_registry_of_this_clone(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = make_registry(home_registry_dir("acme/widgets"))
    monkeypatch.chdir(clone_of(tmp_path / "w", "https://github.com/acme/widgets"))
    assert cli.main(["reject", "widgets-4-1", "--reason", "misread", "--by", "bo"]) == 0
    assert status_on_disk(registry, "widgets-4-1") == "Unknown"


def test_without_registry_outside_a_clone_exits_2_with_a_reason(
    home: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    assert cli.main(["confirm", "widgets-4-1", "--by", "maria"]) == 2
    err = capsys.readouterr().err
    assert "knack confirm:" in err and "not a git clone" in err and "--registry" in err


def test_without_registry_a_clone_with_no_init_exits_2(
    home: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(clone_of(tmp_path / "w", "https://github.com/acme/widgets"))
    assert cli.main(["confirm", "widgets-4-1", "--by", "maria"]) == 2
    assert "no registry at" in capsys.readouterr().err


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


def test_no_gate_skips_re_extraction(
    home: Path, tmp_path: Path, sparks: list[FakeSpark]
) -> None:
    registry = make_registry(tmp_path / "reg")
    args = ["reject", "widgets-4-1", "--registry", str(registry), "--reason", "FORGET"]
    assert cli.main([*args, "--no-gate"]) == 0
    assert sparks == [] and status_on_disk(registry, "widgets-4-1") == "Unknown"


def test_gate_re_extracts_with_the_new_correction(
    home: Path, tmp_path: Path, sparks: list[FakeSpark]
) -> None:
    registry = make_registry(tmp_path / "reg")
    args = ["reject", "widgets-4-1", "--registry", str(registry), "--reason", "dup"]
    assert cli.main(args) == 0
    [prompt] = sparks[0].prompts
    assert "REJECTED (reason: dup)" in prompt


def forgetful_reject(registry: Path) -> int:
    # The fake extractor forgets every root once a correction says FORGET.
    args = ["reject", "widgets-4-1", "--registry", str(registry), "--reason", "FORGET"]
    return cli.main([*args, "--by", "bo"])


def test_a_regression_rolls_the_reject_back_and_exits_1(
    home: Path, tmp_path: Path
) -> None:
    registry = make_registry(tmp_path / "reg")
    assert forgetful_reject(registry) == 1
    assert status_on_disk(registry, "widgets-4-1") == "Inferred"
    assert "4" in raw_entries(registry)
    assert (home / ".knack" / "corrections.jsonl").read_text() == ""


def test_a_regression_prints_what_regressed(
    home: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    forgetful_reject(make_registry(tmp_path / "reg"))
    out = capsys.readouterr().out
    assert "widgets-4-1: Inferred -> Unknown rolled back" in out
    assert "widgets-3-1 (#3) no longer extracted" in out
    assert "'alternative of widgets-3-1'" in out and "'quote of widgets-3-1'" in out


def no_token(extractor: str = "spark") -> tuple[FakeGitHub, FakeSpark]:
    raise MissingCredentials("GITHUB_TOKEN is not set")


def test_gate_without_credentials_exits_2_before_correcting(
    home: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "live_clients", no_token)
    registry = make_registry(tmp_path / "reg")
    assert cli.main(["confirm", "widgets-4-1", "--registry", str(registry)]) == 2
    err = capsys.readouterr().err
    assert "GITHUB_TOKEN is not set" in err and "--no-gate" in err
    assert status_on_disk(registry, "widgets-4-1") == "Inferred"
