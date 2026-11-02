from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from conftest import clean_tree, FakeGitHub, FakeSpark, REPO, STRUCTURAL, SUMMARIES
from knack.contracts.models import FoundBy, ModelCall, NOT_RECORDED, Root
from knack.pipeline import spark, spark_open
from knack.pipeline.calls import reported_call
from knack.pipeline.extract import extract_pr
from knack.pipeline.init import run_init
from knack.pipeline.merged import run_merged
from knack.pipeline.models import PullRequest
from knack.pipeline.spark import SparkApi
from knack.pipeline.spark_open import SparkOpenApi
from knack.roots.store import load_roots
from knack.walk.registry import load_registry, Registry
from test_corroborate import OTHER, reading, SAME_TEXT

TITLE = "Read blobs one at a time"
NOBODY = ModelCall(model=NOT_RECORDED, host=NOT_RECORDED, trace_id=NOT_RECORDED)


class ReportingSpark(FakeSpark):
    # Reports each response like a live client: the model it named, host, response id.
    host = "api.meta.ai"
    reports = "muse-spark-1.3"

    def __init__(self) -> None:
        super().__init__([STRUCTURAL])
        self.last_model: str | None = None
        self.last_trace_id: str | None = None

    def ask(self, prompt: str) -> str:
        answer = super().ask(prompt)
        self.last_model, self.last_trace_id = self.reports, f"resp_{len(self.prompts)}"
        return answer

    def trace_of(self, title: str) -> str:
        # The response id of the call that read this PR's thread.
        asked = [i for i, p in enumerate(self.prompts, 1) if f"Title: {title}\n" in p]
        return f"resp_{asked[0]}"


class ReportingOpen(ReportingSpark):
    host = "inference.baseten.co"
    reports = "meta-models/muse-spark-open-1026"

    def __init__(self, readings: dict[str, str]) -> None:
        super().__init__()
        self.readings = readings

    def ask(self, prompt: str) -> str:
        self.prompts.append(prompt)
        self.last_model, self.last_trace_id = self.reports, f"open_{len(self.prompts)}"
        return next(a for t, a in self.readings.items() if f"Title: {t}\n" in prompt)

    def trace_of(self, title: str) -> str:
        return super().trace_of(title).replace("resp_", "open_")


class FailingOpen(ReportingOpen):
    # Spark Open never answers, so it never read any PR.
    def ask(self, prompt: str) -> str:
        raise RuntimeError("baseten down")


def found(client: ReportingSpark, role: str) -> FoundBy:
    call = {"model": client.reports, "host": client.host}
    return FoundBy.model_validate(
        call | {"trace_id": client.trace_of(TITLE)} | {"role": role}
    )


def init_roots(
    tmp_path: Path, first: FakeSpark, second: FakeSpark | None
) -> list[Root]:
    github = FakeGitHub(clean_tree(tmp_path))
    path = run_init(
        REPO, 50, tmp_path / "out", github, first, lambda _: None, second=second
    )
    return load_roots(load_registry(path).roots_dir)


def answering(*answers: dict[str, Any]) -> Callable[..., dict[str, Any]]:
    # Stands in for request_json: each call returns the next answer.
    left = iter(answers)

    def request_json(*_: object) -> dict[str, Any]:
        return next(left)

    return request_json


def models_by_status(roots: list[Root]) -> list[tuple[str, list[FoundBy | str]]]:
    return [(root.status, root.models) for root in roots]


