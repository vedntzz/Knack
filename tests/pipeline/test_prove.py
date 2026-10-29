from pathlib import Path

import pytest
from conftest import (
    BASE,
    clean_tree,
    COMPLIANT,
    HEAD,
    MEMORIZED,
    STRUCTURAL,
    VIOLATIONS,
    write_tree,
)
from knack.pipeline.prove import (
    failed_checks,
    feedback,
    passed,
    ProofCase,
    prove,
    side_ok,
    Sides,
    verifier_sides,
)

# flags base only through the base's local variable name `results`
MEMORIZED_ON_BASE = STRUCTURAL.replace("$R = await", "results = await")
# catches only the variant whose first gather argument is a plain .read() call
ONE_OF_THREE = STRUCTURAL.replace("gather($$$)", "gather($A.read(), $$$)")
BROKEN = "id: compiled-rule\nlanguage: python\nrule: {nonsense: 1}\n"


def side(tmp_path: Path, name: str, source: str) -> dict[str, Path]:
    return {
        "pkg/loader.py": write_tree(tmp_path / name, {"pkg/loader.py": source})
        / "pkg/loader.py"
    }


def variants(tmp_path: Path) -> Sides:
    named = {"violation": VIOLATIONS, "compliant": COMPLIANT}
    files = {f"{k}_{i}.py": s for k, ss in named.items() for i, s in enumerate(ss, 1)}
    out = write_tree(tmp_path / "variants", files)
    sides = {"variant-violation": "violation", "variant-compliant": "compliant"}
    return {s: {n: out / n for n in files if n.startswith(k)} for s, k in sides.items()}


def case(tmp_path: Path, tree: Path | None = None) -> ProofCase:
    base, head = side(tmp_path, "base", BASE), side(tmp_path, "head", HEAD)
    sides = verifier_sides(7, base, head, tmp_path / "renamed", variants(tmp_path))
    return ProofCase(
        sides=sides, changed=["pkg/loader.py"], tree=tree or clean_tree(tmp_path)
    )


def verdicts(tmp_path: Path, rule: str) -> dict[str, bool]:
    return side_ok(prove(rule, case(tmp_path)).rows)


def test_structural_rule_catching_two_of_three_violations_passes(
    tmp_path: Path,
) -> None:
    proof = prove(STRUCTURAL, case(tmp_path))
    assert passed(proof) and failed_checks(proof) == []


def test_rule_spelling_a_pr_introduced_name_fails_rename_head(tmp_path: Path) -> None:
    assert verdicts(tmp_path, MEMORIZED) == {
        "base": True,
        "head": True,
        "rename-base": True,
        "rename-head": False,
        "variant-violation": True,
        "variant-compliant": False,
    }


def test_rule_spelling_a_base_local_fails_rename_base(tmp_path: Path) -> None:
    assert verdicts(tmp_path, MEMORIZED_ON_BASE) == {
        "base": True,
        "head": True,
        "rename-base": False,
        "rename-head": True,
        "variant-violation": False,
        "variant-compliant": True,
    }


def test_catching_one_of_three_violations_fails_the_variant_check(
    tmp_path: Path,
) -> None:
    assert verdicts(tmp_path, ONE_OF_THREE)["variant-violation"] is False


def test_flagging_one_compliant_variant_fails(tmp_path: Path) -> None:
    proof_case = case(tmp_path)
    proof_case.sides["variant-compliant"]["compliant_2.py"].write_text(VIOLATIONS[0])
    assert side_ok(prove(STRUCTURAL, proof_case).rows)["variant-compliant"] is False


def test_match_on_the_default_branch_fails_the_tree_check(tmp_path: Path) -> None:
    tree = clean_tree(tmp_path)
    write_tree(tree, {"jobs/bulk.py": VIOLATIONS[0]})
    proof = prove(STRUCTURAL, case(tmp_path, tree))
    assert proof.false_positives == [
        "jobs/bulk.py:4  data = await asyncio.gather(*(b.read() for b in blobs))"
    ]
    assert not passed(proof) and failed_checks(proof) == [
        "1 false positives on the default branch"
    ]


def test_matches_inside_the_prs_own_files_are_not_false_positives(
    tmp_path: Path,
) -> None:
    tree = write_tree(tmp_path / "tree", {"pkg/loader.py": BASE})
    assert prove(STRUCTURAL, case(tmp_path, tree)).false_positives == []


def test_broken_rule_fails_every_check_with_its_error(tmp_path: Path) -> None:
    proof = prove(BROKEN, case(tmp_path))
    assert not passed(proof) and proof.tree_error
    assert all(row.error for row in proof.rows)
    assert "ast-grep" in failed_checks(proof)[0]


def test_feedback_names_failing_sides_and_shows_wrong_variants(tmp_path: Path) -> None:
    proof_case = case(tmp_path)
    text = feedback(prove(MEMORIZED, proof_case), proof_case)
    assert "rename-head must flag 0" in text
    assert COMPLIANT[1] in text and COMPLIANT[2] in text and "must allow" in text
    assert COMPLIANT[0] not in text and VIOLATIONS[0] not in text


def test_feedback_names_missed_violations(tmp_path: Path) -> None:
    proof_case = case(tmp_path)
    text = feedback(prove(STRUCTURAL, proof_case), proof_case)
    assert VIOLATIONS[1] in text and "must flag" in text
    assert VIOLATIONS[0] not in text


@pytest.mark.parametrize("name", ["rename-base", "rename-head"])
def test_renamed_sides_keep_relative_paths(tmp_path: Path, name: str) -> None:
    assert list(case(tmp_path).sides[name]) == ["pkg/loader.py"]


def old_release_case(tmp_path: Path, files: dict[str, str]) -> ProofCase:
    # The PR's case plus a checkout of release 0.115.0 holding the given files.
    old = write_tree(tmp_path / "old", files)
    return case(tmp_path).model_copy(update={"old_ref": "0.115.0", "old_tree": old})


def test_match_on_the_previous_release_fails_the_old_release_check(
    tmp_path: Path,
) -> None:
    proof = prove(STRUCTURAL, old_release_case(tmp_path, {"pkg/old.py": VIOLATIONS[0]}))
    assert failed_checks(proof) == ["1 false positives on release 0.115.0"]


def test_previous_release_matches_in_the_prs_own_files_do_not_count(
    tmp_path: Path,
) -> None:
    proof = prove(STRUCTURAL, old_release_case(tmp_path, {"pkg/loader.py": BASE}))
    assert passed(proof)


def test_feedback_shows_the_previous_release_false_positives(tmp_path: Path) -> None:
    old = old_release_case(tmp_path, {"pkg/old.py": VIOLATIONS[0]})
    text = feedback(prove(STRUCTURAL, old), old)
    expected = "release 0.115.0 must flag 0 outside this PR's files | 1 false positives"
    assert expected in text and "pkg/old.py:4" in text


def test_without_a_previous_release_there_is_no_old_release_check(
    tmp_path: Path,
) -> None:
    plain = case(tmp_path)
    assert "release" not in feedback(prove(STRUCTURAL, plain), plain)
