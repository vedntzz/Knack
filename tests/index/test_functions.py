from pathlib import Path
from textwrap import dedent

import pytest
from knack.index.functions import extract_functions, IndexedFunction
from knack.index.walker import IndexerError

FILE = Path("pkg/mod.py")
PRE_FIX = Path(__file__).parents[1] / "guard" / "fixtures" / "pre_fix.py"


def extract(source: str) -> list[IndexedFunction]:
    # Dedents inline test source before indexing it.
    return extract_functions(dedent(source), FILE)


def test_top_level_function_has_qualname_line_and_end_line() -> None:
    source = """
        import os

        def load(path):
            data = os.read(path)
            return data
    """
    assert extract(source) == [
        IndexedFunction(file=FILE, qualname="load", line=4, end_line=6)
    ]


def test_async_def_is_included() -> None:
    source = """
        async def fetch():
            return 1
    """
    assert [f.qualname for f in extract(source)] == ["fetch"]


def test_method_qualname_is_class_dot_method() -> None:
    source = """
        class Store:
            def save(self):
                pass
    """
    assert [f.qualname for f in extract(source)] == ["Store.save"]


def test_nested_function_qualname_is_outer_dot_inner() -> None:
    source = """
        def outer():
            def inner():
                pass
            return inner
    """
    assert [f.qualname for f in extract(source)] == ["outer", "outer.inner"]


def test_decorated_function_line_is_def_line_not_decorator() -> None:
    source = """
        @cache
        @route("/x")
        def handler():
            pass
    """
    assert [(f.line, f.end_line) for f in extract(source)] == [(4, 5)]


def test_source_without_functions_returns_empty_list() -> None:
    assert extract("x = 1\nclass Empty:\n    pass\n") == []


def test_syntax_error_raises_indexer_error_naming_the_file() -> None:
    with pytest.raises(IndexerError, match="pkg/mod.py"):
        extract("def broken(:\n")


def test_null_byte_raises_indexer_error_naming_the_file() -> None:
    with pytest.raises(IndexerError, match="pkg/mod.py"):
        extract("x = 1\0\n")


def test_pre_fix_fixture_yields_get_dags() -> None:
    functions = extract_functions(PRE_FIX.read_text(), PRE_FIX)
    assert "get_dags" in [f.qualname for f in functions]
