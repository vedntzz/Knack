import json
from pathlib import Path

import pytest
from conftest import git, make_repo
from knack import cli
from knack.watch.state import read_seen
from test_watch_run import head, write_registry


@pytest.fixture
def repo(tmp_path: Path, isolated_git: None, monkeypatch: pytest.MonkeyPatch) -> Path:
    # A clone of acme/widgets as cwd, with knack init's registry in a temp HOME.
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = make_repo(tmp_path / "widgets")
    monkeypatch.chdir(repo)
    return repo


def home_out(tmp_path: Path) -> Path:
    return tmp_path / "home" / ".knack" / "registries" / "acme-widgets"


def watch(settings: Path, *extra: str) -> int:
    return cli.main(["watch", "--muse-settings", str(settings), *extra])


def test_watch_installs_both_hooks_and_a_baseline(
    repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_registry(home_out(tmp_path))
    settings = tmp_path / "muse.json"
    assert watch(settings) == 0
    assert (repo / ".git" / "hooks" / "post-merge").exists()
    assert "PostToolBatch" in json.loads(settings.read_text())["hooks"]
    assert read_seen(home_out(tmp_path)) == head(repo)
    printed = capsys.readouterr().out
    assert printed.startswith("knack watch acme/widgets\n")
    assert f"watching merges after {head(repo)[:7]}" in printed


def test_explicit_registry_is_used(repo: Path, tmp_path: Path) -> None:
    out = tmp_path / "elsewhere"
    write_registry(out)
    assert watch(tmp_path / "muse.json", "--registry", str(out / "registry.json")) == 0
    assert read_seen(out) == head(repo)


def test_without_a_registry_watch_points_at_init(
    repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert watch(tmp_path / "muse.json") == 2
    assert "knack init --repo acme/widgets" in capsys.readouterr().err
    assert not (repo / ".git" / "hooks" / "post-merge").exists()


def test_registry_for_another_repo_is_refused(
    repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_registry(home_out(tmp_path))
    git(repo, "remote", "set-url", "origin", "https://github.com/other/thing.git")
    out = home_out(tmp_path) / "registry.json"
    assert watch(tmp_path / "muse.json", "--registry", str(out)) == 2
    assert "other/thing" in capsys.readouterr().err


def test_outside_a_git_repo_watch_exits_2(
    tmp_path: Path, isolated_git: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert watch(tmp_path / "muse.json") == 2


def test_a_foreign_post_merge_hook_exits_2_untouched(
    repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_registry(home_out(tmp_path))
    hook = repo / ".git" / "hooks" / "post-merge"
    hook.write_text("#!/bin/sh\nmake deps\n")
    assert watch(tmp_path / "muse.json") == 2
    assert hook.read_text() == "#!/bin/sh\nmake deps\n"
    assert "post-merge" in capsys.readouterr().err
