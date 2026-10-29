from pathlib import Path

import pytest
from conftest import clean_tree, FakeGitHub, REPO
from knack.pipeline.select import is_doc, is_test, qualifies, select_prs


@pytest.mark.parametrize(
    "path",
    ["tests/test_x.py", "pkg/tests/helpers.py", "pkg/test_y.py", "pkg/conftest.py"],
)
def test_test_paths_are_recognised(path: str) -> None:
    assert is_test(path)


@pytest.mark.parametrize("path", ["docs/guide.py", "pkg/docs/a.txt", "README.md"])
def test_doc_paths_are_recognised(path: str) -> None:
    assert is_doc(path)


def test_source_path_is_neither_test_nor_doc() -> None:
    assert not is_test("pkg/latest.py") and not is_doc("pkg/latest.py")


@pytest.mark.parametrize(
    ("paths", "expected"),
    [
        (["pkg/a.py"], True),
        (["pkg/a.py", "tests/test_a.py", "docs/a.md"], True),
        ([f"pkg/m{i}.py" for i in range(5)], True),
        ([f"pkg/m{i}.py" for i in range(6)], False),
        (["tests/test_a.py"], False),
        (["pkg/a.js", "README.md"], False),
        ([], False),
    ],
)
def test_qualifies_needs_one_to_five_python_files_beyond_tests_and_docs(
    paths: list[str], expected: bool
) -> None:
    assert qualifies(paths) is expected


def test_selection_keeps_long_described_source_prs_newest_first(
    tmp_path: Path,
) -> None:
    selection = select_prs(FakeGitHub(clean_tree(tmp_path)), REPO, 50)
    assert [pr.number for pr in selection.prs] == [9, 4, 3, 2]
    assert selection.read == 8


def test_kept_pr_carries_shas_and_python_files(tmp_path: Path) -> None:
    pr = select_prs(FakeGitHub(clean_tree(tmp_path)), REPO, 1).prs[0]
    assert (pr.base_sha, pr.head_sha) == ("base9", "head9")
    assert pr.python_files == ["pkg/loader.py", "tests/test_loader.py"]


def test_selection_stops_reading_once_the_limit_is_kept(tmp_path: Path) -> None:
    github = FakeGitHub(clean_tree(tmp_path))
    selection = select_prs(github, REPO, 2)
    assert [pr.number for pr in selection.prs] == [9, 4]
    assert selection.read == github.summaries_read == 6
