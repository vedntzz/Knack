import hashlib
from pathlib import Path
from typing import Any

import yaml
from knack.miss.cases import cases_dir, load_cases
from knack.miss.coverage import CoverageInputs, denied
from knack.pipeline.prove import GuardEdit

# The KN-97 live self-repair run, frozen unchanged (spikes/self_repair_live.md).
REPO = Path(__file__).parents[2]
LIVE = REPO / "mockups" / "fixtures" / "self_repair"
REGISTRY = REPO / "data" / "registry" / "airflow.json"
COMPLIANT_3 = REPO / "tests" / "fixtures" / "self_repair_75025" / "compliant_3.py"
ROUTES = "airflow-core/src/airflow/api_fastapi/core_api/routes"
HEAD_DAGS = REPO / "scripts" / "fixtures" / "75025" / "head" / ROUTES / "public/dags.py"
V1_SHA = "ecf207d0e1efce2759eb92b2beba21e9576eaf0c5d832ca4acdfca1079a4b0d5"
V2_SHA = "865e1a983ffe12941abd400da11efbe14e6a7ec97735455b61218abe464b2303"


def live_rule(version: str) -> str:
    return (LIVE / "rule" / f"{version}.yml").read_text()


def adds_a_match(version: str, before: Path, after: Path) -> bool:
    inputs = CoverageInputs(edits={"e": GuardEdit(before=before, after=after)})
    return denied(live_rule(version), inputs) == {"e"}


def new_compliant_3(tmp_path: Path) -> tuple[Path, Path]:
    (tmp_path / "before.py").write_text("")
    return tmp_path / "before.py", COMPLIANT_3


def branches(version: str) -> list[Any]:
    return yaml.safe_load(live_rule(version))["rule"]["any"]


def test_the_frozen_rules_are_the_live_v1_and_v2() -> None:
    digest = {
        v: hashlib.sha256(live_rule(v).encode()).hexdigest() for v in ("v1", "v2")
    }
    assert digest == {"v1": V1_SHA, "v2": V2_SHA}


def test_the_second_confirm_pinned_the_root_to_v2() -> None:
    root = yaml.safe_load((LIVE / "rule" / "root_after.json").read_text())
    assert root["rule_sha"] == V2_SHA and root["confirmed_by"] == "Vedant Srivastava"


def test_the_registry_keeps_compliant_3_as_a_must_pass_case_for_75025() -> None:
    cases = load_cases(cases_dir(REGISTRY), "airflow-75025")
    passes = [c.after for c in cases if c.kind == "must-pass"]
    assert passes == [COMPLIANT_3.read_text()]


def test_live_v2_allows_compliant_3_that_v1_denied(tmp_path: Path) -> None:
    edit = new_compliant_3(tmp_path)
    assert adds_a_match("v1", *edit) and not adds_a_match("v2", *edit)


def test_live_v2_denies_the_dict_evasion_that_v1_allowed() -> None:
    evasion = LIVE / "edits" / "miss.after.py"
    assert not adds_a_match("v1", HEAD_DAGS, evasion)
    assert adds_a_match("v2", HEAD_DAGS, evasion)


def test_live_v2_allows_the_corrected_edit() -> None:
    assert not adds_a_match("v2", HEAD_DAGS, LIVE / "edits" / "corrected.after.py")


def test_live_v2_dropped_only_v1s_dict_comprehension_branch() -> None:
    dropped = [b for b in branches("v1") if b not in branches("v2")]
    assert [b["all"][0] for b in dropped] == [{"kind": "dictionary_comprehension"}]
