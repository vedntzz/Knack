from pathlib import Path

from bench.pilot.proof import new_hits, prove_trees, RuleProof
from tests_pilot_support import BASE, HEAD, REJECTED, TARGET, write_tree


def trees(tmp_path: Path, head: str = HEAD) -> tuple[Path, Path, Path]:
    base = write_tree(tmp_path / "base", {TARGET: BASE})
    rejected = write_tree(tmp_path / "rejected", {TARGET: REJECTED})
    return base, rejected, write_tree(tmp_path / "head", {TARGET: head})


def test_new_hits_counts_only_matches_the_after_tree_added(
    tmp_path: Path, sleep_rule: Path
) -> None:
    base, rejected, head = trees(tmp_path)
    assert new_hits(base, rejected, [TARGET], sleep_rule) == ["time.sleep(1)"]
    assert new_hits(base, head, [TARGET], sleep_rule) == []


def test_new_hits_treats_a_missing_file_as_empty(
    tmp_path: Path, sleep_rule: Path
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    rejected = write_tree(tmp_path / "rejected", {TARGET: REJECTED})
    assert new_hits(empty, rejected, [TARGET], sleep_rule) == ["time.sleep(1)"]


def test_prove_trees_passes_base_flag_head_allow_accepted_present(
    tmp_path: Path, sleep_rule: Path, accepted_rule: Path
) -> None:
    proof = prove_trees(
        "demo-1", trees(tmp_path), [TARGET], (sleep_rule, accepted_rule)
    )
    assert proof == RuleProof(
        id="demo-1", base_flag_hits=1, head_hits=0, accepted_head_hits=1
    )
    assert proof.proven


def test_prove_trees_fails_when_the_merged_head_also_matches(
    tmp_path: Path, sleep_rule: Path, accepted_rule: Path
) -> None:
    head_with_trap = REJECTED.replace("import time", "import asyncio, time")
    paths = trees(tmp_path, head=head_with_trap)
    proof = prove_trees("demo-1", paths, [TARGET], (sleep_rule, accepted_rule))
    assert proof.head_hits == 1 and not proof.proven


def test_proof_needs_the_accepted_fix_check_to_see_the_head() -> None:
    proof = RuleProof(id="x", base_flag_hits=2, head_hits=0, accepted_head_hits=0)
    assert not proof.proven
