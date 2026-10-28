import json
import subprocess
import sys
from pathlib import Path
from textwrap import dedent
from typing import Any

from knack.contracts.models import Leaf, Root, WalkResponse
from knack.index.build import build_index, Index
from knack.roots.store import load_roots
from knack.walk.registry import load_registry, RegistryEntry
from knack.walk.walk import walk

REPO = Path(__file__).parents[2]
FIXTURES = REPO / "tests" / "guard" / "fixtures"
REGISTRY = REPO / "data" / "registry" / "airflow.json"
ROOTS = REPO / "data" / "roots" / "airflow"
VIOLATING_GET_DAGS = ("violating.py", "get_dags")
KNACK = Path(sys.executable).parent / "knack"
TICKET_75025 = (
    "Dag list: let get_dags sort by state and start_date again by aliasing them "
    "onto DagRun.state and DagRun.start_date."
)
FORBIDDEN_RULE = "id: no-forbidden\nlanguage: python\nseverity: error\nrule:\n  pattern: forbidden()\n"
SOURCES = {
    "a.py": "def helper():\n    forbidden()\n\ndef run():\n    helper()\n\ndef other():\n    pass\n",
    "b.py": "def caller():\n    run()\n",
    "x.py": "def dup():\n    pass\n",
    "y.py": "def dup():\n    pass\n",
    "z.py": "def user():\n    dup()\n",
}


def make_repo(root: Path) -> Index:
    # Writes SOURCES under root and indexes them.
    root.mkdir()
    for name, source in SOURCES.items():
        (root / name).write_text(dedent(source))
    return build_index(root)


def make_root(root_id: str, status: str, alternative: str | None) -> Root:
    return Root.model_validate(
        {
            "id": root_id,
            "title": f"title {root_id}",
            "decision": f"decision {root_id}",
            "why": f"why {root_id}",
            "decided_by": f"owner {root_id}",
            "source_url": "https://github.com/example/repo/pull/42",
            "quote": f"quote {root_id}",
            "status": status,
            "rejected_alternative": alternative,
        }
    )


def forbidden_entry(directory: Path, root_ids: list[str]) -> RegistryEntry:
    # Writes a rule matching forbidden() and binds it to root_ids.
    rule = directory / "no-forbidden.yml"
    rule.write_text(FORBIDDEN_RULE)
    return RegistryEntry(rule=rule, root_ids=root_ids)


def leaves_by_name(response: WalkResponse) -> dict[str, Leaf]:
    return {leaf.function: leaf for leaf in response.leaves}


def walk_repo(tmp_path: Path, ticket: str, roots: list[Root]) -> WalkResponse:
    # Walks the SOURCES repo with the forbidden() rule bound to every given root.
    entry = forbidden_entry(tmp_path, [root.id for root in roots])
    return walk(ticket, make_repo(tmp_path / "repo"), [entry], roots)


def test_ticket_naming_a_file_path_seeds_that_files_functions(tmp_path: Path) -> None:
    names = set(leaves_by_name(walk_repo(tmp_path, "Clean up a.py please", [])))
    assert {"helper", "run", "other"} <= names


def test_ticket_naming_a_function_seeds_it(tmp_path: Path) -> None:
    response = walk_repo(tmp_path, "Make other() faster.", [])
    assert set(leaves_by_name(response)) == {"other"}


def test_seeds_expand_one_hop_along_resolved_edges_both_ways(tmp_path: Path) -> None:
    response = walk_repo(tmp_path, "Refactor run", [])
    assert set(leaves_by_name(response)) == {"run", "helper", "caller"}


def test_unresolved_edges_are_not_followed(tmp_path: Path) -> None:
    response = walk_repo(tmp_path, "Refactor user", [])
    assert set(leaves_by_name(response)) == {"user"}


def test_match_in_span_takes_confirmed_root_as_high(tmp_path: Path) -> None:
    root = make_root("r-1", "Confirmed", "use the other thing")
    leaf = leaves_by_name(walk_repo(tmp_path, "Refactor helper", [root]))["helper"]
    assert (leaf.risk, leaf.status, leaf.root_ids) == ("high", "Confirmed", ["r-1"])
    assert (leaf.why, leaf.decided_by) == ("why r-1", "owner r-1")


