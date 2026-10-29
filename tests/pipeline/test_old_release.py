from pathlib import Path

import pytest
from conftest import (
    BASE,
    clean_tree,
    FakeGitHub,
    FakeSpark,
    REPO,
    STRUCTURAL,
    VIOLATIONS,
    write_tree,
)
from knack import cli
from knack.pipeline.init import run_init
from knack.walk.registry import load_registry

# PR #9 merged 2026-10-01; 0.115.0 is the last release tagged before it.
TAGS = {
    "0.116.0": "2026-10-02T00:00:00Z",
    "0.115.0": "2026-09-15T00:00:00Z",
    "0.114.0": "2026-08-01T00:00:00Z",
}
OLD_VIOLATION = {"pkg/old.py": VIOLATIONS[0]}
Run = tuple[list[str], FakeSpark, FakeGitHub]


def init(
    tmp_path: Path,
    old: dict[str, dict[str, str]],
    tags: dict[str, str] = TAGS,
    old_ref: str | None = None,
) -> Run:
    # Init with the fake repo's release tags and a checkout per old release.
    lines, spark = list[str](), FakeSpark([STRUCTURAL])
    github = FakeGitHub(clean_tree(tmp_path))
    github.tag_names = tags
    github.old_trees = {ref: write_tree(tmp_path / ref, f) for ref, f in old.items()}
    out = tmp_path / "out"
    run_init(REPO, 50, out, github, spark, lines.append, old_ref=old_ref)
    return lines, spark, github


def rule_names(tmp_path: Path) -> list[str]:
    return [
        e.rule.name for e in load_registry(tmp_path / "out" / "registry.json").rules
    ]


def test_previous_release_matches_feed_the_repair_loop(tmp_path: Path) -> None:
    lines, spark, github = init(tmp_path, {"0.115.0": OLD_VIOLATION})
    retry = spark.compile_prompts()[1]
    assert github.refs_checked_out == ["0.115.0"]
    assert "release 0.115.0 must flag 0 outside this PR's files" in retry
    assert "pkg/old.py:4" in retry
    assert rule_names(
        tmp_path
    ) == [] and "1 false positives on release 0.115.0" in "\n".join(lines)


def test_a_rule_clean_on_the_previous_release_is_proven(tmp_path: Path) -> None:
    init(tmp_path, {"0.115.0": {"pkg/util.py": "X = 1\n"}})
    assert rule_names(tmp_path) == ["9.yml"]


def test_previous_release_matches_in_the_prs_files_do_not_count(tmp_path: Path) -> None:
    init(tmp_path, {"0.115.0": {"pkg/loader.py": BASE}})
    assert rule_names(tmp_path) == ["9.yml"]


def test_old_ref_overrides_the_detected_tag(tmp_path: Path) -> None:
    old = {"0.115.0": OLD_VIOLATION, "0.114.0": {"pkg/util.py": "X = 1\n"}}
    lines, _, github = init(tmp_path, old, old_ref="0.114.0")
    assert github.refs_checked_out == ["0.114.0"] and github.tag_reads == 0
    assert "  #9 old release: 0.114.0 (--old-ref)" in lines
    assert rule_names(tmp_path) == ["9.yml"]


def test_the_compile_stage_logs_each_prs_detected_release(tmp_path: Path) -> None:
    lines, _, _ = init(tmp_path, {"0.115.0": {}})
    start = lines.index("[4/5] compile  1 PRs with a verbatim rejected alternative")
    expected = "  #9 old release: 0.115.0 (last release before merge 2026-10-01)"
    assert lines[start + 1] == expected


def test_a_release_tagged_after_the_merge_is_never_the_old_release(
    tmp_path: Path,
) -> None:
    # By version 0.116.0 is the previous minor, but it was tagged after the merge.
    tags = {**TAGS, "0.117.0": "2026-10-20T00:00:00Z"}
    old = {"0.116.0": OLD_VIOLATION, "0.115.0": {"pkg/util.py": "X = 1\n"}}
    _, _, github = init(tmp_path, old, tags=tags)
    assert github.refs_checked_out == ["0.115.0"] and rule_names(tmp_path) == ["9.yml"]


def test_without_release_tags_the_old_release_check_is_skipped(tmp_path: Path) -> None:
    lines, _, github = init(tmp_path, {}, tags={})
    assert github.refs_checked_out == [] and rule_names(tmp_path) == ["9.yml"]
    expected = "  #9 old release: none before merge 2026-10-01, check skipped"
    assert expected in lines


def test_cli_old_ref_reaches_init(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seen: list[str | None] = []

    def fake_init(*args: object, old_ref: str | None = None) -> None:
        seen.append(old_ref)

    monkeypatch.setattr(cli, "live_clients", no_clients)
    monkeypatch.setattr(cli, "run_init", fake_init)
    args = ["init", "--repo", "acme/widgets", "--out", str(tmp_path)]
    assert cli.main(args) == 0 and cli.main([*args, "--old-ref", "0.114.0"]) == 0
    assert seen == [None, "0.114.0"]


def no_clients(extractor: str) -> tuple[None, None]:
    return None, None
