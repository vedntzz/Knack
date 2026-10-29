from pathlib import Path

import pytest
from conftest import git, make_repo, merge_pr
from knack.watch.merged import pending_prs, pr_numbers


def test_squash_and_merge_commit_subjects_name_their_pr() -> None:
    subjects = ["Merge pull request #12 from acme/x", "Fix sort keys (#11)"]
    assert pr_numbers(subjects) == [11, 12]


def test_subjects_without_a_pr_number_are_ignored() -> None:
    subjects = ["Merge branch 'main' into feature", "see #4 for context", "Bump"]
    assert pr_numbers(subjects) == []


def test_numbers_come_oldest_first_without_repeats() -> None:
    assert pr_numbers(["Again (#3)", "B (#5)", "A (#3)"]) == [3, 5]


@pytest.mark.usefixtures("isolated_git")
def test_squash_merge_after_the_baseline_is_pending(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "widgets")
    seen = git(repo, "rev-parse", "HEAD").strip()
    merge_pr(repo)
    assert pending_prs(repo, seen) == [9]


@pytest.mark.usefixtures("isolated_git")
def test_merge_commit_is_pending_but_its_branch_commits_are_not(
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path / "widgets")
    seen = git(repo, "rev-parse", "HEAD").strip()
    merge_pr(repo, subject="Loop instead (#77)", no_ff=True)
    assert pending_prs(repo, seen) == [9]


@pytest.mark.usefixtures("isolated_git")
def test_nothing_is_pending_at_the_baseline(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "widgets")
    assert pending_prs(repo, git(repo, "rev-parse", "HEAD").strip()) == []


@pytest.mark.usefixtures("isolated_git")
def test_no_baseline_or_a_foreign_one_never_replays_history(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "widgets")
    merge_pr(repo)
    assert pending_prs(repo, None) == []
    assert pending_prs(repo, "0" * 40) == []