def test_inferred_root_is_medium(tmp_path: Path) -> None:
    root = make_root("r-1", "Inferred", "use the other thing")
    leaf = leaves_by_name(walk_repo(tmp_path, "Refactor helper", [root]))["helper"]
    assert (leaf.risk, leaf.status) == ("medium", "Inferred")


def test_confirmed_root_without_rejected_alternative_is_medium(tmp_path: Path) -> None:
    root = make_root("r-1", "Confirmed", None)
    leaf = leaves_by_name(walk_repo(tmp_path, "Refactor helper", [root]))["helper"]
    assert (leaf.risk, leaf.status) == ("medium", "Confirmed")


def test_strongest_root_is_confirmed_first_then_lowest_id(tmp_path: Path) -> None:
    statuses = {"r-1": "Inferred", "r-3": "Confirmed", "r-2": "Confirmed"}
    roots = [make_root(root_id, status, "x") for root_id, status in statuses.items()]
    leaf = leaves_by_name(walk_repo(tmp_path, "Refactor helper", roots))["helper"]
    assert (leaf.status, leaf.why) == ("Confirmed", "why r-2")
    assert leaf.root_ids == ["r-1", "r-2", "r-3"]


def test_function_without_root_is_low_unknown_without_why(tmp_path: Path) -> None:
    root = make_root("r-1", "Confirmed", "x")
    leaf = leaves_by_name(walk_repo(tmp_path, "Refactor run", [root]))["run"]
    assert (leaf.risk, leaf.status, leaf.root_ids) == ("low", "Unknown", [])
    assert (leaf.why, leaf.decided_by) == (None, None)


def test_result_validates_as_walk_response_citing_only_matched_roots(
    tmp_path: Path,
) -> None:
    roots = [make_root("r-1", "Confirmed", "x"), make_root("r-9", "Inferred", "x")]
    entry, index = forbidden_entry(tmp_path, ["r-1"]), make_repo(tmp_path / "repo")
    response = walk("Refactor run", index, [entry], roots)
    assert WalkResponse.model_validate(response.model_dump()) == response
    assert response.leaves[0].risk == "high"
    assert [root.id for root in response.roots] == ["r-1"]


def test_75025_ticket_marks_get_dags_high_and_confirmed() -> None:
    registry = [e for e in load_registry(REGISTRY) if e.rule.stem == "75025"]
    response = walk(TICKET_75025, build_index(FIXTURES), registry, load_roots(ROOTS))
    [leaf] = [x for x in response.leaves if (x.file, x.function) == VIOLATING_GET_DAGS]
    assert (leaf.risk, leaf.status) == ("high", "Confirmed")
    assert leaf.root_ids == ["airflow-75025-1"]


def test_registry_rules_exist_with_airflow_ids_and_known_roots() -> None:
    known = {root.id for root in load_roots(ROOTS)}
    for entry in load_registry(REGISTRY):
        assert entry.rule.read_text().startswith(f"id: airflow-{entry.rule.stem}\n")
        assert entry.root_ids and set(entry.root_ids) <= known


def test_cli_walk_json_parses_as_walk_response() -> None:
    args = ["walk", TICKET_75025, "--repo", str(FIXTURES), "--registry", str(REGISTRY)]
    done = run_knack([*args, "--roots", str(ROOTS), "--json"])
    response = WalkResponse.model_validate(json.loads(done.stdout))
    assert (done.returncode, response.leaves[0].risk) == (0, "high")


def test_cli_walk_text_lists_risk_function_and_citation() -> None:
    args = ["walk", TICKET_75025, "--repo", str(FIXTURES), "--registry", str(REGISTRY)]
    lines = run_knack([*args, "--roots", str(ROOTS)]).stdout.splitlines()
    [line] = [line for line in lines if "violating.py" in line and "get_dags" in line]
    assert line.split()[0] == "high"
    assert "Confirmed" in line and "airflow-75025-1" in line


def run_knack(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(KNACK), *args], capture_output=True, text=True)


def registry_json(entries: list[dict[str, Any]]) -> str:
    return json.dumps(entries)


def test_load_registry_resolves_rules_relative_to_registry_file(tmp_path: Path) -> None:
    path = tmp_path / "registry" / "team.json"
    path.parent.mkdir()
    path.write_text(registry_json([{"rule": "../rules/r.yml", "root_ids": ["r-1"]}]))
    [entry] = load_registry(path)
    assert entry.rule.resolve() == (tmp_path / "rules" / "r.yml").resolve()
    assert entry.root_ids == ["r-1"]
