from typing import Any

from knack.pipeline.http import request_json

URL = "https://api.meta.ai/v1/responses"
MODEL = "muse-spark-1.3"
TIMEOUT_SECONDS = 300


def answer_text(response: dict[str, Any]) -> str:
    # The first message item holds the answer; reasoning items come before it.
    messages = [item for item in response["output"] if item.get("type") == "message"]
    if not messages:
        raise ValueError("Spark returned no message")
    return str(messages[0]["content"][0]["text"])


class SparkApi:
    model = MODEL

    def __init__(self, api_key: str) -> None:
        self.headers = {"Authorization": f"Bearer {api_key}"}

    def ask(self, prompt: str) -> str:
        body = {"model": MODEL, "input": prompt, "reasoning": {"summary": "auto"}}
        return answer_text(request_json(URL, self.headers, body, TIMEOUT_SECONDS))
