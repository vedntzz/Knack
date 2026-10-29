from typing import Any

import pytest
from knack.pipeline import spark_open
from knack.pipeline.spark_open import chat_answer_text, MODEL, SparkOpenApi, URL

Sent = list[tuple[str, dict[str, str], Any]]


def chat_response(content: Any) -> dict[str, Any]:
    # The OpenAI-compatible chat completions shape Baseten returns.
    message = {"role": "assistant", "content": content}
    return {"choices": [{"index": 0, "message": message, "finish_reason": "stop"}]}


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> Sent:
    calls: Sent = []

    def fake(url: str, headers: dict[str, str], body: Any, timeout: float) -> Any:
        calls.append((url, headers, body))
        return chat_response("the answer")

    monkeypatch.setattr(spark_open, "request_json", fake)
    return calls


def test_spark_open_is_basetens_chat_completions_endpoint() -> None:
    assert URL == "https://inference.baseten.co/v1/chat/completions"
    assert MODEL == "meta-models/muse-spark-open-1026"


def test_ask_sends_the_prompt_as_one_user_message(sent: Sent) -> None:
    assert SparkOpenApi("key").ask("the prompt") == "the answer"
    [(url, headers, body)] = sent
    assert url == URL and headers == {"Authorization": "Bearer key"}
    assert body == {
        "model": MODEL,
        "messages": [{"role": "user", "content": "the prompt"}],
    }


def test_roots_record_the_spark_open_model_id() -> None:
    assert SparkOpenApi("key").model == MODEL


def test_answer_text_is_the_first_choice_message() -> None:
    assert chat_answer_text(chat_response("hi")) == "hi"


@pytest.mark.parametrize("response", [chat_response(None), {"choices": []}])
def test_answer_without_content_is_an_error(response: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        chat_answer_text(response)
