import json
from pathlib import Path

import pytest
from conftest import SpikeLoader, SPIKES

SCRIPTS = ["batch_select", "batch_extract", "batch_compile", "batch_precision"]


def test_slug_flattens_owner_and_name(load_spike: SpikeLoader) -> None:
    assert load_spike("batch_repo").Batch("apache/airflow").slug == "apache-airflow"


def test_each_repo_writes_under_its_own_slug_folder(load_spike: SpikeLoader) -> None:
    batch = load_spike("batch_repo").Batch("fastapi/fastapi")
    assert batch.dir == SPIKES / "batch" / "fastapi-fastapi"
    assert [batch.prs.name, batch.decisions.name] == ["prs.json", "decisions.jsonl"]
    assert {batch.prs.parent, batch.decisions.parent, batch.rules.parent} == {batch.dir}
    assert batch.src == batch.dir / "src"


def test_no_repo_writes_into_the_legacy_airflow_folder(
    load_spike: SpikeLoader,
) -> None:
    # the existing Airflow outputs sit directly in spikes/batch and must stay untouched
    batch = load_spike("batch_repo").Batch("apache/airflow")
    legacy = SPIKES / "batch"
    assert legacy not in {batch.prs.parent, batch.decisions.parent, batch.rules.parent}


def test_api_and_clone_urls_name_the_repo(load_spike: SpikeLoader) -> None:
    batch = load_spike("batch_repo").Batch("fastapi/fastapi")
    assert batch.api == "https://api.github.com/repos/fastapi/fastapi"
    assert batch.clone_url == "https://github.com/fastapi/fastapi.git"


@pytest.mark.parametrize("script", SCRIPTS)
def test_repo_defaults_to_airflow(load_spike: SpikeLoader, script: str) -> None:
    assert load_spike(script).parse_args([]).repo == "apache/airflow"


@pytest.mark.parametrize("script", SCRIPTS)
def test_repo_flag_is_accepted(load_spike: SpikeLoader, script: str) -> None:
    args = load_spike(script).parse_args(["--repo", "fastapi/fastapi"])
    assert args.repo == "fastapi/fastapi"


@pytest.mark.parametrize("script", SCRIPTS)
@pytest.mark.parametrize("bad", ["fastapi", "a/b/c", "/fastapi", "fastapi/", "a b/c"])
def test_malformed_repo_is_rejected(
    load_spike: SpikeLoader, script: str, bad: str
) -> None:
    with pytest.raises(SystemExit):
        load_spike(script).parse_args(["--repo", bad])


def test_extract_extra_pr_is_airflow_only(load_spike: SpikeLoader) -> None:
    spike = load_spike("batch_extract")
    assert spike.extras(spike.Batch("apache/airflow")) == [75025]
    assert spike.extras(spike.Batch("fastapi/fastapi")) == []


def test_compile_keeps_airflow_hand_picked_targets(load_spike: SpikeLoader) -> None:
    spike = load_spike("batch_compile")
    assert spike.targets(spike.Batch("apache/airflow")) == [
        75774,
        74150,
        75271,
        75734,
        75025,
    ]


def test_compile_targets_other_repos_by_rejected_alternatives(
    load_spike: SpikeLoader, tmp_path: Path
) -> None:
    spike = load_spike("batch_compile")
    batch = spike.Batch("fastapi/fastapi", root=tmp_path)
    batch.dir.mkdir()
    rows: list[dict[str, object]] = [
        {"number": 1, "decisions": [{"rejected_alternatives": [{"quote": "q"}]}]},
        {"number": 2, "decisions": [{"rejected_alternatives": []}]},
        {"number": 3, "decisions": []},
    ]
    batch.decisions.write_text("".join(json.dumps(r) + "\n" for r in rows))
    assert spike.targets(batch) == [1]


def test_extract_resumes_from_the_repo_own_file(
    load_spike: SpikeLoader, tmp_path: Path
) -> None:
    spike = load_spike("batch_extract")
    batch = spike.Batch("fastapi/fastapi", root=tmp_path)
    batch.dir.mkdir()
    batch.decisions.write_text(json.dumps({"number": 7}) + "\n")
    assert spike.done_numbers(batch) == {7}
    assert spike.done_numbers(spike.Batch("other/repo", root=tmp_path)) == set()
