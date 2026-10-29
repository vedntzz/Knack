from pathlib import Path

import pytest
from conftest import clean_tree, FakeGitHub, FakeSpark, STRUCTURAL
from knack import cli
from knack.pipeline.clients import live_clients, MissingCredentials
from knack.walk.registry import load_registry


@pytest.fixture
def fakes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    pair = (FakeGitHub(clean_tree(tmp_path)), FakeSpark([STRUCTURAL]))
    monkeypatch.setattr(cli, "live_clients", lambda: pair)


@pytest.mark.usefixtures("fakes")
def test_init_prints_the_staged_log_and_exits_0(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "reg"
    assert cli.main(["init", "--repo", "acme/widgets", "--out", str(out)]) == 0
    printed = capsys.readouterr().out
    assert "[1/5] select" in printed and f"{out / 'registry.json'}" in printed
    assert load_registry(out / "registry.json").repo == "acme/widgets"


@pytest.mark.usefixtures("fakes")
def test_init_defaults_to_the_home_registry_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    assert cli.main(["init", "--repo", "Acme/Widgets", "--prs", "1"]) == 0
    expected = tmp_path / "home" / ".knack" / "registries" / "acme-widgets"
    assert (expected / "registry.json").exists()


@pytest.mark.usefixtures("fakes")
def test_prs_flag_caps_the_selection(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    cli.main(
        ["init", "--repo", "acme/widgets", "--prs", "1", "--out", str(tmp_path / "r")]
    )
    assert "1 PRs read, 1 kept" in capsys.readouterr().out


@pytest.mark.parametrize("repo", ["acme", "acme/widgets/extra", "a b/c"])
def test_repo_must_be_owner_slash_name(repo: str) -> None:
    with pytest.raises(SystemExit) as raised:
        cli.main(["init", "--repo", repo])
    assert raised.value.code == 2


def test_live_clients_need_both_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("MODEL_API_KEY", "k")
    with pytest.raises(MissingCredentials, match="GITHUB_TOKEN"):
        live_clients()


def test_missing_credentials_exit_2_with_a_message(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    assert cli.main(["init", "--repo", "acme/widgets"]) == 2
    assert "MODEL_API_KEY" in capsys.readouterr().err
