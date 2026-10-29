from collections.abc import Callable
from pathlib import Path

import pytest
from conftest import (
    clean_tree,
    EXTRACTIONS,
    FakeGitHub,
    FakeSpark,
    git,
    make_repo,
    MEMORIZED,
    merge_pr,
    STRUCTURAL,
)
from knack.pipeline.clients import MissingCredentials
from knack.pipeline.ports import GitHub, Spark
from knack.roots.corrections import (
    append_correction,
    few_shot_block,
    recent_corrections,
)
from knack.roots.store import load_roots
from knack.walk.registry import load_registry, Registry, RegistryEntry
from knack.watch.run import run_pending
from knack.watch.state import read_seen, watch_lock, write_seen
from test_corroborate import FakeSparkOpen
from test_init import rejection, root

Clients = Callable[[], tuple[GitHub, Spark] | tuple[GitHub, Spark, Spark]]


class Setup:
    # A clone with a baseline, a registry holding one earlier rule, and fakes.
    def __init__(self, tmp_path: Path, *rules: str) -> None:
        self.repo = make_repo(tmp_path / "widgets")
        self.out = tmp_path / "reg"
        self.registry = write_registry(self.out)
        self.github = FakeGitHub(clean_tree(tmp_path))
        self.spark = FakeSpark(list(rules or [STRUCTURAL]))
        self.lines = list[str]()
        write_seen(self.out, head(self.repo))

    def clients(self) -> tuple[GitHub, Spark]:
        return self.github, self.spark

    def run(self, clients: Clients | None = None) -> Path | None:
        chosen = clients or self.clients
        return run_pending(self.repo, self.registry, chosen, self.lines.append)


def head(repo: Path) -> str:
    return git(repo, "rev-parse", "HEAD").strip()


def write_registry(out: Path) -> Path:
    (out / "rules").mkdir(parents=True)
    (out / "rules" / "1.yml").write_text("id: widgets-1\n")
    entry = RegistryEntry(rule=Path("rules/1.yml"), root_ids=["widgets-1-1"])
    registry = Registry(repo="acme/widgets", roots_dir=Path("roots"), rules=[entry])
    (out / "registry.json").write_text(registry.model_dump_json())
    return out / "registry.json"


def no_credentials() -> tuple[GitHub, Spark]:
    raise MissingCredentials("GITHUB_TOKEN is not set")


@pytest.fixture
def setup(tmp_path: Path, isolated_git: None) -> Setup:
    return Setup(tmp_path)


def test_one_real_merge_appends_one_new_rule(setup: Setup) -> None:
    merge_pr(setup.repo)
    assert setup.run() == setup.registry
    rules = [(e.rule.name, e.root_ids) for e in load_registry(setup.registry).rules]
    assert rules == [("1.yml", ["widgets-1-1"]), ("9.yml", ["widgets-9-1"])]
    assert (setup.out / "rules" / "9.yml").read_text().startswith("id: widgets-9\n")


def test_the_run_prints_the_staged_progress_log(setup: Setup) -> None:
    merge_pr(setup.repo)
    setup.run()
    assert setup.lines[0] == "knack watch acme/widgets: 1 merged PR: #9"
    assert setup.lines[1] == "[1/5] select   1 PRs read, 1 kept"
    assert "  #9: 1 decision, 1 rejected alternative" in setup.lines
    assert "  #9 proven on attempt 1" in setup.lines
    assert setup.lines[-1].startswith(
        "[5/5] install  1 rules proven, 0 discarded, 2 in registry -> "
    )


def test_rules_are_proven_against_the_merged_clone_not_a_new_clone(
    setup: Setup,
) -> None:
    merge_pr(setup.repo)
    setup.run()
    assert setup.github.checkouts == 0


def test_the_baseline_moves_so_a_merge_is_processed_once(setup: Setup) -> None:
    merge_pr(setup.repo)
    setup.run()
    asked, setup.lines[:] = len(setup.spark.prompts), []
    assert read_seen(setup.out) == head(setup.repo)
    assert setup.run() is None
    assert setup.lines == [] and len(setup.spark.prompts) == asked


def test_unprovable_rule_leaves_the_registry_as_it_was(
    tmp_path: Path, isolated_git: None
) -> None:
    setup = Setup(tmp_path, MEMORIZED)
    merge_pr(setup.repo)
    setup.run()
    assert [e.rule.name for e in load_registry(setup.registry).rules] == ["1.yml"]
    assert "0 rules proven, 1 discarded, 1 in registry" in setup.lines[-1]


def test_a_clone_of_another_repo_is_ignored(setup: Setup) -> None:
    git(setup.repo, "remote", "set-url", "origin", "https://github.com/other/thing.git")
    merge_pr(setup.repo)
    assert setup.run() is None and setup.spark.prompts == []


def test_without_a_baseline_the_first_run_only_records_one(
    setup: Setup,
) -> None:
    (setup.out / "watch.json").unlink()
    merge_pr(setup.repo)
    assert setup.run() is None and setup.spark.prompts == []
    assert read_seen(setup.out) == head(setup.repo)


def test_missing_credentials_keep_the_merge_pending(setup: Setup) -> None:
    before = read_seen(setup.out)
    merge_pr(setup.repo)
    with pytest.raises(MissingCredentials):
        setup.run(no_credentials)
    assert read_seen(setup.out) == before


def test_a_run_already_in_progress_is_left_alone(setup: Setup) -> None:
    merge_pr(setup.repo)
    with watch_lock(setup.out) as acquired:
        assert acquired and setup.run() is None
    assert setup.spark.prompts == []
    assert setup.run() == setup.registry


def test_watch_runs_teach_the_extract_prompt_from_corrections(
    setup: Setup, corrections: Path
) -> None:
    append_correction(
        rejection(root("widgets-2-1", "Inferred"), "misread"), corrections
    )
    merge_pr(setup.repo)
    setup.run()
    extract = [p for p in setup.spark.prompts if p.startswith("You are reading")]
    lessons = few_shot_block(recent_corrections(corrections))
    assert extract and "misread" in lessons and all(lessons in p for p in extract)


def test_clients_with_a_second_extractor_corroborate_the_run(setup: Setup) -> None:
    second = FakeSparkOpen({**EXTRACTIONS})
    merge_pr(setup.repo)
    setup.run(lambda: (setup.github, setup.spark, second))
    roots = load_roots(setup.out / "roots")
    assert [(r.id, r.status) for r in roots] == [("widgets-9-1", "Corroborated")]
    assert any("1 corroborated, 0 uncorroborated" in line for line in setup.lines)
