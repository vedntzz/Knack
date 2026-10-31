from dataclasses import dataclass

from knack.contracts.models import Ruling
from knack.dispute.argue import ruling_prompt, SPARK_MODEL
from knack.dispute.latest import Disputed
from knack.miss.cases import EditCase, ModelAnswer
from knack.miss.loop import LoopOutcome
from knack.miss.selfcheck import (
    answer_json,
    ask_judge,
    Asked,
    prompt_sha256,
    settle,
    Settle,
)
from knack.miss.sources import case_from_receipt, Places
from knack.pipeline.ports import Spark

QUESTION = "the quotes do not answer the objection, so the deny should not hold"
AUTO_NOTE = "auto: Spark escalated, and Spark Open, asked independently, escalated too"
# Spark Open has no schema mode, so the shape argue's schema enforces is asked for in words.
JSON_REPLY = """
Reply with JSON only: {"decision": "hold" or "escalate", "reply": "one or two sentences", "cited_quotes": ["exact words from a quote"]}
"""


@dataclass(frozen=True)
class Second:
    # Spark Open, where the deny's edit snapshot is, and the miss loop to settle with.
    judge: Spark
    places: Places
    settle: Settle


def spark_escalated(done: Disputed) -> bool:
    # Spark's own escalate; a hold knack overturned, or no Spark at all, is not one.
    if done.record.decision != "escalate" or done.spark is None:
        return False
    return _escalates_quietly(done.spark[1])


def escalates(text: str) -> bool:
    return Ruling.model_validate(answer_json(text)).decision == "escalate"


def second_opinion(
    objection: str, done: Disputed, second: Second
) -> LoopOutcome | None:
    # The case comes first, so a deny with no edit snapshot asks Spark Open nothing.
    case = _auto_case(done, second.places)
    confirmed = [root for root in done.roots if root.status == "Confirmed"]
    prompt = ruling_prompt(objection, confirmed) + JSON_REPLY
    answers = [_spark_answer(done), ask_judge(second.judge, prompt, escalates)]
    return settle(second.settle, case, Asked("argue", QUESTION, answers))


def _auto_case(done: Disputed, places: Places) -> EditCase:
    case = case_from_receipt(done.record.receipt_hash, "must-pass", places)
    return case.model_copy(
        update={"source": f"{case.source} (auto)", "note": AUTO_NOTE}
    )


def _spark_answer(done: Disputed) -> ModelAnswer:
    prompt, answer = done.spark or ("", "")
    fields = {"model": SPARK_MODEL, "prompt_sha256": prompt_sha256(prompt)}
    return ModelAnswer(**fields, yes=_escalates_quietly(answer), answer=answer)


def _escalates_quietly(text: str) -> bool:
    try:
        return escalates(text)
    except Exception:
        return False
