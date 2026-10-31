import json
import os
import platform
import sys
from pathlib import Path

import pytest
from conftest import make_repo
from knack.watch.install import (
    add_muse_hook,
    install_post_merge,
    muse_command,
    WatchInstallError,
)

PYTHON = "/opt/knack/bin/python"
GUARD = {
    "matcher": "write_file|edit_file",
    "hooks": [{"type": "command", "command": "guard"}],
}


@pytest.fixture
def repo(tmp_path: Path, isolated_git: None) -> Path:
    return make_repo(tmp_path / "widgets")


def test_post_merge_hook_is_executable_and_never_fails_the_merge(
    repo: Path, tmp_path: Path
) -> None:
    hook = install_post_merge(repo, tmp_path / "reg" / "registry.json", PYTHON)
    assert hook == repo / ".git" / "hooks" / "post-merge"
    assert os.access(hook, os.X_OK)
    text = hook.read_text()
    assert text.startswith("#!/bin/sh\n") and text.rstrip().endswith("|| true")
    assert f"{PYTHON} -m knack.watch.hook post-merge" in text
    assert str(tmp_path / "reg" / "registry.json") in text


def test_reinstall_replaces_our_own_hook(repo: Path, tmp_path: Path) -> None:
    install_post_merge(repo, tmp_path / "old.json", PYTHON)
    hook = install_post_merge(repo, tmp_path / "new.json", PYTHON)
    assert "new.json" in hook.read_text() and "old.json" not in hook.read_text()


def test_a_foreign_post_merge_hook_is_never_overwritten(
    repo: Path, tmp_path: Path
) -> None:
    hook = repo / ".git" / "hooks" / "post-merge"
    hook.write_text("#!/bin/sh\nmake deps\n")
    with pytest.raises(WatchInstallError, match="post-merge"):
        install_post_merge(repo, tmp_path / "registry.json", PYTHON)
    assert hook.read_text() == "#!/bin/sh\nmake deps\n"


def test_muse_hook_is_added_beside_existing_hooks(tmp_path: Path) -> None:
    settings = tmp_path / "settings.json"
    settings.write_text(
        json.dumps({"schema_version": 1, "hooks": {"PreToolUse": [GUARD]}})
    )
    assert add_muse_hook(settings, tmp_path / "registry.json", PYTHON) is True
    hooks = json.loads(settings.read_text())["hooks"]
    assert hooks["PreToolUse"] == [GUARD]
    command = hooks["PostToolBatch"][0]["hooks"][0]
    assert command["type"] == "command"
    assert "-m knack.watch.hook tool-batch" in command["command"]
    assert command["command"].startswith("sh -c '") and command["command"].endswith(
        "|| true'"
    )


def test_muse_hook_is_added_once(tmp_path: Path) -> None:
    settings = tmp_path / "settings.json"
    add_muse_hook(settings, tmp_path / "registry.json", PYTHON)
    assert add_muse_hook(settings, tmp_path / "registry.json", PYTHON) is False
    assert len(json.loads(settings.read_text())["hooks"]["PostToolBatch"]) == 1


def test_missing_settings_file_is_created(tmp_path: Path) -> None:
    settings = tmp_path / "muse" / "settings.json"
    add_muse_hook(settings, tmp_path / "registry.json", PYTHON)
    assert json.loads(settings.read_text())["schema_version"] == 1


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS universal binaries only")
def test_hooks_pin_python_to_the_architecture_knack_was_installed_for(
    repo: Path, tmp_path: Path
) -> None:
    # An x86_64 git (Rosetta) would otherwise start a universal python as x86_64.
    pinned = f"/usr/bin/arch -{platform.machine()} {PYTHON} -m knack.watch.hook"
    assert pinned in install_post_merge(repo, tmp_path / "r.json", PYTHON).read_text()
    assert pinned in muse_command(PYTHON, tmp_path / "r.json")


def test_corroborate_rides_along_in_both_hook_commands(
    repo: Path, tmp_path: Path
) -> None:
    registry = tmp_path / "r.json"
    hook = install_post_merge(repo, registry, PYTHON, corroborate=True)
    assert f"post-merge --registry {registry} --corroborate" in hook.read_text()
    assert f"tool-batch --registry {registry} --corroborate" in muse_command(
        PYTHON, registry, corroborate=True
    )


def test_reinstalling_with_corroborate_replaces_our_muse_hook(tmp_path: Path) -> None:
    settings, registry = tmp_path / "settings.json", tmp_path / "r.json"
    add_muse_hook(settings, registry, PYTHON)
    assert add_muse_hook(settings, registry, PYTHON, corroborate=True) is True
    batch = json.loads(settings.read_text())["hooks"]["PostToolBatch"]
    commands = [hook["command"] for entry in batch for hook in entry["hooks"]]
    assert commands == [muse_command(PYTHON, registry, corroborate=True)]


def test_no_corroborate_rides_along_in_both_hook_commands(
    repo: Path, tmp_path: Path
) -> None:
    registry = tmp_path / "r.json"
    hook = install_post_merge(repo, registry, PYTHON, self_check=False)
    assert f"post-merge --registry {registry} --no-corroborate" in hook.read_text()
    command = muse_command(PYTHON, registry, self_check=False)
    assert f"tool-batch --registry {registry} --no-corroborate" in command


def test_switching_between_any_two_settings_leaves_one_muse_hook(
    tmp_path: Path,
) -> None:
    settings, registry = tmp_path / "settings.json", tmp_path / "r.json"
    add_muse_hook(settings, registry, PYTHON, corroborate=True)
    add_muse_hook(settings, registry, PYTHON)
    assert add_muse_hook(settings, registry, PYTHON, self_check=False) is True
    batch = json.loads(settings.read_text())["hooks"]["PostToolBatch"]
    commands = [hook["command"] for entry in batch for hook in entry["hooks"]]
    assert commands == [muse_command(PYTHON, registry, self_check=False)]
