from pathlib import Path

from conftest import HELDOUT_COMPLIANT, HELDOUT_VIOLATIONS, STRUCTURAL, write_tree
from knack.pipeline.heldout import (
    HeldOut,
    holds_install_bar,
    install_failure,
    not_run,
    score_heldout,
)
from knack.pipeline.progress import heldout_line


def heldout_sides(tmp_path: Path) -> dict[str, dict[str, Path]]:
    files = {f"violation_{i}.py": s for i, s in enumerate(HELDOUT_VIOLATIONS, 1)}
    files |= {f"compliant_{i}.py": s for i, s in enumerate(HELDOUT_COMPLIANT, 1)}
    write_tree(tmp_path, files)
    named = {
        kind: sorted(tmp_path.glob(f"{kind}_*.py"))
        for kind in ("violation", "compliant")
    }
    return {
        "variant-violation": {p.name: p for p in named["violation"]},
        "variant-compliant": {p.name: p for p in named["compliant"]},
    }


def test_heldout_counts_caught_violations_and_allowed_compliant(
    tmp_path: Path,
) -> None:
    held = score_heldout(STRUCTURAL, heldout_sides(tmp_path), "spark-open-x")
    assert (held.author, held.caught, held.violations) == ("spark-open-x", 2, 3)
    assert (held.allowed, held.compliant, held.error) == (3, 3, None)
    assert held.passed


def test_heldout_uses_the_same_bar_as_the_training_variants() -> None:
    assert not HeldOut(
        author="m", caught=1, violations=3, allowed=3, compliant=3
    ).passed
    assert not HeldOut(
        author="m", caught=3, violations=3, allowed=2, compliant=3
    ).passed
    assert HeldOut(author="m", caught=2, violations=3, allowed=3, compliant=3).passed


def test_a_heldout_that_could_not_run_is_never_a_pass_or_a_zero() -> None:
    held = not_run("m", RuntimeError("boom"))
    assert not held.passed and held.error == "RuntimeError: boom"
    assert heldout_line(9, held) == "  #9 held-out: not run (RuntimeError: boom)"


def test_an_unparseable_rule_is_not_run(tmp_path: Path) -> None:
    held = score_heldout("rule: {pattern: [", heldout_sides(tmp_path), "m")
    assert held.error is not None and not held.passed


def test_the_install_bar_allows_every_compliant_file_on_a_set_that_ran() -> None:
    clean = HeldOut(author="m", caught=0, violations=3, allowed=3, compliant=3)
    assert install_failure(clean) is None and holds_install_bar(clean)
    flagged = clean.model_copy(update={"allowed": 2})
    assert install_failure(flagged) == (
        "held-out: 2/3 compliant allowed "
        "(every held-out compliant file must be allowed)"
    )


def test_the_install_bar_never_passes_an_empty_or_unrun_set() -> None:
    empty = HeldOut(author="m", caught=2, violations=3)
    assert install_failure(empty) == "held-out: empty set (3 violations, 0 compliant)"
    broken = not_run("m", RuntimeError("boom"))
    assert install_failure(broken) == "held-out: not run (RuntimeError: boom)"


def test_the_miss_loop_adds_a_recall_floor_to_the_same_bar() -> None:
    held = HeldOut(author="m", caught=1, violations=3, allowed=3, compliant=3)
    assert holds_install_bar(held, floor=1) and not holds_install_bar(held, floor=2)
