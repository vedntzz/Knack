from pathlib import Path
from types import ModuleType

import pytest
from conftest import SpikeLoader

RecordedClones = tuple[ModuleType, list[list[str]]]


@pytest.fixture
def recorded_clones(
    load_spike: SpikeLoader, monkeypatch: pytest.MonkeyPatch
) -> RecordedClones:
    # fake subprocess.run so no clone touches the network
    spike, calls = load_spike("batch_precision"), list[list[str]]()

    def record(argv: list[str], **_: object) -> None:
        calls.append(argv)

    monkeypatch.setattr(spike.subprocess, "run", record)
    return spike, calls


def test_ref_gets_its_own_clone_folder(recorded_clones: RecordedClones) -> None:
    spike, _ = recorded_clones
    airflow = spike.Batch("apache/airflow")
    assert spike.clone_dir(airflow, "v2-10-stable") == Path(
        "/tmp/apache-airflow-v2-10-stable"
    )


def test_repos_get_separate_clone_folders(recorded_clones: RecordedClones) -> None:
    spike, _ = recorded_clones
    fastapi = spike.Batch("fastapi/fastapi")
    assert spike.clone_dir(fastapi, "master") == Path("/tmp/fastapi-fastapi-master")


def test_clone_checks_out_the_requested_ref(
    recorded_clones: RecordedClones, tmp_path: Path
) -> None:
    spike, calls = recorded_clones
    airflow = spike.Batch("apache/airflow")
    spike.shallow_clone(airflow, "v2-10-stable", tmp_path / "airflow-v2-10-stable")
    assert calls[0][calls[0].index("--branch") + 1] == "v2-10-stable"
    assert calls[0][-1] == str(tmp_path / "airflow-v2-10-stable")


def test_clone_fetches_the_requested_repo(
    recorded_clones: RecordedClones, tmp_path: Path
) -> None:
    spike, calls = recorded_clones
    spike.shallow_clone(spike.Batch("fastapi/fastapi"), "master", tmp_path / "c")
    assert "https://github.com/fastapi/fastapi.git" in calls[0]


def test_ref_and_repo_parse_together(load_spike: SpikeLoader) -> None:
    args = load_spike("batch_precision").parse_args(
        ["--repo", "fastapi/fastapi", "--ref", "master"]
    )
    assert (args.repo, args.ref) == ("fastapi/fastapi", "master")


def test_rules_are_read_from_the_repo_folder(load_spike: SpikeLoader) -> None:
    spike = load_spike("batch_precision")
    assert spike.Batch("fastapi/fastapi").rules.parts[-3:] == (
        "batch",
        "fastapi-fastapi",
        "rules",
    )
