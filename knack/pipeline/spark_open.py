import os
from typing import Any

from knack.pipeline.http import request_json

URL = "https://inference.baseten.co/v1/chat/completions"
MODEL = "meta-models/muse-spark-open-1026"
TIMEOUT_SECONDS = 300
# Exactly "1" keeps Spark Open's reasoning trace; anything else changes nothing.
OPEN_WEIGHTS_ENV = "KNACK_OPEN_WEIGHTS"


def chat_answer_text(response: dict[str, Any]) -> str:
    # OpenAI-compatible: the answer is the first choice's message content.
    choices: list[dict[str, Any]] = response.get("choices") or []
    content = choices[0]["message"].get("content") if choices else None
    if not content:
        raise ValueError("Spark Open returned no message content")
    return str(content)


def open_weights_on() -> bool:
    return os.environ.get(OPEN_WEIGHTS_ENV) == "1"


def reasoning_trace(response: dict[str, Any]) -> str | None:
    # Open-weights servers put the trace in reasoning_content, or reasoning.
    choices: list[dict[str, Any]] = response.get("choices") or []
    message: dict[str, Any] = (choices[0].get("message") or {}) if choices else {}
    trace = message.get("reasoning_content") or message.get("reasoning")
    return str(trace) if trace else None


class SparkOpenApi:
    model = MODEL

    def __init__(self, api_key: str) -> None:
        self.headers = {"Authorization": f"Bearer {api_key}"}
        # The last answer's reasoning, kept only when KNACK_OPEN_WEIGHTS=1.
        self.last_trace: str | None = None

    def ask(self, prompt: str) -> str:
        body = {"model": MODEL, "messages": [{"role": "user", "content": prompt}]}
        response = request_json(URL, self.headers, body, TIMEOUT_SECONDS)
        self.last_trace = reasoning_trace(response) if open_weights_on() else None
        return chat_answer_text(response)
