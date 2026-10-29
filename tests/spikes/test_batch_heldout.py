from pathlib import Path
from types import ModuleType

import pytest
from conftest import SPIKES, SpikeLoader

CATCHES_GATHER = """id: compiled-rule
language: python
severity: error
message: m
rule: {pattern: asyncio.gather($$$)}
"""
CATCHES_NOTHING = """id: compiled-rule
language: python
severity: error
message: m
rule: {pattern: never_called_anywhere($$$)}
"""
GATHER = "import asyncio\nasync def f(xs):\n    return await asyncio.gather(*xs)\n"
LOOP = "async def f(xs):\n    return [await x for x in xs]\n"


@pytest.fixture
def spike(load_spike: SpikeLoader) -> ModuleType:
    return load_spike("batch_heldout")


def variant_set(tmp_path: Path, violations: list[str], compliant: list[str]) -> dict[str, dict[str, Path]]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    sides = {"variant-violation": ("violation", violations), "variant-compliant": ("compliant", compliant)}
    for prefix, sources in sides.values():
        for i, source in enumerate(sources, 1):
            (tmp_path / f"{prefix}_{i}.py").write_text(source)
    return {side: {f"{prefix}_{i}.py": tmp_path / f"{prefix}_{i}.py" for i in range(1, len(sources) + 1)}
            for side, (prefix, sources) in sides.items()}


def test_heldout_set_lives_apart_from_the_training_set(spike: ModuleType, tmp_path: Path) -> None:
    batch = spike.Batch("fastapi/fastapi", root=tmp_path)
    assert spike.heldout_dir(batch, 7) == batch.src / "7" / "variants-heldout"


def test_compiler_never_reads_the_heldout_set() -> None:
    assert "heldout" not in (SPIKES / "batch_compile.py").read_text()


def test_rule_catching_violations_and_allowing_compliant_passes(spike: ModuleType, tmp_path: Path) -> None:
    score = spike.variant_score(CATCHES_GATHER, variant_set(tmp_path, [GATHER, GATHER, LOOP], [LOOP] * 3))
    assert score == (2, 3, False) and spike.variant_pass(score)


def test_rule_catching_one_violation_fails(spike: ModuleType, tmp_path: Path) -> None:
    score = spike.variant_score(CATCHES_GATHER, variant_set(tmp_path, [GATHER, LOOP, LOOP], [LOOP] * 3))
    assert score == (1, 3, False) and not spike.variant_pass(score)


def test_rule_flagging_compliant_code_fails(spike: ModuleType, tmp_path: Path) -> None:
    score = spike.variant_score(CATCHES_GATHER, variant_set(tmp_path, [GATHER] * 3, [LOOP, GATHER, LOOP]))
    assert score == (3, 2, False) and not spike.variant_pass(score)


def test_rule_ast_grep_cannot_parse_fails(spike: ModuleType, tmp_path: Path) -> None:
    score = spike.variant_score("rule: [", variant_set(tmp_path, [GATHER] * 3, [LOOP] * 3))
    assert score[2] is True and not spike.variant_pass(score)


def test_silent_rule_allows_everything_but_fails(spike: ModuleType, tmp_path: Path) -> None:
    assert spike.variant_score(CATCHES_NOTHING, variant_set(tmp_path, [GATHER] * 3, [LOOP] * 3)) == (0, 3, False)


def test_identical_modules_counts_heldout_copies_of_training_modules(spike: ModuleType, tmp_path: Path) -> None:
    train = variant_set(tmp_path / "train", [GATHER, LOOP, "x = 1\n"], [LOOP] * 3)
    heldout = variant_set(tmp_path / "heldout", [GATHER + "\n", "y = 2\n", "z = 3\n"], ["w = 4\n"] * 3)
    assert spike.identical_modules(train, heldout) == 1
