import re
from pathlib import Path

from knack.git import git_output

# GitHub's merge-commit subject, and its squash-merge suffix.
PR_SUBJECT = re.compile(r"^Merge pull request #(\d+) |\(#(\d+)\)$")


def pr_numbers(subjects: list[str]) -> list[int]:
    # git log lists newest first; numbers come back oldest first, once each.
    found = [PR_SUBJECT.search(subject.strip()) for subject in reversed(subjects)]
    numbers = [int(m.group(1) or m.group(2)) for m in found if m]
    return list(dict.fromkeys(numbers))


def pending_prs(root: Path, seen: str | None) -> list[int]:
    # PRs merged onto this branch since seen; none without a baseline HEAD descends from.
    if seen is None or not _is_ancestor(root, seen):
        return []
    log = git_output(root, "log", "--first-parent", "--format=%s", f"{seen}..HEAD")
    return pr_numbers((log or "").splitlines())


def _is_ancestor(root: Path, commit: str) -> bool:
    return git_output(root, "merge-base", "--is-ancestor", commit, "HEAD") is not None
