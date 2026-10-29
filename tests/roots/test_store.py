import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from knack.contracts.models import Root
from knack.roots.seed import EXTRACTION_MODEL, main, roots_from_extraction
from knack.roots.store import load_roots, RootStoreError

REPO = Path(__file__).parents[2]
DECISIONS = REPO / "spikes" / "batch" / "apache-airflow" / "decisions.jsonl"
CONFIRMED_75025 = REPO / "data" / "roots" / "airflow" / "75025.json"
SEEDED_PRS = ["75774", "74150", "75271", "75734"]
TITLE = "Fix MSGraphSensor timeout being reset on every re-defer"
EXPECTED_CITATION = {
    "title": TITLE,
    "decision": "Carry the start time through re-defers",
    "why": "The deadline moved forward on every poll",
    "decided_by": "stegololz",
    "source_url": "https://github.com/apache/airflow/pull/75774",
    "quote": "verbatim quote 1",
    "rejected_alternative": "alternative 1",
    "model": EXTRACTION_MODEL,
}


def root_data(root_id: str, status: str = "Confirmed") -> dict[str, Any]:
    return {
        "id": root_id,
        "title": "Outbound HTTP client",
        "decision": "Use requests, not httpx, for outbound HTTP.",
        "why": "One HTTP client keeps retries and auth handling consistent.",
        "decided_by": "Alice Chen",
        "source_url": "https://github.com/example/repo/pull/42",
        "quote": "We standardise on requests; httpx is not approved.",
        "status": status,
    }


def read_root(path: Path) -> Root:
    return Root.model_validate_json(path.read_text())


def write_json(path: Path, data: dict[str, Any]) -> Path:
    # Writes data as JSON at path and returns path.
    path.write_text(json.dumps(data))
    return path


def alternative(n: int, verbatim: bool = True) -> dict[str, Any]:
    return {
        "alternative": f"alternative {n}",
        "why_rejected": f"reason {n}",
        "quote": f"verbatim quote {n}",
        "verbatim": verbatim,
    }


def decision(alternatives: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "decision": "Carry the start time through re-defers",
        "why": "The deadline moved forward on every poll",
        "decided_by": "stegololz",
        "rejected_alternatives": alternatives,
    }


def record(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    return {"number": 75774, "decisions": decisions}


def test_load_roots_returns_roots_sorted_by_id(tmp_path: Path) -> None:
    write_json(tmp_path / "b.json", root_data("root-b"))
    write_json(tmp_path / "a.json", root_data("root-a"))
    assert [root.id for root in load_roots(tmp_path)] == ["root-a", "root-b"]


def test_invalid_root_file_raises_naming_the_file(tmp_path: Path) -> None:
    write_json(tmp_path / "broken.json", {**root_data("root-a"), "status": "Maybe"})
    with pytest.raises(RootStoreError, match="broken.json"):
        load_roots(tmp_path)


def test_unparseable_root_file_raises_naming_the_file(tmp_path: Path) -> None:
    (tmp_path / "garbage.json").write_text("{not json")
    with pytest.raises(RootStoreError, match="garbage.json"):
        load_roots(tmp_path)


def test_duplicate_ids_raise(tmp_path: Path) -> None:
    write_json(tmp_path / "one.json", root_data("root-a"))
    write_json(tmp_path / "two.json", root_data("root-a"))
    with pytest.raises(RootStoreError, match="root-a"):
        load_roots(tmp_path)


def test_extraction_maps_each_rejected_alternative_to_inferred_root() -> None:
    data = record(
        [decision([alternative(1), alternative(2)]), decision([alternative(3)])]
    )
    roots = roots_from_extraction(data, TITLE)
    assert [root.id.rpartition("-")[2] for root in roots] == ["1", "2", "3"]
    assert {(root.id.rpartition("-")[0]) for root in roots} == {"airflow-75774"}
    assert {(root.status, root.seeded) for root in roots} == {("Inferred", False)}


def test_extraction_root_cites_pr_quote_and_model() -> None:
    [root] = roots_from_extraction(record([decision([alternative(1)])]), TITLE)
    cited = root.model_dump(mode="json", include=set(EXPECTED_CITATION))
    assert cited == EXPECTED_CITATION


def test_decision_without_rejected_alternative_produces_no_root() -> None:
    assert roots_from_extraction(record([decision([])]), TITLE) == []


def test_non_verbatim_quote_is_skipped() -> None:
    data = record([decision([alternative(1, verbatim=False), alternative(2)])])
    assert [root.quote for root in roots_from_extraction(data, TITLE)] == [
        "verbatim quote 2"
    ]


def test_seed_writes_inferred_roots_and_keeps_75025_confirmed(tmp_path: Path) -> None:
    shutil.copy(CONFIRMED_75025, tmp_path / "75025.json")
    assert main([str(DECISIONS), str(tmp_path), "--prs", *SEEDED_PRS]) == 0
    labels = Counter((root.status, root.seeded) for root in load_roots(tmp_path))
    assert labels == {("Confirmed", False): 1, ("Inferred", False): 8}
    assert read_root(tmp_path / "75025.json").status == "Confirmed"


def write_batch(directory: Path, number: int, title: str | None) -> Path:
    # Writes a one-PR decisions.jsonl plus prs.json and returns the jsonl path.
    directory.mkdir()
    titles = [] if title is None else [{"number": number, "title": title}]
    (directory / "prs.json").write_text(json.dumps(titles))
    line = json.dumps({**record([decision([alternative(1)])]), "number": number})
    return write_json_line(directory / "decisions.jsonl", line)


def write_json_line(path: Path, line: str) -> Path:
    path.write_text(line + "\n")
    return path


def test_seed_refuses_to_overwrite_confirmed_root(tmp_path: Path) -> None:
    batch = write_batch(tmp_path / "batch", 75025, TITLE)
    shutil.copy(CONFIRMED_75025, tmp_path / "75025.json")
    with pytest.raises(RootStoreError, match="airflow-75025-1"):
        main([str(batch), str(tmp_path), "--prs", "75025"])
    assert read_root(tmp_path / "75025.json").status == "Confirmed"
    assert [path.name for path in tmp_path.glob("*.json")] == ["75025.json"]


def test_seed_pr_without_title_raises(tmp_path: Path) -> None:
    batch = write_batch(tmp_path / "batch", 75025, None)
    with pytest.raises(RootStoreError, match="no title for PR 75025"):
        main([str(batch), str(tmp_path / "roots"), "--prs", "75025"])


def test_seed_unknown_pr_raises(tmp_path: Path) -> None:
    with pytest.raises(RootStoreError, match="no extraction for PR 1$"):
        main([str(DECISIONS), str(tmp_path), "--prs", "1"])
