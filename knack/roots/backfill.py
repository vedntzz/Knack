import re
from collections.abc import Callable
from functools import cache
from pathlib import Path

from knack.contracts.models import Root
from knack.roots.store import root_files, write_root

# (repo, PR number) -> when it merged, or None when it never did.
MergedAt = Callable[[str, int], str | None]
PULL_URL = re.compile(r"https://github\.com/([\w.-]+/[\w.-]+)/pull/(\d+)/?")


def backfill_merged_at(roots_dir: Path, merged_at: MergedAt) -> list[str]:
    # Roots cited to a merged PR and lacking merged_at get it; returns their ids.
    ask = cache(merged_at)
    missing = [(p, r) for p, r in root_files(roots_dir) if r.merged_at is None]
    filled = [_filled(path, root, ask) for path, root in missing]
    return sorted(root_id for root_id in filled if root_id)


def missing_merged_at(roots_dir: Path) -> list[str]:
    return sorted(root.id for _, root in root_files(roots_dir) if not root.merged_at)


def _filled(path: Path, root: Root, merged_at: MergedAt) -> str | None:
    # Only merged_at changes; the file keeps its name, status and quote.
    pull = PULL_URL.fullmatch(str(root.source_url))
    when = merged_at(pull[1], int(pull[2])) if pull else None
    if when is None:
        return None
    write_root(root.model_copy(update={"merged_at": when}), path)
    return root.id
