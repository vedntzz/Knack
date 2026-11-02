import io
import json
import os
from pathlib import Path

import pytest
from knack.contracts.models import Root
from knack.dispute import argue as argue_module
from knack.dispute.argue import argue, Ruling, SparkRuling
from knack.roots.store import load_roots
from pydantic import ValidationError

ROOTS = Path(__file__).parents[2] / "data" / "roots" / "airflow"
QUOTE_75025 = "I removed them rather than aliasing them onto `DagRun.state` and `DagRun.start_date`."
RESTATES_REJECTED = (
    "The frontend still sends sort=state. Let me alias state and start_date onto "
    "DagRun.state and DagRun.start_date so those sorts work again."
)
UNCOVERED_CONDITION = (
    "A customer's external dashboard is pinned to an old client that can only send "
    "sort=state, and we contractually must not break it before March. Can I add the alias?"
)
live = pytest.mark.skipif(
    os.environ.get("KNACK_LIVE") != "1" or not os.environ.get("MODEL_API_KEY"),
    reason="needs KNACK_LIVE=1 and MODEL_API_KEY",
)


def root(root_id: str, quote: str, status: str = "Confirmed") -> Root:
    return Root.model_validate(
        {
            "id": root_id,
            "title": "t",
            "decision": "d",
            "why": "w",
            "decided_by": "Pushkal Gupta",
            "source_url": "https://github.com/apache/airflow/pull/75025",
            "quote": quote,
            "status": status,
        }
    )


CONFIRMED = root("airflow-75025-1", QUOTE_75025)
INFERRED = root("airflow-74150-1", "never on asyncio's default executor:", "Inferred")


def spark_says(decision: str, reply: str, quotes: list[str]):
    # Fake Spark that records every prompt and returns one fixed ruling.
    prompts: list[str] = []
    answer = json.dumps({"decision": decision, "reply": reply, "cited_quotes": quotes})

    def ask(prompt: str) -> str:
        prompts.append(prompt)
        return answer

    return ask, prompts


def test_ruling_is_frozen() -> None:
    ruling = Ruling(decision="hold", reply="no", cited_quotes=[QUOTE_75025])
    with pytest.raises(ValidationError):
        ruling.decision = "escalate"  # type: ignore[misc]


def test_hold_when_objection_restates_rejected_alternative() -> None:
    ask, _ = spark_says("hold", "We chose not to alias.", ["rather than aliasing them"])
    ruling = argue(RESTATES_REJECTED, [CONFIRMED], ask=ask)
    assert ruling.decision == "hold"
    assert ruling.cited_quotes == ["rather than aliasing them"]


def test_escalate_when_objection_raises_uncovered_condition() -> None:
    ask, _ = spark_says("escalate", "The quotes say nothing about pinned clients.", [])
    ruling = argue(UNCOVERED_CONDITION, [CONFIRMED], ask=ask)
    assert ruling.decision == "escalate"


def test_fabricated_quote_is_rejected_as_escalate() -> None:
    ask, _ = spark_says("hold", "We never alias.", ["Aliasing is forbidden forever."])
    ruling = argue(RESTATES_REJECTED, [CONFIRMED], ask=ask)
    assert ruling.decision == "escalate"
    assert ruling.cited_quotes == []
    assert "verbatim" in ruling.reply


def test_quote_from_inferred_root_is_rejected() -> None:
    ask, _ = spark_says(
        "hold", "Executor rule.", ["never on asyncio's default executor"]
    )
    ruling = argue(RESTATES_REJECTED, [CONFIRMED, INFERRED], ask=ask)
    assert ruling.decision == "escalate"


def test_prompt_carries_only_confirmed_quotes() -> None:
    ask, prompts = spark_says("escalate", "Unsure.", [])
    argue(RESTATES_REJECTED, [CONFIRMED, INFERRED], ask=ask)
    assert QUOTE_75025 in prompts[0]
    assert INFERRED.quote not in prompts[0]


def test_hold_without_citation_is_rejected() -> None:
    ask, _ = spark_says("hold", "Because I said so.", [])
    ruling = argue(RESTATES_REJECTED, [CONFIRMED], ask=ask)
    assert ruling.decision == "escalate"


def test_no_confirmed_roots_escalates_without_asking() -> None:
    ask, prompts = spark_says("hold", "x", [INFERRED.quote])
    ruling = argue(RESTATES_REJECTED, [INFERRED], ask=ask)
    assert ruling.decision == "escalate"
    assert prompts == []


@pytest.mark.parametrize("answer", ["not json", '{"decision": "maybe"}', "boom"])
def test_bad_spark_answer_escalates_never_crashes(answer: str) -> None:
    def ask(prompt: str) -> str:
        if answer == "boom":
            raise ConnectionError("spark down")
        return answer

    ruling = argue(RESTATES_REJECTED, [CONFIRMED], ask=ask)
    assert ruling.decision == "escalate"


@live
def test_live_spark_holds_on_rejected_alternative() -> None:
    ruling = argue(RESTATES_REJECTED, load_roots(ROOTS))
    assert ruling.decision == "hold", ruling.reply


@live
def test_live_spark_escalates_on_uncovered_condition() -> None:
    ruling = argue(UNCOVERED_CONDITION, load_roots(ROOTS))
    assert ruling.decision == "escalate", ruling.reply


def spark_replies(monkeypatch: pytest.MonkeyPatch, response: dict[str, object]) -> None:
    # Fake Meta Responses endpoint answering every POST with one body.
    def urlopen(request: object, timeout: float) -> io.BytesIO:
        return io.BytesIO(json.dumps(response).encode())

    monkeypatch.setenv("MODEL_API_KEY", "key")
    monkeypatch.setattr(argue_module.urllib.request, "urlopen", urlopen)


def message(text: str) -> list[dict[str, object]]:
    return [{"type": "message", "content": [{"type": "output_text", "text": text}]}]


def test_spark_keeps_the_response_id_as_its_trace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spark_replies(monkeypatch, {"id": "resp_abc", "output": message("ruled")})
    spark = SparkRuling()
    assert (spark("prompt"), spark.last_trace_id) == ("ruled", "resp_abc")
    assert spark.host == "api.meta.ai"


def test_a_response_without_an_id_has_no_trace(monkeypatch: pytest.MonkeyPatch) -> None:
    spark_replies(monkeypatch, {"output": message("ruled")})
    spark = SparkRuling()
    spark("prompt")
    assert spark.last_trace_id is None
