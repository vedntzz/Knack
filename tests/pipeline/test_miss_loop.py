import json
from pathlib import Path

from conftest import (
    BASE,
    clean_tree,
    FakeAdversary,
    FakeGitHub,
    FakeSpark,
    HELDOUT,
    HELDOUT_COMPLIANT,
    HELDOUT_VIOLATIONS,
    STRUCTURAL,
    VARIANTS,
    write_tree,
)
from knack.miss.cases import CaseKind, cases_dir, EditCase, load_cases, save_case
from knack.miss.loop import (
    default_heldout,
    default_loop,
    Loop,
    outcome_lines,
    record_and_recompile,
)
from test_prove import EDIT_ADDS, MEMORIZED_ON_BASE, NARROWED, PINGS

RULE_ID = "widgets-9"
ROOT = {
    "id": "widgets-9-1",
    "title": "Read blobs one at a time",
    "decision": "Read blobs one at a time in a loop",
    "why": "gather opens every blob at once",
    "decided_by": "maria",
    "source_url": "https://github.com/acme/widgets/pull/9",
    "quote": "gather would open every blob at once",
    "status": "Inferred",
    "rejected_alternative": "asyncio.gather over every read",
}
# A gather the decision allows: no blob reads.
PING_MODULE = "import asyncio\n\nasync def ping_heldout(a, b):\n    got = await asyncio.gather(a.ping(), b.ping())\n    return got\n"
# Catches bare-return gathers only, so it misses the edit's assigned gather.
RETURNS_ONLY = """id: compiled-rule
language: python
severity: error
message: m
rule: {pattern: return await asyncio.gather($$$)}
"""
# Violations no gather pattern on an assignment catches.
BARE = "import asyncio\n\nasync def f{n}(xs):\n    return await asyncio.gather(*[x.read() for x in xs])\n"


def registry(tmp_path: Path, old_rule: str) -> Path:
    folder = tmp_path / "registry"
    write_tree(folder, {"roots/widgets-9-1.json": json.dumps(ROOT)})
    write_tree(folder, {"rules/9.yml": old_rule.replace("compiled-rule", RULE_ID)})
    entry = {"rule": "rules/9.yml", "root_ids": ["widgets-9-1"]}
    body = {"repo": "acme/widgets", "roots_dir": "roots", "rules": [entry]}
    (folder / "registry.json").write_text(json.dumps(body))
    return folder / "registry.json"


def heldout(tmp_path: Path, cross_violations: list[str] = HELDOUT_VIOLATIONS) -> Path:
    for which, violations in (
        ("same", HELDOUT_VIOLATIONS),
        ("cross", cross_violations),
    ):
        named = {f"violation_{i}.py": s for i, s in enumerate(violations, 1)}
        named |= {f"compliant_{i}.py": s for i, s in enumerate(HELDOUT_COMPLIANT, 1)}
        write_tree(tmp_path / "heldout" / "9" / which, named)
    return tmp_path / "heldout"


def loop(tmp_path: Path, old: str, compiled: str, **kw: Path) -> tuple[Loop, FakeSpark]:
    spark = FakeSpark([compiled])
    ports = Loop(
        github=FakeGitHub(clean_tree(tmp_path)),
        compiler=spark,
        writer=FakeAdversary(VARIANTS, HELDOUT),
        registry=registry(tmp_path, old),
        heldout=kw["heldout"] if "heldout" in kw else heldout(tmp_path),
        work=tmp_path / "work",
        log=lambda line: None,
    )
    return ports, spark


def edit(kind: CaseKind, adds: str) -> EditCase:
    return EditCase(
        kind=kind,
        rule_id=RULE_ID,
        file="pkg/loader.py",
        before=BASE,
        after=BASE + adds,
        source="edit test.json",
    )


def rule_text(ports: Loop) -> str:
    return (ports.registry.parent / "rules" / "9.yml").read_text()


