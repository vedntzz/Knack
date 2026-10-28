from pathlib import Path
from textwrap import dedent

from knack.index.build import build_index, Index, IndexedEdge, load_index, write_index

FIXTURES = Path(__file__).parents[1] / "guard" / "fixtures"


def make_repo(root: Path, files: dict[str, str]) -> Path:
    # Writes dedented sources under root and returns root.
    for name, source in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(dedent(source))
    return root


def edge_for(index: Index, callee_text: str) -> IndexedEdge:
    # Finds the single edge whose callee text matches.
    [edge] = [e for e in index.edges if e.callee_text == callee_text]
    return edge


def test_same_file_call_resolves_as_same_file(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, {"a.py": "def helper(): pass\ndef run(): helper()\n"})
    edge = edge_for(build_index(repo), "helper")
    assert (edge.resolution, edge.target_file, edge.target_qualname) == (
        "same_file",
        Path("a.py"),
        "helper",
    )


def test_cross_file_call_to_unique_name_resolves_as_unique_name(
    tmp_path: Path,
) -> None:
    files = {"a.py": "def helper(): pass\n", "b.py": "def run(): helper()\n"}
    edge = edge_for(build_index(make_repo(tmp_path, files)), "helper")
    assert (edge.resolution, edge.target_file, edge.target_qualname) == (
        "unique_name",
        Path("a.py"),
        "helper",
    )


def test_name_defined_in_two_files_stays_unresolved(tmp_path: Path) -> None:
    files = {
        "a.py": "def helper(): pass\n",
        "b.py": "def helper(): pass\n",
        "c.py": "def run(): helper()\n",
    }
    edge = edge_for(build_index(make_repo(tmp_path, files)), "helper")
    assert (edge.resolution, edge.target_file, edge.target_qualname) == (
        "unresolved",
        None,
        None,
    )


def test_self_method_call_resolves_to_class_method_in_same_file(
    tmp_path: Path,
) -> None:
    source = """
        class Store:
            def helper(self):
                pass

            def save(self):
                self.helper()
    """
    edge = edge_for(build_index(make_repo(tmp_path, {"s.py": source})), "self.helper")
    assert (edge.caller, edge.resolution, edge.target_qualname) == (
        "Store.save",
        "same_file",
        "Store.helper",
    )


def test_syntax_error_file_is_skipped_and_rest_indexed(tmp_path: Path) -> None:
    files = {"bad.py": "def broken(:\n", "good.py": "def ok(): pass\n"}
    index = build_index(make_repo(tmp_path, files))
    assert index.skipped == [Path("bad.py")]
    assert [f.qualname for f in index.functions] == ["ok"]


def test_index_round_trips_through_json(tmp_path: Path) -> None:
    files = {
        "a.py": "def helper(): pass\n",
        "b.py": "def run(): helper()\n",
        "c.py": "x(\n",
    }
    index = build_index(make_repo(tmp_path / "repo", files))
    write_index(index, tmp_path / "out" / "index.json")
    assert load_index(tmp_path / "out" / "index.json") == index


def test_guard_fixtures_index_with_get_dags() -> None:
    index = build_index(FIXTURES)
    assert "get_dags" in {f.qualname for f in index.functions}
