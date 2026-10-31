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
from knack.contracts.models import DecisionStatus, Root
from knack.pipeline.init import run_init
from knack.roots.store import load_roots, write_root
from knack.walk.registry import home_registry_dir, Registry, RegistryEntry
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
    # The regression gate has its own tests; this one is about the hook.
    assert cli.main(["confirm", "widgets-9-1", "--by", "maria", "--no-gate"]) == 0
    output = json.loads(pretool(repo, home).stdout)["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny"
    assert (
        "https://github.com/acme/widgets/pull/9" in output["permissionDecisionReason"]
    )


# Imported rules 5 and 77, and widgets-9-1 a human already confirmed elsewhere.
IMPORTED: dict[str, DecisionStatus] = {
    "widgets-5-1": "Confirmed",
    "widgets-77-1": "Inferred",
    "widgets-9-1": "Confirmed",
}


def imported_root(root_id: str, status: DecisionStatus) -> Root:
    url = f"https://github.com/acme/widgets/pull/{root_id.split('-')[1]}"
    fields = {"id": root_id, "title": "t", "source_url": url, "status": status}
    fields |= {"decision": "Read blobs one at a time", "why": "w", "decided_by": "m"}
    return Root.model_validate({**fields, "quote": "q", "rejected_alternative": "a"})


def team_registry(out: Path) -> Path:
    # A registry a teammate shares: two rules and three roots.
    for root_id, status in IMPORTED.items():
        write_root(imported_root(root_id, status), out / "roots" / f"{root_id}.json")
    (out / "rules").mkdir(parents=True)
    rules = [team_rule(out, number) for number in ("5", "77")]
    registry = Registry(repo="acme/widgets", roots_dir=Path("roots"), rules=rules)
    (out / "registry.json").write_text(registry.model_dump_json())
    return out / "registry.json"


def team_rule(out: Path, number: str) -> RegistryEntry:
    (out / "rules" / f"{number}.yml").write_text(f"id: team-{number}\n")
    ids = [f"widgets-{number}-1"]
    return RegistryEntry(rule=Path("rules") / f"{number}.yml", root_ids=ids)


def init_after_import(tmp_path: Path) -> Path:
    assert cli.main(["import", "--registry", str(team_registry(tmp_path / "t"))]) == 0
    clients = FakeGitHub(clean_tree(tmp_path)), FakeSpark([STRUCTURAL])
    home_dir = home_registry_dir("acme/widgets")
    return run_init("acme/widgets", 50, home_dir, *clients, log=lambda _: None)


def test_init_after_import_keeps_every_imported_rule(
    home: Path, tmp_path: Path
) -> None:
    path = init_after_import(tmp_path)
    registry = Registry.model_validate_json(path.read_text())
    assert [(e.rule.name, e.root_ids) for e in registry.rules] == [
        ("5.yml", ["widgets-5-1"]),
        ("77.yml", ["widgets-77-1"]),
        ("9.yml", ["widgets-9-1"]),
    ]
    assert (path.parent / "rules" / "77.yml").read_text() == "id: team-77\n"


def test_init_after_import_never_touches_a_reviewed_root(
    home: Path, tmp_path: Path
) -> None:
    path = init_after_import(tmp_path)
    roots = {r.id: r for r in load_roots(path.parent / "roots")}
    assert {i: r.status for i, r in roots.items()} == IMPORTED
    assert roots["widgets-9-1"] == imported_root("widgets-9-1", "Confirmed")
