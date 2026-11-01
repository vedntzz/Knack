from dataclasses import dataclass
from pathlib import Path

from knack.contracts.models import Ruling
from knack.dispute.argue import ruling_prompt, SPARK_MODEL
from knack.dispute.latest import Disputed
from knack.miss.cases import EditCase, ModelAnswer
from knack.miss.provisional import save_provisional
from knack.miss.selfcheck import (
    answer_json,
    ask_judge,
    Asked,
    Log,
    log_check,
    prompt_sha256,
    self_checks_path,
)
from knack.miss.sources import case_from_receipt, Places
from knack.pipeline.ports import Spark

QUESTION = "the quotes do not answer the objection, so the deny should not hold"
AUTO_NOTE = "auto, provisional: Spark escalated, and Spark Open, asked independently, escalated too"
HELD = 'provisional must-pass case {path}; a case only after: knack resolve {hash} allow --reason "<why>"'
# Spark Open has no schema mode, so the shape argue's schema enforces is asked for in words.
JSON_REPLY = """
Reply with JSON only: {"decision": "hold" or "escalate", "reply": "one or two sentences", "cited_quotes": ["exact words from a quote"]}
"""


@dataclass(frozen=True)
class Second:
    # Spark Open, where the deny's edit snapshot is, and the registry the case waits beside.
    judge: Spark
    places: Places
    registry: Path
    log: Log


def spark_escalated(done: Disputed) -> bool:
    # Spark's own escalate; a hold knack overturned, or no Spark at all, is not one.
    if done.record.decision != "escalate" or done.spark is None:
        return False
    return _escalates_quietly(done.spark[1])


def escalates(text: str) -> bool:
    return Ruling.model_validate(answer_json(text)).decision == "escalate"


def second_opinion(objection: str, done: Disputed, second: Second) -> Path | None:
    # Agreement only holds a provisional case; the miss loop never runs from an objection.
    case = _auto_case(done, second.places)
    asked = _asked(objection, done, second.judge)
    checks = self_checks_path(second.registry)
    agreed = log_check(checks, second.log, case, asked)
    return _held(second, done.record.receipt_hash, agreed) if agreed else None


def _asked(objection: str, done: Disputed, judge: Spark) -> Asked:
    # The case comes first in second_opinion, so a deny with no edit snapshot asks no one.
    confirmed = [root for root in done.roots if root.status == "Confirmed"]
    prompt = ruling_prompt(objection, confirmed) + JSON_REPLY
    answers = [_spark_answer(done), ask_judge(judge, prompt, escalates)]
    return Asked("argue", QUESTION, answers)


def _held(second: Second, receipt_hash: str, case: EditCase) -> Path:
    # Waits beside the registry until a person's knack resolve allow promotes it.
    path = save_provisional(second.registry, receipt_hash, case)
    second.log(HELD.format(path=path, hash=receipt_hash))
    return path


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
