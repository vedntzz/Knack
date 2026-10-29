import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import (
    clean_tree,
    FakeGitHub,
    FakeSpark,
    git,
    make_repo,
    merge_pr,
    STRUCTURAL,
    VIOLATIONS,
)
from knack import cli
from knack.walk.registry import home_registry_dir, Registry
from knack.watch.run import run_pending
from knack.watch.state import write_seen


@pytest.fixture
def home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("KNACK_REGISTRY", raising=False)
    return tmp_path / "home"


def empty_home_registry(repo: Path) -> Path:
    # What knack init leaves before any rule: a registry and a baseline at HEAD.
    path = home_registry_dir("acme/widgets") / "registry.json"
    path.parent.mkdir(parents=True)
    registry = Registry(repo="acme/widgets", roots_dir=Path("roots"), rules=[])
    path.write_text(registry.model_dump_json())
    write_seen(path.parent, git(repo, "rev-parse", "HEAD").strip())
    return path


def watch_merge(tmp_path: Path, repo: Path, registry: Path) -> None:
    # The post-merge run, with fakes in place of GitHub and Spark.
    clients = FakeGitHub(clean_tree(tmp_path)), FakeSpark([STRUCTURAL])
    merge_pr(repo)
    assert run_pending(repo, registry, lambda: clients, print) == registry


def pretool(repo: Path, home: Path) -> subprocess.CompletedProcess[bytes]:
    # The hook exactly as Muse Code runs it: no KNACK_REGISTRY, cwd in the clone.
    tool_input = {"path": "pkg/fetch.py", "content": VIOLATIONS[0]}
    event = {"tool_name": "write_file", "tool_input": tool_input, "cwd": str(repo)}
    env = {k: v for k, v in os.environ.items() if not k.startswith("KNACK_")}
    argv = [sys.executable, "-m", "knack.hooks.pretool"]
    payload = json.dumps(event).encode()
    env["HOME"] = str(home)
    return subprocess.run(argv, input=payload, capture_output=True, cwd=repo, env=env)


def test_a_rule_written_by_watch_is_enforced_by_the_pretool_hook(
    home: Path,
    tmp_path: Path,
    isolated_git: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = make_repo(tmp_path / "widgets")
    watch_merge(tmp_path, repo, empty_home_registry(repo))
    # Inferred until a human confirms it: advises, never blocks.
    assert pretool(repo, home).stdout == b""
    monkeypatch.chdir(repo)
    assert cli.main(["confirm", "widgets-9-1", "--by", "maria"]) == 0
    output = json.loads(pretool(repo, home).stdout)["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny"
    assert (
        "https://github.com/acme/widgets/pull/9" in output["permissionDecisionReason"]
    )
