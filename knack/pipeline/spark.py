from typing import Any
from urllib.parse import urlsplit

from knack.pipeline.http import request_json, response_id

URL = "https://api.meta.ai/v1/responses"
MODEL = "muse-spark-1.3"
HOST = urlsplit(URL).netloc
TIMEOUT_SECONDS = 300


def reported_model(response: dict[str, Any]) -> str | None:
    # The model the response says answered; None when it names none.
    found = response.get("model")
    return str(found) if found else None


def answer_text(response: dict[str, Any]) -> str:
    # The first message item holds the answer; reasoning items come before it.
    messages = [item for item in response["output"] if item.get("type") == "message"]
    if not messages:
        raise ValueError("Spark returned no message")
    return str(messages[0]["content"][0]["text"])


class SparkApi:
    model = MODEL
    host = HOST

    def __init__(self, api_key: str) -> None:
        self.headers = {"Authorization": f"Bearer {api_key}"}
        # The last response's model and id, exactly as it reported them.
        self.last_model: str | None = None
        self.last_trace_id: str | None = None

    def ask(self, prompt: str) -> str:
        body = {"model": MODEL, "input": prompt, "reasoning": {"summary": "auto"}}
        self.last_model = self.last_trace_id = None
        response = request_json(URL, self.headers, body, TIMEOUT_SECONDS)
        self.last_model = reported_model(response)
        self.last_trace_id = response_id(response)
        return answer_text(response)
