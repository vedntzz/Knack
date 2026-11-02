from pathlib import Path

from conftest import write_tree
from knack.miss.coverage import coverage_inputs, coverage_losses, CoverageInputs
from knack.pipeline.prove import GuardEdit, ProofCase

# The real v1 and v2 of airflow-75025 from the self-repair run that lost a form.
FIXTURES = Path(__file__).parents[1] / "fixtures" / "self_repair_75025"
HELDOUT = Path(__file__).parents[2] / "data" / "heldout" / "airflow" / "75025"
V1, V2 = (FIXTURES / "v1.yml").read_text(), (FIXTURES / "v2.yml").read_text()
V1_PLUS_BRANCH = (FIXTURES / "v1_plus_branch.yml").read_text()
CALLS = (
    "id: r\nlanguage: python\nseverity: error\nmessage: m\nrule: {pattern: %s($$$)}\n"
)
# The same calls, matched by a rewritten pattern.
ONE_ARG = CALLS.replace("%s($$$)", "foo($A)")


def airflow_inputs(tmp_path: Path) -> CoverageInputs:
    case = ProofCase(sides={}, changed=[], tree=tmp_path)
    return coverage_inputs(case, HELDOUT)


def test_the_real_v2_fails_because_it_dropped_a_branch_no_input_exercises(
    tmp_path: Path,
) -> None:
    losses = coverage_losses(V1, V2, airflow_inputs(tmp_path))
    assert len(losses) == 1 and losses[0].startswith("dropped a v1 branch no input")
    assert "pair" in losses[0] and "last_run_(state|start_date)" in losses[0]


def test_a_candidate_that_keeps_v1_and_adds_a_branch_passes(tmp_path: Path) -> None:
    assert coverage_losses(V1, V1_PLUS_BRANCH, airflow_inputs(tmp_path)) == []


def test_v1_against_itself_loses_nothing(tmp_path: Path) -> None:
    assert coverage_losses(V1, V1, airflow_inputs(tmp_path)) == []


def test_the_inputs_are_every_file_and_edit_v1_must_deny(tmp_path: Path) -> None:
    write_tree(tmp_path, {"b/x.py": "", "v/violation_1.py": "", "h/c.py": ""})
    edit = GuardEdit(before=tmp_path / "h/c.py", after=tmp_path / "h/c.py")
    sides = {"base": {"x.py": tmp_path / "b/x.py"}, "head": {"y.py": tmp_path / "y"}}
    sides |= {"variant-violation": {"violation_1.py": tmp_path / "v/violation_1.py"}}
    case = ProofCase(sides=sides, changed=[], tree=tmp_path, guard_edits={"e": edit})
    inputs = coverage_inputs(case, HELDOUT)
    assert sorted(inputs.files)[:2] == ["base x.py", "held-out cross violation_1.py"]
    assert "variant-violation violation_1.py" in inputs.files and len(inputs.files) == 8
    assert inputs.edits == {"guard edit e": edit}


def test_an_input_v1_denies_and_the_candidate_does_not_is_named(
    tmp_path: Path,
) -> None:
    write_tree(tmp_path, {"x.py": "foo(1)\n", "y.py": "bar(1)\n"})
    files = {"base x.py": tmp_path / "x.py", "base y.py": tmp_path / "y.py"}
    losses = coverage_losses(CALLS % "foo", CALLS % "bar", CoverageInputs(files=files))
    assert losses == ["no longer denies base x.py"]


def test_a_must_fail_edit_v1_denies_must_stay_denied(tmp_path: Path) -> None:
    write_tree(tmp_path, {"before.py": "foo(1)\n", "after.py": "foo(1)\nfoo(2)\n"})
    edit = GuardEdit(before=tmp_path / "before.py", after=tmp_path / "after.py")
    inputs = CoverageInputs(edits={"guard edit e": edit})
    assert coverage_losses(CALLS % "foo", CALLS % "bar", inputs) == [
        "no longer denies guard edit e"
    ]


def test_a_rewritten_branch_that_inputs_exercise_passes_if_inputs_stay_denied(
    tmp_path: Path,
) -> None:
    write_tree(tmp_path, {"x.py": "foo(1)\n"})
    inputs = CoverageInputs(files={"base x.py": tmp_path / "x.py"})
    assert coverage_losses(CALLS % "foo", ONE_ARG, inputs) == []


def test_a_candidate_ast_grep_rejects_loses_every_input(tmp_path: Path) -> None:
    write_tree(tmp_path, {"x.py": "foo(1)\n"})
    inputs = CoverageInputs(files={"base x.py": tmp_path / "x.py"})
    broken = "id: r\nlanguage: python\nrule: {nope: 1}\n"
    assert "no longer denies base x.py" in coverage_losses(
        CALLS % "foo", broken, inputs
    )
