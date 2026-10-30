import re
from collections.abc import Callable
from functools import cache
from pathlib import Path
from typing import Protocol

from knack.pipeline.models import Decision, PullSummary
from knack.roots.store import find_root, load_roots, write_root

# Merge and automation accounts whose names do not end in "bot".
MERGE_BOTS = frozenset(
    {"bors", "bors-ng", "homu", "mergify", "kodiakhq", "github-actions", "renovate"}
)
LOGIN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*(?:\[bot\])?")
PR_NUMBER = re.compile(r"/pull/(\d+)")


class Reviews(Protocol):
    # The two GitHub reads attribution needs; GitHubApi satisfies it.
    def summary(self, repo: str, number: int) -> PullSummary: ...

    def approvers(self, repo: str, number: int) -> list[str]: ...


def is_bot(login: str) -> bool:
    name = login.strip().lower()
    return name.endswith("[bot]") or name.endswith("bot") or name in MERGE_BOTS


def names_a_bot(decided_by: str) -> bool:
    # Any bot login in the text counts, so "merged by pytorchbot" is caught too.
    return any(is_bot(token) for token in LOGIN.findall(decided_by))


def human_attribution(author: str, approvers: list[str]) -> str:
    # The PR author, then each human approver once; empty when no human is on record.
    humans = [a for a in dict.fromkeys(approvers) if a != author and not is_bot(a)]
    parts = [] if is_bot(author) else [f"{author} (author)"]
    parts += [f"approved by {', '.join(humans)}"] if humans else []
    return "; ".join(parts)


def attribute(
    decisions: list[Decision], author: str, approvers: Callable[[], list[str]]
) -> list[Decision]:
    # Approvers are fetched once, and only if a decision names a bot.
    fetch = cache(approvers)
    return [_attributed(decision, author, fetch) for decision in decisions]


def reattribute_roots(directory: Path, repo: str, github: Reviews) -> list[str]:
    # Rewrites, in place, each root whose decided_by names a bot; returns their ids.
    stale = [root for root in load_roots(directory) if names_a_bot(root.decided_by)]
    for root in stale:
        _rewrite(
            directory, root.id, _pr_attribution(str(root.source_url), repo, github)
        )
    return [root.id for root in stale]


def _pr_attribution(source_url: str, repo: str, github: Reviews) -> str:
    # The root's own PR, read back from GitHub: its author and approvers.
    number = int(PR_NUMBER.findall(source_url)[-1])
    author = github.summary(repo, number).author
    return human_attribution(author, github.approvers(repo, number))


def _attributed(
    decision: Decision, author: str, approvers: Callable[[], list[str]]
) -> Decision:
    if not names_a_bot(decision.decided_by):
        return decision
    fixed = human_attribution(author, approvers())
    return decision.model_copy(update={"decided_by": fixed})


def _rewrite(directory: Path, root_id: str, decided_by: str) -> None:
    # The root keeps its file and every other field.
    found = find_root(directory, root_id)
    if found is not None:
        path, root = found
        write_root(root.model_copy(update={"decided_by": decided_by}), path)
