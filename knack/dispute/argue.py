import json
import os
import urllib.request
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit

from knack.contracts.models import Root, Ruling
from knack.pipeline.http import response_id

Ask = Callable[[str], str]
SPARK_URL = "https://api.meta.ai/v1/responses"
SPARK_MODEL = "muse-spark-1.3"
SPARK_HOST = urlsplit(SPARK_URL).netloc
SPARK_TIMEOUT_S = 120
NO_CONFIRMED_ROOTS = "No Confirmed decision covers this, so a person has to decide."
SPARK_FAILED = "Spark could not give a ruling, so a person has to decide"
NOT_VERBATIM = "Spark cited words that are not verbatim in any Confirmed decision, so a person has to decide."
UNCITED_HOLD = "Spark held without citing the decision, so a person has to decide."
PROMPT = """An AI coding agent objects to a recorded team decision. Answer as the person who made it.
Use ONLY the verbatim quotes below. Do not add reasons they do not state.
Rule "hold" when the quotes already answer the objection, for example when it restates an
alternative the quotes reject. An objection that proposes a rejected alternative below holds,
even reworded or with a reason the quote already weighs. An offer in a quote to do it the other
way is not a reversal: the decision is what was done. Cite the exact words you rely on.
Rule "escalate" when the objection raises a condition, constraint or case the quotes do not
address. Say plainly what they do not cover; a person will decide.
Every cited_quotes entry must be copied character for character from a quote below; the
decision and rejected alternative lines are summaries, never cite them.

QUOTES:
{quotes}

OBJECTION:
{objection}
"""
REASK = """
Your last ruling cited words that are not in any quote: {cited}
Rule again. Copy every cited_quotes entry character for character from a quote above.
"""


def argue(objection: str, roots: list[Root], ask: Ask | None = None) -> Ruling:
    confirmed = [root for root in roots if root.status == "Confirmed"]
    if not confirmed:
        return _escalate(NO_CONFIRMED_ROOTS)
    prompt = ruling_prompt(objection, confirmed)
    quotes = [root.quote for root in confirmed]
    return _checked(_ruled_verbatim(prompt, quotes, ask or ask_spark), quotes)


class SparkRuling:
    # Spark behind argue's Ask; it keeps the last response id as the ruling's trace.
    host = SPARK_HOST

    def __init__(self) -> None:
        self.last_trace_id: str | None = None

    def __call__(self, prompt: str) -> str:
        self.last_trace_id = None
        response = _post_spark(prompt)
        self.last_trace_id = response_id(response)
        return _message_text(response)


def _post_spark(prompt: str) -> dict[str, Any]:
    body = json.dumps(_spark_body(prompt)).encode()
    request = urllib.request.Request(SPARK_URL, data=body, headers=_spark_headers())
    with urllib.request.urlopen(request, timeout=SPARK_TIMEOUT_S) as response:
        return json.load(response)


ask_spark = SparkRuling()


def ruling_prompt(objection: str, confirmed: list[Root]) -> str:
    quotes = "\n\n".join(_quote_block(root) for root in confirmed)
    return PROMPT.format(quotes=quotes, objection=objection)


def _quote_block(root: Root) -> str:
    head = f"[{root.id}] decided by {root.decided_by} ({root.source_url}):"
    return "\n".join(
        [head, f"Decision: {root.decision}", *_rejected(root), f'"{root.quote}"']
    )


def _rejected(root: Root) -> list[str]:
    # Named apart from the quote, so an offer in the quote never reads as the decision.
    alternative = root.rejected_alternative
    return [f"Rejected alternative: {alternative}"] if alternative else []


def _ask_for_ruling(prompt: str, ask: Ask) -> Ruling:
    try:
        return Ruling.model_validate_json(ask(prompt))
    except Exception as error:
        # Spark down or off-schema: a person decides, never a crash.
        return _escalate(f"{SPARK_FAILED} ({type(error).__name__}).")


def _ruled_verbatim(prompt: str, quotes: list[str], ask: Ask) -> Ruling:
    # A hold citing words not in the record is asked once more, then checked as it stands.
    ruling = _ask_for_ruling(prompt, ask)
    invented = _invented(ruling, quotes)
    if ruling.decision != "hold" or not invented:
        return ruling
    return _ask_for_ruling(prompt + REASK.format(cited=json.dumps(invented)), ask)


def _invented(ruling: Ruling, quotes: list[str]) -> list[str]:
    return [cited for cited in ruling.cited_quotes if not _is_verbatim(cited, quotes)]


def _checked(ruling: Ruling, quotes: list[str]) -> Ruling:
    if not all(_is_verbatim(cited, quotes) for cited in ruling.cited_quotes):
        return _escalate(NOT_VERBATIM)
    if ruling.decision == "hold" and not ruling.cited_quotes:
        return _escalate(UNCITED_HOLD)
    return ruling


def _is_verbatim(cited: str, quotes: list[str]) -> bool:
    # Empty strings are substrings of everything, so they prove nothing.
    return bool(cited.strip()) and any(cited in quote for quote in quotes)


def _escalate(reason: str) -> Ruling:
    return Ruling(decision="escalate", reply=reason, cited_quotes=[])


def _spark_body(prompt: str) -> dict[str, Any]:
    schema = Ruling.model_json_schema()
    output = {"type": "json_schema", "name": "ruling", "strict": True, "schema": schema}
    return {"model": SPARK_MODEL, "input": prompt, "text": {"format": output}}


def _spark_headers() -> dict[str, str]:
    key = os.environ["MODEL_API_KEY"]
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _message_text(response: dict[str, Any]) -> str:
    message = next(item for item in response["output"] if item["type"] == "message")
    return message["content"][0]["text"]
