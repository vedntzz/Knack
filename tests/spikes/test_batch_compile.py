import ast
import random
from pathlib import Path
from types import ModuleType

import pytest
from conftest import SpikeLoader

BASE = """import asyncio


async def load(items):
    results = await asyncio.gather(*[i.read() for i in items])
    return results
"""
HEAD = """async def load(items):
    results = []
    for item in items:
        results.append(await item.read())
    return results
"""
# flags base; allows head only because head spells the PR's new name `append`
MEMORIZED_ON_HEAD = """id: compiled-rule
language: python
severity: error
message: m
rule:
  kind: function_definition
  not: {has: {regex: append, stopBy: end}}
"""
# flags base only through the base's local variable name `results`
MEMORIZED_ON_BASE = """id: compiled-rule
language: python
severity: error
message: m
rule: {pattern: results = await asyncio.gather($$$)}
"""
STRUCTURAL = """id: compiled-rule
language: python
severity: error
message: m
rule: {pattern: $R = await asyncio.gather($$$)}
"""
# catches only the variant whose first gather argument is a plain .read() call
ONE_OF_THREE = """id: compiled-rule
language: python
severity: error
message: m
rule: {pattern: $R = await asyncio.gather($A.read(), $$$)}
"""
# fresh code with its own names; STRUCTURAL catches violations 1 and 3 but not the bare return in 2
VIOLATIONS = [
    "import asyncio\n\nasync def fetch_all(blobs):\n    data = await asyncio.gather(*(b.read() for b in blobs))\n    return data\n",
    "import asyncio\n\nasync def grab(files):\n    return await asyncio.gather(*[f.read() for f in files])\n",
    "import asyncio\n\nasync def pull(srcs):\n    chunks = await asyncio.gather(srcs[0].read(), srcs[1].read())\n    return chunks\n",
]
COMPLIANT = [
    "async def fetch_all(blobs):\n    data = []\n    for b in blobs:\n        data.append(await b.read())\n    return data\n",
    "async def grab(files):\n    return [await f.read() for f in files]\n",
    "async def pull(srcs):\n    first = await srcs[0].read()\n    second = await srcs[1].read()\n    return first, second\n",
]


@pytest.fixture
def spike(load_spike: SpikeLoader) -> ModuleType:
    return load_spike("batch_compile")


def write_side(tmp_path: Path, side: str, source: str) -> dict[str, Path]:
    path = tmp_path / side / "pkg" / "loader.py"
    path.parent.mkdir(parents=True)
    path.write_text(source)
    return {"pkg/loader.py": path}


def write_variants(tmp_path: Path) -> dict[str, dict[str, Path]]:
    out = tmp_path / "variants"
    out.mkdir()
    named = {
        "variant-violation": ("violation", VIOLATIONS),
        "variant-compliant": ("compliant", COMPLIANT),
    }
    for prefix, sources in named.values():
        for i, source in enumerate(sources, 1):
            (out / f"{prefix}_{i}.py").write_text(source)
    return {
        side: {f"{prefix}_{i}.py": out / f"{prefix}_{i}.py" for i in (1, 2, 3)}
        for side, (prefix, _) in named.items()
    }


def sides_for(spike: ModuleType, tmp_path: Path) -> dict[str, dict[str, Path]]:
    base, head = write_side(tmp_path, "base", BASE), write_side(tmp_path, "head", HEAD)
    return spike.verifier_sides(
        7, base, head, tmp_path / "renamed", write_variants(tmp_path)
    )


def verdicts(spike: ModuleType, tmp_path: Path, rule: str) -> dict[str, bool]:
    return spike.side_ok(spike.evaluate(rule, sides_for(spike, tmp_path)))


def test_introduced_identifiers_are_head_names_missing_from_base(
    spike: ModuleType,
) -> None:
    introduced = spike.introduced_identifiers([BASE], [HEAD + "print(len(items))\n"])
    assert introduced == {"item", "append"}


def test_rename_names_rewrites_every_occurrence_and_nothing_else(
    spike: ModuleType,
) -> None:
    renamed = spike.rename_names(HEAD, {"item": "zz1", "append": "zz2"})
    assert (
        "item " not in renamed and "item." not in renamed and ".append" not in renamed
    )
    assert "for zz1 in items" in renamed and "results.zz2(await zz1.read())" in renamed
    ast.parse(renamed)


def test_rename_names_reaches_comments_strings_and_docstrings_by_whole_word(
    spike: ModuleType,
) -> None:
    # regex rules read text, so a name left in a docstring or test id still memorizes the PR
    source = 'def f():\n    """see :meth:`aget_conn`"""\n    # aget_conn here\n    x = "aget_conn"\n    return aget_connection\n'
    renamed = spike.rename_names(source, {"aget_conn": "zz1"})
    assert renamed.count("zz1") == 3 and "aget_connection" in renamed


def test_rename_names_leaves_string_prefixes_alone(spike: ModuleType) -> None:
    source = 'with open(p) as f:\n    print(f"{p}", rb"x", f)\n'
    renamed = spike.rename_names(source, {"f": "zz1", "rb": "zz2"})
    assert renamed == 'with open(p) as zz1:\n    print(f"{p}", rb"x", zz1)\n'


