from pathlib import Path
from typing import Any

import yaml
from conftest import write_tree
from knack.miss.coverage import contradicted_branches, coverage_losses, CoverageInputs
from knack.miss.repair import added_candidate
from knack.pipeline.prove import GuardEdit
from test_no_coverage_loss import airflow_inputs, CALLS, FIXTURES, V1, V2

# Spark Open's compliant file from the KN-97 live run that v1's dict-comprehension branch denied.
COMPLIANT_3 = (FIXTURES / "compliant_3.py").read_text()
TWO_CALLS = CALLS.replace("rule: {pattern: %s($$$)}", "rule: {any: [%s, %s]}")


def branches(rule_yaml: str) -> list[Any]:
    return yaml.safe_load(rule_yaml)["rule"]["any"]


def new_file(tmp_path: Path, name: str, after: str) -> dict[str, GuardEdit]:
    write_tree(tmp_path, {f"{name}/before.py": "", f"{name}/after.py": after})
    folder = tmp_path / name
    return {name: GuardEdit(before=folder / "before.py", after=folder / "after.py")}


def test_only_the_dict_comprehension_branch_flags_the_compliant_file(
    tmp_path: Path,
) -> None:
    dropped = contradicted_branches(V1, new_file(tmp_path, "c3", COMPLIANT_3))
    assert len(dropped) == 1
    assert dropped[0]["all"][0] == {"kind": "dictionary_comprehension"}


def test_a_false_block_repair_keeps_every_uncontradicted_v1_branch_verbatim(
    tmp_path: Path,
) -> None:
    dropped = contradicted_branches(V1, new_file(tmp_path, "c3", COMPLIANT_3))
    candidate = branches(added_candidate(V1, V2, dropped))
    kept = [b for b in branches(V1) if b not in dropped]
    assert candidate[: len(kept)] == kept and len(kept) == len(branches(V1)) - 1
    # The real v2 re-proposed the dropped branch verbatim; it stays dropped.
    assert dropped[0] in branches(V2) and dropped[0] not in candidate


def test_a_dropped_branch_whose_input_is_no_longer_denied_fails_coverage(
    tmp_path: Path,
) -> None:
    write_tree(tmp_path, {"x.py": "foo(1)\n", "y.py": "bar(1)\n"})
    old = TWO_CALLS % ("{pattern: foo($$$)}", "{pattern: bar($$$)}")
    dropped = contradicted_branches(old, new_file(tmp_path, "ok", "bar(2)\n"))
    candidate = added_candidate(old, CALLS % "baz", dropped)
    files = {"base x.py": tmp_path / "x.py", "base y.py": tmp_path / "y.py"}
    assert coverage_losses(old, candidate, CoverageInputs(files=files)) == [
        "no longer denies base y.py"
    ]


def test_with_no_must_pass_edit_the_repair_is_kn112s_add(tmp_path: Path) -> None:
    assert contradicted_branches(V1, {}) == []
    assert added_candidate(V1, V2, []) == added_candidate(V1, V2)
    assert coverage_losses(V1, added_candidate(V1, V2), airflow_inputs(tmp_path)) == []


def test_every_branch_contradicted_leaves_sparks_rule(tmp_path: Path) -> None:
    dropped = contradicted_branches(CALLS % "foo", new_file(tmp_path, "f", "foo()\n"))
    assert added_candidate(CALLS % "foo", CALLS % "bar", dropped) == CALLS % "bar"
