import ast
import random

from conftest import BASE, HEAD
from knack.pipeline.rename import (
    fresh_names,
    introduced_identifiers,
    rename_locals,
    rename_names,
)


def test_introduced_identifiers_are_head_names_missing_from_base() -> None:
    introduced = introduced_identifiers([BASE], [HEAD + "print(len(items))\n"])
    assert introduced == {"item", "append"}


def test_fresh_names_are_stable_for_one_seed() -> None:
    first = fresh_names({"b", "a"}, random.Random(3))
    assert first == fresh_names({"a", "b"}, random.Random(3))
    assert all(new.startswith("_r") for new in first.values())


def test_rename_names_rewrites_every_occurrence_and_nothing_else() -> None:
    renamed = rename_names(HEAD, {"item": "zz1", "append": "zz2"})
    assert "item " not in renamed and ".append" not in renamed
    assert "for zz1 in items" in renamed and "results.zz2(await zz1.read())" in renamed
    ast.parse(renamed)


def test_rename_names_leaves_string_prefixes_alone() -> None:
    source = 'with open(p) as f:\n    print(f"{p}", rb"x", f)\n'
    renamed = rename_names(source, {"f": "zz1", "rb": "zz2"})
    assert renamed == 'with open(p) as zz1:\n    print(f"{p}", rb"x", zz1)\n'


def test_rename_names_reaches_comments_strings_and_docstrings_by_whole_word() -> None:
    # Regex rules read text, so a name left in a docstring still memorizes the PR.
    source = 'def f():\n    """see :meth:`aget_conn`"""\n    # aget_conn here\n    x = "aget_conn"\n    return aget_connection\n'
    renamed = rename_names(source, {"aget_conn": "zz1"})
    assert renamed.count("zz1") == 3 and "aget_connection" in renamed


def test_rename_locals_keeps_parameters_and_attributes() -> None:
    renamed = rename_locals(BASE, random.Random(0))
    assert "results" not in renamed and "def load(items)" in renamed
    assert ".read() for _r" in renamed and "asyncio.gather" in renamed
    ast.parse(renamed)


def test_rename_locals_follows_closures_and_skips_module_names() -> None:
    source = "total = 0\n\ndef outer():\n    count = 1\n    def inner():\n        return count\n    return inner\n"
    renamed = rename_locals(source, random.Random(0))
    assert renamed.startswith("total = 0") and "count" not in renamed
    assert ast.parse(renamed) and "def inner" in renamed


def test_rename_locals_counts_characters_not_bytes() -> None:
    source = 'def f():\n    é = "ü"; value = 1\n    return value\n'
    renamed = rename_locals(source, random.Random(0))
    assert "value" not in renamed and '"ü"' in renamed
    ast.parse(renamed)