def test_a_miss_recompiles_and_installs_a_rule_that_passes_every_gate(
    tmp_path: Path,
) -> None:
    ports, _ = loop(tmp_path, MEMORIZED_ON_BASE, STRUCTURAL)
    outcome = record_and_recompile(ports, [edit("must-fail", EDIT_ADDS)])
    assert outcome.installed and outcome.recompiled and outcome.reasons == []
    assert [g.name for g in outcome.gates] == [
        "cases",
        "proof",
        "held-out same",
        "held-out cross",
        "fresh cross-model",
    ]
    assert rule_text(ports).startswith(f"id: {RULE_ID}\n")
    assert "asyncio.gather($$$)" in rule_text(ports)


def test_the_recompile_starts_from_the_old_rule_and_its_missed_edit(
    tmp_path: Path,
) -> None:
    ports, spark = loop(tmp_path, MEMORIZED_ON_BASE, STRUCTURAL)
    record_and_recompile(ports, [edit("must-fail", EDIT_ADDS)])
    first = spark.compile_prompts()[0]
    assert "YOUR PREVIOUS RULE:" in first and "results = await" in first
    assert f"MISSED GUARD EDIT {edit('must-fail', EDIT_ADDS).name}" in first


def test_the_case_is_recorded_beside_the_registry(tmp_path: Path) -> None:
    ports, _ = loop(tmp_path, MEMORIZED_ON_BASE, STRUCTURAL)
    record_and_recompile(ports, [edit("must-fail", EDIT_ADDS)])
    assert load_cases(cases_dir(ports.registry), RULE_ID) == [
        edit("must-fail", EDIT_ADDS)
    ]


def test_recall_no_worse_than_the_old_rule_installs(tmp_path: Path) -> None:
    # Neither rule catches the bare-return set: 0 >= 0, so recall holds.
    bare = [BARE.format(n=n) for n in range(3)]
    held = heldout(tmp_path, bare)
    ports, _ = loop(tmp_path, MEMORIZED_ON_BASE, STRUCTURAL, heldout=held)
    outcome = record_and_recompile(ports, [edit("must-fail", EDIT_ADDS)])
    cross = next(g for g in outcome.gates if g.name == "held-out cross")
    assert outcome.installed and cross.passed
    assert cross.detail == "0/3 violations caught (old rule 0), 3/3 compliant allowed"


def test_recall_below_the_old_rule_is_not_installed(tmp_path: Path) -> None:
    # The old rule catches every bare return; the recompiled one catches none.
    bare = [BARE.format(n=n) for n in range(3)]
    held = heldout(tmp_path, bare)
    ports, _ = loop(tmp_path, RETURNS_ONLY, STRUCTURAL, heldout=held)
    old = rule_text(ports)
    outcome = record_and_recompile(ports, [edit("must-fail", EDIT_ADDS)])
    assert not outcome.installed and rule_text(ports) == old
    assert outcome.reasons == [
        "held-out cross: 0/3 violations caught (old rule 3), 3/3 compliant allowed"
    ]


def test_a_flagged_compliant_file_fails_whatever_the_old_rule_did(
    tmp_path: Path,
) -> None:
    # Precision stays absolute: one compliant held-out file flagged keeps the old rule.
    held = heldout(tmp_path)
    (held / "9" / "cross" / "compliant_1.py").write_text(PING_MODULE)
    ports, _ = loop(tmp_path, MEMORIZED_ON_BASE, STRUCTURAL, heldout=held)
    outcome = record_and_recompile(ports, [edit("must-fail", EDIT_ADDS)])
    assert not outcome.installed
    assert outcome.reasons == [
        "held-out cross: 2/3 violations caught (old rule 0), 2/3 compliant allowed"
    ]


def test_the_recorded_case_is_its_own_gate(tmp_path: Path) -> None:
    ports, _ = loop(tmp_path, MEMORIZED_ON_BASE, MEMORIZED_ON_BASE)
    outcome = record_and_recompile(ports, [edit("must-fail", EDIT_ADDS)])
    cases = outcome.gates[0]
    name = edit("must-fail", EDIT_ADDS).name
    assert (cases.name, cases.passed) == ("cases", False)
    assert cases.detail == f"guard edit {name} adds no new match"
    assert "guard edit" not in outcome.gates[1].detail


def test_a_missing_held_out_set_keeps_the_old_rule(tmp_path: Path) -> None:
    ports, _ = loop(tmp_path, MEMORIZED_ON_BASE, STRUCTURAL, heldout=tmp_path / "none")
    outcome = record_and_recompile(ports, [edit("must-fail", EDIT_ADDS)])
    assert not outcome.installed
    assert outcome.reasons[0].startswith("held-out same: missing ")


