import os
from collections.abc import Iterator
from pathlib import Path

SKIPPED_DIR_NAMES = frozenset(
    {".git", ".venv", "venv", "__pycache__", "node_modules", ".knack"}
)


class IndexerError(Exception):
    pass


def find_python_files(repo_root: Path) -> list[Path]:
    if not repo_root.is_dir():
        raise IndexerError(f"repo root is not a directory: {repo_root}")
    return sorted(_walk_python_files(repo_root))


def _walk_python_files(repo_root: Path) -> Iterator[Path]:
    # os.walk does not descend into symlinked dirs unless followlinks=True.
    for current, dir_names, file_names in os.walk(repo_root):
        dir_names[:] = [name for name in dir_names if not _is_skipped_dir(name)]
        for name in file_names:
            if name.endswith(".py"):
                yield (Path(current) / name).relative_to(repo_root)


def _is_skipped_dir(name: str) -> bool:
    return name in SKIPPED_DIR_NAMES or name.startswith(".")
