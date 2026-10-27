from pathlib import Path
from textwrap import dedent

import pytest
from knack.index.calls import extract_calls, IndexedCall
from knack.index.walker import IndexerError

FILE = Path("pkg/mod.py")
PRE_FIX = Path(__file__).parents[1] / "guard" / "fixtures" / "pre_fix.py"


def extract(source: str) -> list[IndexedCall]:
    # Dedents inline test source before indexing it.
    return extract_calls(dedent(source), FILE)


def edges(source: str) -> set[tuple[str, str]]:
    # Reduces calls to (caller, callee) pairs for order-free checks.
    return {(call.caller, call.callee) for call in extract(source)}


def test_call_gives_caller_callee_and_line() -> None:
    source = """
        def load(path):
            return read(path)
    """
    assert extract(source) == [
        IndexedCall(file=FILE, caller="load", callee="read", line=3)
    ]


def test_self_method_call_keeps_self_prefix() -> None:
    source = """
        class Store:
            def save(self):
                self.helper()
    """
    assert edges(source) == {("Store.save", "self.helper")}


def test_dotted_call_gives_full_dotted_name() -> None:
    source = """
        def build():
            return os.path.join("a", "b")
    """
    assert edges(source) == {("build", "os.path.join")}


def test_call_in_nested_function_has_outer_dot_inner_caller() -> None:
    source = """
        def outer():
            def inner():
                work()
            return inner
    """
    assert edges(source) == {("outer.inner", "work")}


def test_module_level_call_has_module_caller() -> None:
    assert edges("setup()\n") == {("<module>", "setup")}


def test_decorator_call_belongs_to_enclosing_scope() -> None:
    source = """
        class Api:
            @route("/x")
            def handler(self):
                pass
    """
    assert edges(source) == {("Api", "route")}


def test_call_on_call_result_yields_both_callees() -> None:
    source = """
        def get_dags():
            SortParam(["dag_id"], DagModel).dynamic_depends()
    """
    assert edges(source) == {
        ("get_dags", "SortParam"),
        ("get_dags", "<expr>.dynamic_depends"),
    }


def test_pre_fix_fixture_has_get_dags_to_sort_param_edge() -> None:
    calls = extract_calls(PRE_FIX.read_text(), PRE_FIX)
    assert ("get_dags", "SortParam") in {(c.caller, c.callee) for c in calls}


def test_syntax_error_raises_indexer_error() -> None:
    with pytest.raises(IndexerError, match="pkg/mod.py"):
        extract("def broken(:\n")


def test_call_in_class_body_has_class_caller() -> None:
    source = """
        class Config:
            timeout = compute_timeout()
    """
    assert edges(source) == {("Config", "compute_timeout")}


def test_call_in_list_comprehension_belongs_to_enclosing_function() -> None:
    source = """
        def names(items):
            return [clean(item) for item in items]
    """
    assert edges(source) == {("names", "clean")}
