import os
import tempfile
from pathlib import Path

from knack.git import head_commit, repo_slug
from knack.home import knack_home
from knack.index.build import build_index, Index, load_index, write_index


def default_cache_dir() -> Path:
    return knack_home() / "cache"


def repo_index(repo_root: Path, repo: str) -> Index:
    # The hooks' entry: HEAD from git, cache under the user's home.
    return cached_index(repo_root, repo, head_commit(repo_root), default_cache_dir())


def cached_index(
    repo_root: Path, repo: str, head: str | None, cache_dir: Path
) -> Index:
    # No HEAD means no stable key, so a fresh repo is indexed every time.
    if head is None:
        return build_index(repo_root)
    path = cache_path(cache_dir, repo, head)
    if not path.is_file():
        _write_atomically(build_index(repo_root), path)
    return load_index(path).model_copy(update={"repo_root": repo_root})


def cache_path(cache_dir: Path, repo: str, head: str) -> Path:
    return cache_dir / repo_slug(repo).replace("/", "-") / f"{head}.json"


def _write_atomically(index: Index, path: Path) -> None:
    # A concurrent hook never reads a half-written cache file.
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    os.close(handle)
    write_index(index, Path(temp))
    os.replace(temp, path)
