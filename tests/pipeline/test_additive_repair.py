from pathlib import Path
from typing import Any

import yaml
from conftest import write_tree
from knack.guard.runner import scan_file_with_rule
from knack.miss.coverage import coverage_losses
from knack.miss.repair import added_candidate
from test_no_coverage_loss import airflow_inputs, CALLS, V1, V2

# The evasion v2 was compiled for: the sort keys built with dict(...), not {...}.
DICT_EVASION = "from airflow.models import DagRun\n\nkeys = dict(state=DagRun.state, start_date=DagRun.start_date)\n"


def branches(rule_yaml: str) -> list[Any]:
    return yaml.safe_load(rule_yaml)["rule"]["any"]


def denies(tmp_path: Path, rule_yaml: str, source: str) -> bool:
    write_tree(tmp_path, {"rule.yml": rule_yaml, "evasion.py": source})
    return bool(scan_file_with_rule(tmp_path / "evasion.py", tmp_path / "rule.yml"))


def test_the_real_v2_keeps_every_v1_branch_and_adds_keyword_argument() -> None:
    added = [b for b in branches(V2) if b not in branches(V1)]
    assert len(added) == 1 and added[0]["all"][0] == {"kind": "keyword_argument"}
    assert branches(added_candidate(V1, V2)) == branches(V1) + added


def test_the_kept_pair_branch_is_the_one_v2_dropped() -> None:
    candidate = added_candidate(V1, V2)
    assert "last_run_(state|start_date)" in str(branches(candidate))
    assert "last_run_(state|start_date)" not in str(branches(V2))


def test_the_v2_candidate_loses_no_coverage(tmp_path: Path) -> None:
    candidate = added_candidate(V1, V2)
    assert coverage_losses(V1, candidate, airflow_inputs(tmp_path)) == []


def test_the_v2_candidate_still_denies_the_dict_evasion(tmp_path: Path) -> None:
    assert not denies(tmp_path / "v1", V1, DICT_EVASION)
    assert denies(tmp_path / "candidate", added_candidate(V1, V2), DICT_EVASION)


def test_a_recompile_identical_to_v1_adds_nothing() -> None:
    assert yaml.safe_load(added_candidate(V1, V1)) == yaml.safe_load(V1)


def test_the_candidate_keeps_v1s_id_message_and_severity() -> None:
    candidate = yaml.safe_load(added_candidate(V1, V2))
    assert {k: v for k, v in candidate.items() if k != "rule"} == {
        k: v for k, v in yaml.safe_load(V1).items() if k != "rule"
    }


def test_a_v1_that_is_not_a_top_level_any_is_wrapped() -> None:
    candidate = added_candidate(CALLS % "foo", CALLS % "bar")
    assert branches(candidate) == [{"pattern": "foo($$$)"}, {"pattern": "bar($$$)"}]


def test_a_branch_repeated_in_the_recompile_is_added_once() -> None:
    twice = CALLS.replace("rule: {pattern: %s($$$)}", "rule: {any: [%s, %s]}")
    new = twice % ("{pattern: bar($$$)}", "{pattern: bar($$$)}")
    assert branches(added_candidate(CALLS % "foo", new))[1:] == [
        {"pattern": "bar($$$)"}
    ]


def test_an_unreadable_recompile_adds_nothing() -> None:
    candidate = added_candidate(V1, "not: [a rule")
    assert yaml.safe_load(candidate) == yaml.safe_load(V1)
