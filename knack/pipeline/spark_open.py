from typing import Any

from knack.pipeline.http import request_json

URL = "https://inference.baseten.co/v1/chat/completions"
MODEL = "meta-models/muse-spark-open-1026"
TIMEOUT_SECONDS = 300


def chat_answer_text(response: dict[str, Any]) -> str:
    # OpenAI-compatible: the answer is the first choice's message content.
    choices: list[dict[str, Any]] = response.get("choices") or []
    content = choices[0]["message"].get("content") if choices else None
    if not content:
        raise ValueError("Spark Open returned no message content")
    return str(content)


class SparkOpenApi:
    model = MODEL

    def __init__(self, api_key: str) -> None:
        self.headers = {"Authorization": f"Bearer {api_key}"}

    def ask(self, prompt: str) -> str:
        body = {"model": MODEL, "messages": [{"role": "user", "content": prompt}]}
        return chat_answer_text(request_json(URL, self.headers, body, TIMEOUT_SECONDS))
