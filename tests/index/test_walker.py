from pathlib import Path

import pytest
from knack.index.walker import find_python_files, IndexerError


def touch(repo: Path, relative: str) -> None:
    # Creates an empty file and any missing parent dirs.
    target = repo / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.touch()


def test_nested_python_files_are_found_as_sorted_relative_paths(
    tmp_path: Path,
) -> None:
    for relative in ["pkg/sub/deep.py", "main.py", "pkg/a.py"]:
        touch(tmp_path, relative)
    assert find_python_files(tmp_path) == [
        Path("main.py"),
        Path("pkg/a.py"),
        Path("pkg/sub/deep.py"),
    ]


def test_non_python_files_are_ignored(tmp_path: Path) -> None:
    for relative in ["app.py", "README.md", "app.pyc", "data.json", "py"]:
        touch(tmp_path, relative)
    assert find_python_files(tmp_path) == [Path("app.py")]


def test_tooling_and_hidden_dirs_are_skipped(tmp_path: Path) -> None:
    skipped = [".git", ".venv", "venv", "__pycache__", "node_modules", ".knack"]
    for name in [*skipped, ".hidden", "pkg/.cache"]:
        touch(tmp_path, f"{name}/inside.py")
    touch(tmp_path, "pkg/kept.py")
    assert find_python_files(tmp_path) == [Path("pkg/kept.py")]


def test_symlinked_directory_is_not_followed(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    touch(outside, "elsewhere.py")
    repo = tmp_path / "repo"
    touch(repo, "real.py")
    (repo / "linked").symlink_to(outside, target_is_directory=True)
    assert find_python_files(repo) == [Path("real.py")]


def test_empty_repo_returns_empty_list(tmp_path: Path) -> None:
    assert find_python_files(tmp_path) == []


def test_nonexistent_root_raises_indexer_error(tmp_path: Path) -> None:
    with pytest.raises(IndexerError):
        find_python_files(tmp_path / "missing")


def test_file_as_root_raises_indexer_error(tmp_path: Path) -> None:
    touch(tmp_path, "not_a_dir.py")
    with pytest.raises(IndexerError):
        find_python_files(tmp_path / "not_a_dir.py")
