from pathlib import Path

import pytest
from knack.index import cache
from knack.index.build import build_index, Index
from knack.index.cache import cache_path, cached_index

HEAD = "a" * 40
OTHER_HEAD = "b" * 40


def make_repo(root: Path) -> Path:
    root.mkdir()
    (root / "a.py").write_text("def helper():\n    pass\n")
    return root


def count_builds(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    # Records every real build the cache asks for.
    calls: list[Path] = []

    def counting_build(repo_root: Path) -> Index:
        calls.append(repo_root)
        return build_index(repo_root)

    monkeypatch.setattr(cache, "build_index", counting_build)
    return calls


def test_cache_path_is_repo_slug_then_head(tmp_path: Path) -> None:
    path = cache_path(tmp_path, "apache/airflow", HEAD)
    assert path == tmp_path / "apache-airflow" / f"{HEAD}.json"


def test_second_run_with_same_head_does_not_rebuild(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls, repo = count_builds(monkeypatch), make_repo(tmp_path / "repo")
    first = cached_index(repo, "apache/airflow", HEAD, tmp_path / "cache")
    second = cached_index(repo, "apache/airflow", HEAD, tmp_path / "cache")
    assert len(calls) == 1 and first == second
    assert cache_path(tmp_path / "cache", "apache/airflow", HEAD).is_file()


def test_new_head_rebuilds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls, repo = count_builds(monkeypatch), make_repo(tmp_path / "repo")
    cached_index(repo, "apache/airflow", HEAD, tmp_path / "cache")
    cached_index(repo, "apache/airflow", OTHER_HEAD, tmp_path / "cache")
    assert len(calls) == 2


def test_no_head_builds_every_time_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls, repo = count_builds(monkeypatch), make_repo(tmp_path / "repo")
    cached_index(repo, "apache/airflow", None, tmp_path / "cache")
    cached_index(repo, "apache/airflow", None, tmp_path / "cache")
    assert len(calls) == 2 and not (tmp_path / "cache").exists()


def test_cached_index_reports_the_current_checkout_root(tmp_path: Path) -> None:
    cached_index(make_repo(tmp_path / "one"), "apache/airflow", HEAD, tmp_path / "c")
    two = make_repo(tmp_path / "two")
    assert cached_index(two, "apache/airflow", HEAD, tmp_path / "c").repo_root == two