def test_a_false_block_recompiles_a_rule_that_allows_the_edit(tmp_path: Path) -> None:
    ports, _ = loop(tmp_path, STRUCTURAL, NARROWED)
    outcome = record_and_recompile(ports, [edit("must-pass", PINGS)])
    assert outcome.installed and "read" in rule_text(ports)


def test_earlier_cases_stay_in_every_later_recompile(tmp_path: Path) -> None:
    # STRUCTURAL denies the miss but blocks the earlier false-block case again.
    ports, _ = loop(tmp_path, MEMORIZED_ON_BASE, STRUCTURAL)
    save_case(cases_dir(ports.registry), edit("must-pass", PINGS))
    outcome = record_and_recompile(ports, [edit("must-fail", EDIT_ADDS)])
    assert not outcome.installed
    name = edit("must-pass", PINGS).name
    assert outcome.reasons == [f"cases: guard allow {name} adds a new match"]


def test_a_rule_that_already_handles_the_case_is_not_recompiled(
    tmp_path: Path,
) -> None:
    ports, spark = loop(tmp_path, STRUCTURAL, STRUCTURAL)
    old = rule_text(ports)
    outcome = record_and_recompile(ports, [edit("must-fail", EDIT_ADDS)])
    assert not outcome.recompiled and not outcome.installed
    assert spark.compile_prompts() == [] and rule_text(ports) == old


def test_a_case_is_named_by_its_file_and_content_key() -> None:
    case = edit("must-fail", EDIT_ADDS)
    assert case.name == f"pkg/loader.py [{case.key}]" and len(case.key) == 12
    assert edit("must-pass", EDIT_ADDS).key != case.key


def test_a_kept_rule_leaves_its_candidate_on_disk_for_review(tmp_path: Path) -> None:
    bare = [BARE.format(n=n) for n in range(3)]
    held = heldout(tmp_path, bare)
    ports, _ = loop(tmp_path, MEMORIZED_ON_BASE, STRUCTURAL, heldout=held)
    outcome = record_and_recompile(ports, [edit("must-fail", EDIT_ADDS)])
    assert outcome.candidate_path is not None
    assert outcome.candidate_path.read_text() == STRUCTURAL.strip() + "\n"
    assert f"candidate rule: {outcome.candidate_path}" in outcome_lines(outcome)


REPO_DATA = Path(__file__).parents[2] / "data"


def home_registry(home: Path, repo: str) -> Path:
    # Where knack init installs: ~/.knack/registries/<owner-name>/registry.json.
    path = home / ".knack" / "registries" / repo.replace("/", "-") / "registry.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"repo": repo, "roots_dir": "roots", "rules": []}))
    return path


def test_a_home_registry_reads_the_repos_data_heldout(tmp_path: Path) -> None:
    found = default_heldout(home_registry(tmp_path, "apache/airflow"))
    assert found == REPO_DATA / "heldout" / "airflow" and (found / "75025").is_dir()


def test_the_heldout_set_is_named_by_the_guarded_repo(tmp_path: Path) -> None:
    found = default_heldout(home_registry(tmp_path, "fastapi/fastapi"))
    assert found == REPO_DATA / "heldout" / "fastapi"


def test_the_shipped_registry_reads_its_own_heldout() -> None:
    found = default_heldout(REPO_DATA / "registry" / "airflow.json")
    assert found.resolve() == (REPO_DATA / "heldout" / "airflow").resolve()


def test_held_out_sets_beside_a_registry_still_win(tmp_path: Path) -> None:
    registry = home_registry(tmp_path, "apache/airflow")
    beside = registry.parent.parent / "heldout" / registry.stem
    beside.mkdir(parents=True)
    assert default_heldout(registry) == beside


def test_the_default_loop_uses_the_repos_heldout(tmp_path: Path) -> None:
    registry = home_registry(tmp_path, "apache/airflow")
    loop = default_loop(
        FakeGitHub(tmp_path), FakeSpark([]), FakeSpark([]), registry, print
    )
    assert loop.heldout == REPO_DATA / "heldout" / "airflow"
