import subprocess
from pathlib import Path

import pytest
from knack.git import git_root, head_commit, origin_repo, repo_slug

REPO_ROOT = Path(__file__).parents[1]
AIRFLOW_URL = "https://github.com/apache/airflow.git"


def make_clone(path: Path, origin: str | None) -> Path:
    # An empty git repo, optionally with an origin remote; no commits.
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    if origin is not None:
        subprocess.run(["git", "-C", str(path), "remote", "add", "origin", origin])
    return path


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/apache/airflow.git",
        "https://github.com/apache/airflow",
        "https://github.com/Apache/Airflow/",
        "git@github.com:apache/airflow.git",
        "ssh://git@github.com/apache/airflow.git",
        "apache/airflow",
    ],
)
def test_repo_slug_normalizes_remote_forms(url: str) -> None:
    assert repo_slug(url) == "apache/airflow"


def test_origin_repo_reads_the_origin_remote(tmp_path: Path) -> None:
    clone = make_clone(tmp_path / "airflow", AIRFLOW_URL)
    assert origin_repo(clone) == "apache/airflow"


def test_origin_repo_is_none_without_origin(tmp_path: Path) -> None:
    assert origin_repo(make_clone(tmp_path / "bare", None)) is None


def test_origin_repo_is_none_outside_git(tmp_path: Path) -> None:
    assert origin_repo(tmp_path) is None


def test_git_root_from_subdirectory(tmp_path: Path) -> None:
    clone = make_clone(tmp_path / "airflow", AIRFLOW_URL)
    (clone / "pkg" / "sub").mkdir(parents=True)
    assert git_root(clone / "pkg" / "sub") == clone.resolve()


def test_git_root_is_none_outside_git(tmp_path: Path) -> None:
    assert git_root(tmp_path) is None


def test_head_commit_is_a_sha_in_a_repo_with_history() -> None:
    head = head_commit(REPO_ROOT)
    assert head is not None and len(head) == 40


def test_head_commit_is_none_before_first_commit(tmp_path: Path) -> None:
    assert head_commit(make_clone(tmp_path / "fresh", AIRFLOW_URL)) is None