def test_live_spark_reports_the_model_host_and_id_its_response_gave(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    message = {"type": "message", "content": [{"text": "hi"}]}
    answer = {"id": "resp_9", "model": "muse-spark-1.3-1026", "output": [message]}
    monkeypatch.setattr(spark, "request_json", answering(answer))
    client = SparkApi("key")
    client.ask("p")
    assert (client.last_model, client.host, client.last_trace_id) == (
        "muse-spark-1.3-1026",
        "api.meta.ai",
        "resp_9",
    )


def test_live_spark_open_reports_the_model_its_response_named(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    choice = {"message": {"content": "hi"}}
    answer = {"id": "c1", "model": "muse-spark-open-served", "choices": [choice]}
    monkeypatch.setattr(spark_open, "request_json", answering(answer))
    client = SparkOpenApi("key")
    client.ask("p")
    assert client.last_model == "muse-spark-open-served"


@pytest.mark.parametrize(
    ("module", "client", "bare"),
    [
        (
            spark,
            SparkApi,
            {"output": [{"type": "message", "content": [{"text": "x"}]}]},
        ),
        (spark_open, SparkOpenApi, {"choices": [{"message": {"content": "x"}}]}),
    ],
)
def test_a_response_naming_no_model_or_id_leaves_both_unreported(
    monkeypatch: pytest.MonkeyPatch, module: Any, client: Any, bare: dict[str, Any]
) -> None:
    answers = [bare | {"id": "r1", "model": "m1"}, bare]
    monkeypatch.setattr(module, "request_json", answering(*answers))
    asked = client("key")
    asked.ask("first")
    asked.ask("second")
    assert (asked.last_model, asked.last_trace_id) == (None, None)


def test_a_client_that_reports_nothing_is_not_recorded() -> None:
    assert reported_call(FakeSpark([STRUCTURAL])) == NOBODY


def test_extract_records_the_call_that_read_the_pr(tmp_path: Path) -> None:
    client = ReportingSpark()
    pr = PullRequest(
        **SUMMARIES[0].model_dump(), base_sha="b", head_sha="h", python_files=[]
    )
    extraction = extract_pr(FakeGitHub(clean_tree(tmp_path)), client, REPO, pr)
    assert extraction.call == ModelCall(
        model="muse-spark-1.3", host="api.meta.ai", trace_id=client.trace_of(TITLE)
    )


def test_init_records_spark_as_the_extractor_of_an_inferred_root(
    tmp_path: Path,
) -> None:
    first = ReportingSpark()
    roots = init_roots(tmp_path, first, None)
    assert models_by_status(roots) == [("Inferred", [found(first, "extracted")])]


def test_a_corroborated_root_records_spark_then_spark_open(tmp_path: Path) -> None:
    first, second = ReportingSpark(), ReportingOpen(reading(SAME_TEXT))
    roots = init_roots(tmp_path, first, second)
    both = [found(first, "extracted"), found(second, "corroborated")]
    assert models_by_status(roots) == [("Corroborated", both)]


def test_an_uncorroborated_root_records_only_the_model_that_found_it(
    tmp_path: Path,
) -> None:
    first, second = ReportingSpark(), ReportingOpen(reading(OTHER))
    assert models_by_status(init_roots(tmp_path, first, second)) == [
        ("Uncorroborated", [found(first, "extracted")]),
        ("Uncorroborated", [found(second, "corroborated")]),
    ]


def test_spark_open_is_recorded_only_when_it_actually_ran(tmp_path: Path) -> None:
    first = ReportingSpark()
    roots = init_roots(tmp_path, first, FailingOpen({}))
    assert models_by_status(roots) == [("Inferred", [found(first, "extracted")])]


def test_a_client_naming_nothing_records_not_recorded(tmp_path: Path) -> None:
    roots = init_roots(tmp_path, FakeSpark([STRUCTURAL]), None)
    nobody = FoundBy(**NOBODY.model_dump(), role="extracted")
    assert models_by_status(roots) == [("Inferred", [nobody])]


def test_watch_records_the_models_the_same_way(tmp_path: Path) -> None:
    out = tmp_path / "watched"
    out.mkdir()
    registry = out / "registry.json"
    kept = Registry(repo=REPO, roots_dir=Path("roots"), rules=[])
    registry.write_text(kept.model_dump_json())
    first, second = ReportingSpark(), ReportingOpen(reading(SAME_TEXT))
    github, tree = FakeGitHub(clean_tree(tmp_path)), clean_tree(tmp_path)
    run_merged(registry, [9], tree, github, first, lambda _: None, second=second)
    both = [found(first, "extracted"), found(second, "corroborated")]
    assert models_by_status(load_roots(out / "roots")) == [("Corroborated", both)]
