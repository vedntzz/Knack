import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from knack.pipeline import spark_open, stages
from knack.pipeline.models import PullRequest
from knack.pipeline.spark_open import (
    MODEL,
    OPEN_WEIGHTS_ENV,
    reasoning_trace,
    SparkOpenApi,
)
from tests.pipeline.conftest import (
    EXTRACTIONS,
    FakeGitHub,
    FakeSpark,
    MEMORIZED,
    REPO,
    summary,
)

# Hash of out/work written by the pre-KN-74 code on this same input.
PRE_FEATURE_HASH = "3170413ebde8e9021fa828d61425f38a0770bc76797b24c1fec251cbc01eaf87"
TITLES = {9: "Read blobs one at a time", 4: "Plain refactor", 2: "Spark babbles"}
TRACE = "PR 9 rejects gather because of the fd limit."


def open_answer(prompt: str, reasoning: str | None) -> dict[str, Any]:
    # Baseten's chat shape; open-weights models add reasoning_content beside content.
    answer = next(a for t, a in EXTRACTIONS.items() if f"Title: {t}\n" in prompt)
    message = {"role": "assistant", "content": answer}
    return {
        "choices": [
            {
                "message": message
                | ({"reasoning_content": reasoning} if reasoning else {})
            }
        ]
    }


def fake_baseten(monkeypatch: pytest.MonkeyPatch, reasoning: str | None) -> None:
    def fake(url: str, headers: dict[str, str], body: Any, timeout: float) -> Any:
        return open_answer(body["messages"][0]["content"], reasoning)

    monkeypatch.setattr(spark_open, "request_json", fake)


def pull(number: int) -> PullRequest:
    fields = summary(number, TITLES[number]).model_dump()
    return PullRequest(**fields, base_sha="b", head_sha="h", python_files=[])


def read_both(tmp_path: Path) -> Path:
    # Spark and Spark Open read three PRs; returns the work dir the readings land in.
    run = stages.Run(
        FakeGitHub(tmp_path),
        FakeSpark([MEMORIZED]),
        REPO,
        tmp_path / "out",
        print,
        second=SparkOpenApi("key"),
    )
    stages.read_and_save(run, [pull(number) for number in TITLES])
    return tmp_path / "out" / "work"


def tree_hash(work: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in work.rglob("*") if p.is_file()):
        digest.update(str(path.relative_to(work)).encode() + path.read_bytes())
    return digest.hexdigest()


def test_flag_off_writes_no_trace_and_the_pre_feature_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(OPEN_WEIGHTS_ENV, raising=False)
    fake_baseten(monkeypatch, TRACE)
    work = read_both(tmp_path)
    assert list(work.rglob("*.trace.json")) == []
    assert tree_hash(work) == PRE_FEATURE_HASH


def test_flag_on_saves_the_trace_beside_each_saved_reading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(OPEN_WEIGHTS_ENV, "1")
    fake_baseten(monkeypatch, TRACE)
    work = read_both(tmp_path)
    assert sorted(str(p.relative_to(work)) for p in work.rglob("*.trace.json")) == [
        "4/readings.trace.json",
        "9/readings.trace.json",
    ]
    assert json.loads((work / "9" / "readings.trace.json").read_text()) == {
        "model": MODEL,
        "reasoning": TRACE,
    }


def test_flag_on_leaves_the_readings_bytes_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(OPEN_WEIGHTS_ENV, "1")
    fake_baseten(monkeypatch, TRACE)
    work = read_both(tmp_path)
    for trace in work.rglob("*.trace.json"):
        trace.unlink()
    assert tree_hash(work) == PRE_FEATURE_HASH


def test_flag_on_without_reasoning_in_the_response_writes_no_trace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(OPEN_WEIGHTS_ENV, "1")
    fake_baseten(monkeypatch, None)
    assert list(read_both(tmp_path).rglob("*.trace.json")) == []


@pytest.mark.parametrize("value", ["", "0", "true", "yes"])
def test_only_exactly_one_turns_the_flag_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv(OPEN_WEIGHTS_ENV, value)
    fake_baseten(monkeypatch, TRACE)
    assert list(read_both(tmp_path).rglob("*.trace.json")) == []


@pytest.mark.parametrize("field", ["reasoning_content", "reasoning"])
def test_reasoning_trace_reads_either_field_name(field: str) -> None:
    response = {"choices": [{"message": {"content": "x", field: TRACE}}]}
    assert reasoning_trace(response) == TRACE


def test_reasoning_trace_is_none_when_absent() -> None:
    assert reasoning_trace({"choices": [{"message": {"content": "x"}}]}) is None
    assert reasoning_trace({}) is None