def test_rename_locals_keeps_params_module_names_and_attributes(
    spike: ModuleType,
) -> None:
    renamed = spike.rename_locals(BASE, random.Random(0))
    assert "results" not in renamed
    assert "async def load(items)" in renamed and "asyncio.gather" in renamed
    assert "i.read() for i in items" not in renamed
    ast.parse(renamed)


def test_rename_locals_follows_closures_and_leaves_module_scope(
    spike: ModuleType,
) -> None:
    source = "total = 0\n\ndef outer():\n    count = 1\n    def inner():\n        return count\n    return inner\n"
    renamed = spike.rename_locals(source, random.Random(0))
    assert renamed.startswith("total = 0") and "count" not in renamed
    assert ast.parse(renamed) and "def inner" in renamed


def test_rule_spelling_a_pr_introduced_name_fails_rename_head(
    spike: ModuleType, tmp_path: Path
) -> None:
    assert verdicts(spike, tmp_path, MEMORIZED_ON_HEAD) == {
        "base": True,
        "head": True,
        "rename-base": True,
        "rename-head": False,
        "variant-violation": True,
        "variant-compliant": False,
    }


def test_rule_spelling_a_base_local_fails_rename_base(
    spike: ModuleType, tmp_path: Path
) -> None:
    assert verdicts(spike, tmp_path, MEMORIZED_ON_BASE) == {
        "base": True,
        "head": True,
        "rename-base": False,
        "rename-head": True,
        "variant-violation": False,
        "variant-compliant": True,
    }


def test_structural_rule_catching_two_of_three_violations_passes(
    spike: ModuleType, tmp_path: Path
) -> None:
    assert spike.passes(
        spike.evaluate(STRUCTURAL, sides_for(spike, tmp_path)), [], None
    )


def test_catching_one_of_three_violations_fails_the_variant_check(
    spike: ModuleType, tmp_path: Path
) -> None:
    assert verdicts(spike, tmp_path, ONE_OF_THREE)["variant-violation"] is False


def test_flagging_one_compliant_variant_fails_the_variant_check(
    spike: ModuleType, tmp_path: Path
) -> None:
    sides = sides_for(spike, tmp_path)
    sides["variant-compliant"]["compliant_2.py"].write_text(VIOLATIONS[0])
    assert (
        spike.side_ok(spike.evaluate(STRUCTURAL, sides))["variant-compliant"] is False
    )


def test_rename_failure_blocks_the_rule(spike: ModuleType, tmp_path: Path) -> None:
    rows = spike.evaluate(MEMORIZED_ON_HEAD, sides_for(spike, tmp_path))
    assert not spike.passes(rows, [], None)
    assert "rename-head must flag 0" in spike.report_rows(rows)


def test_feedback_shows_missed_violations_and_flagged_compliant_code(
    spike: ModuleType, tmp_path: Path
) -> None:
    sides = sides_for(spike, tmp_path)
    feedback = spike.variant_feedback(spike.evaluate(MEMORIZED_ON_HEAD, sides), sides)
    assert COMPLIANT[1] in feedback and COMPLIANT[2] in feedback
    assert COMPLIANT[0] not in feedback and VIOLATIONS[0] not in feedback
    assert "must allow" in feedback


def test_feedback_names_missed_violations(spike: ModuleType, tmp_path: Path) -> None:
    sides = sides_for(spike, tmp_path)
    feedback = spike.variant_feedback(spike.evaluate(STRUCTURAL, sides), sides)
    assert VIOLATIONS[1] in feedback and "must flag" in feedback
    assert VIOLATIONS[0] not in feedback


def test_prompt_forbids_matching_pr_introduced_identifiers(spike: ModuleType) -> None:
    assert (
        "Do not match identifiers introduced by this PR; "
        "match the structure of the violation."
    ) in spike.PROMPT


def test_previous_rule_is_kept_as_v2_and_v1_is_untouched(
    spike: ModuleType, tmp_path: Path
) -> None:
    batch = spike.Batch("apache/airflow", root=tmp_path)
    batch.rules.mkdir(parents=True)
    (batch.rules / "1.yml").write_text("v2 rule")
    (batch.rules / "1.v1.yml").write_text("v1 rule")
    spike.preserve_as(batch, 1, "v2")
    assert (batch.rules / "1.v2.yml").read_text() == "v2 rule"
    assert (batch.rules / "1.v1.yml").read_text() == "v1 rule"
    assert not (batch.rules / "1.yml").exists()


def test_rerun_never_overwrites_an_existing_v2(
    spike: ModuleType, tmp_path: Path
) -> None:
    batch = spike.Batch("apache/airflow", root=tmp_path)
    batch.rules.mkdir(parents=True)
    (batch.rules / "1.v2.yml").write_text("v2 rule")
    (batch.rules / "1.yml").write_text("v3 rule")
    spike.preserve_as(batch, 1, "v2")
    assert (batch.rules / "1.v2.yml").read_text() == "v2 rule"


def test_v3_rule_is_kept_as_v3_beside_v2(spike: ModuleType, tmp_path: Path) -> None:
    batch = spike.Batch("apache/airflow", root=tmp_path)
    batch.rules.mkdir(parents=True)
    (batch.rules / "1.v2.yml").write_text("v2 rule")
    (batch.rules / "1.yml").write_text("v3 rule")
    spike.preserve_as(batch, 1, "v3")
    assert (batch.rules / "1.v3.yml").read_text() == "v3 rule"
    assert (batch.rules / "1.v2.yml").read_text() == "v2 rule"
