from pathlib import Path

import pytest
from conftest import clean_tree, FakeGitHub, FakeSpark, MEMORIZED, REPO, STRUCTURAL
from knack.pipeline.github import GitHubApi
from knack.pipeline.init import run_init
from knack.roots.store import load_roots
from knack.walk.registry import load_registry


def init(tmp_path: Path, *rules: str) -> Path:
    github = FakeGitHub(clean_tree(tmp_path))
    return run_init(
        REPO, 50, tmp_path / "out", github, FakeSpark(list(rules)), lambda line: None
    )


def test_every_root_stores_its_prs_merge_time(tmp_path: Path) -> None:
    roots = load_roots(load_registry(init(tmp_path, STRUCTURAL)).roots_dir)
    assert [(r.id, r.merged_at) for r in roots] == [("widgets-9-1", "2026-10-01")]


def test_a_proven_rule_stores_where_it_was_proven(tmp_path: Path) -> None:
    proof = load_registry(init(tmp_path, MEMORIZED, STRUCTURAL)).rules[0].proof
    assert proof is not None
    assert (proof.pr, proof.base_sha, proof.head_sha) == (9, "base9", "head9")
    assert proof.attempts == 2


def test_a_proven_rule_stores_its_base_and_head_results(tmp_path: Path) -> None:
    proof = load_registry(init(tmp_path, STRUCTURAL)).rules[0].proof
    assert proof is not None
    sides = {s.side: (s.files, s.flagged) for s in proof.sides}
    assert sides["base"] == (1, 1) and sides["head"] == (2, 0)
    assert sides["variant-violation"] == (3, 2) and sides["variant-compliant"] == (3, 0)


def test_a_proven_rule_stores_its_false_positive_counts(tmp_path: Path) -> None:
    proof = load_registry(init(tmp_path, STRUCTURAL)).rules[0].proof
    assert proof is not None
    assert (proof.false_positives, proof.old_release) == (0, None)


def test_a_proven_rule_stores_its_heldout_score(tmp_path: Path) -> None:
    proof = load_registry(init(tmp_path, STRUCTURAL)).rules[0].proof
    assert proof is not None and proof.heldout is not None
    held = proof.heldout
    assert (held.author, held.caught, held.violations) == ("fake-spark", 2, 3)
    assert (held.allowed, held.compliant, held.error) == (3, 3, None)


def test_the_proof_is_written_into_the_registry_file(tmp_path: Path) -> None:
    text = init(tmp_path, STRUCTURAL).read_text()
    assert '"proof"' in text and '"heldout"' in text and '"false_positives": 0' in text


def test_github_reads_a_prs_merge_time(monkeypatch: pytest.MonkeyPatch) -> None:
    pulls: dict[str, dict[str, str | None]] = {
        "/repos/a/b/pulls/1": {"merged_at": "2026-10-01T00:00:00Z"},
        "/repos/a/b/pulls/2": {"merged_at": None},
    }

    def get(self: GitHubApi, path: str) -> dict[str, str | None]:
        return pulls[path]

    monkeypatch.setattr(GitHubApi, "_get", get)
    github = GitHubApi("t")
    assert github.merged_at("a/b", 1) == "2026-10-01T00:00:00Z"
    assert github.merged_at("a/b", 2) is None
