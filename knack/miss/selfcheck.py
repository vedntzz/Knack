import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from knack.miss.cases import case_path, cases_dir, EditCase, ModelAnswer
from knack.miss.loop import LoopOutcome, outcome_lines
from knack.pipeline.ports import Spark

SELF_CHECKS = "self_checks.jsonl"
Trigger = Literal["watch", "argue"]
RunLoop = Callable[[list[EditCase]], LoopOutcome]
Read = Callable[[str], bool]
Log = Callable[[str], None]


class SelfCheck(BaseModel):
    # One question put to both models, kept whether or not they agreed.
    model_config = ConfigDict(frozen=True, extra="forbid")

    time: str
    trigger: Trigger
    # What a yes means, e.g. the change takes the rejected path.
    question: str
    rule_id: str
    source: str
    file: str
    answers: list[ModelAnswer]
    # The recorded case's key when both said yes; None when it was logged only.
    case_key: str | None


@dataclass(frozen=True)
class Asked:
    trigger: Trigger
    question: str
    answers: list[ModelAnswer]


@dataclass(frozen=True)
class Settle:
    # The registry the case is recorded beside, the check log, and the miss loop.
    registry: Path
    checks: Path
    run_loop: RunLoop
    log: Log


def self_checks_path(registry_path: Path) -> Path:
    return registry_path.parent / SELF_CHECKS


def prompt_sha256(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def ask_judge(judge: Spark, prompt: str, read: Read) -> ModelAnswer:
    # A model error or an unreadable answer is a no, never a crash.
    fields = {"model": judge.model, "prompt_sha256": prompt_sha256(prompt)}
    try:
        text = judge.ask(prompt)
    except Exception as error:
        return ModelAnswer(**fields, yes=False, answer=_error_text(error))
    return ModelAnswer(**fields, yes=_read_quietly(read, text), answer=text)


def answer_json(text: str) -> dict[str, Any]:
    # The outermost {...} in the answer, so a fenced or chatty reply still reads.
    found: Any = json.loads(text[text.index("{") : text.rindex("}") + 1])
    if not isinstance(found, dict):
        raise ValueError("the answer is not a JSON object")
    return cast(dict[str, Any], found)


def agreed(answers: list[ModelAnswer]) -> bool:
    # Two different models, both yes; one model twice is not agreement.
    models = {answer.model for answer in answers}
    return len(models) == 2 and len(answers) == 2 and all(a.yes for a in answers)


def settle(ports: Settle, case: EditCase, asked: Asked) -> LoopOutcome | None:
    # Both yes: recorded with both answers, then the miss loop; otherwise logged only.
    receipted = log_check(ports.checks, ports.log, case, asked)
    return _looped(ports, receipted) if receipted else None


def log_check(checks: Path, log: Log, case: EditCase, asked: Asked) -> EditCase | None:
    # Every check is kept; the case carrying both answers comes back only when they agreed.
    receipted = case.model_copy(update={"answers": asked.answers})
    recorded = agreed(asked.answers)
    _append_check(checks, _check(receipted, asked, recorded))
    log(_settled_line(receipted, asked, recorded))
    return receipted if recorded else None


def load_checks(path: Path) -> list[SelfCheck]:
    # A missing file has no checks; a torn line is skipped.
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [check for check in map(_check_or_none, lines) if check]


def _looped(ports: Settle, case: EditCase) -> LoopOutcome | None:
    # A case recorded before is not run again; a loop error keeps the old rule.
    if case_path(cases_dir(ports.registry), case).exists():
        ports.log(f"self-check: {case.name} is already recorded for {case.rule_id}")
        return None
    return _loop_quietly(ports, case)


def _loop_quietly(ports: Settle, case: EditCase) -> LoopOutcome | None:
    try:
        outcome = ports.run_loop([case])
    except Exception as error:
        ports.log(f"self-check loop {_error_text(error)}; the old rule is kept")
        return None
    ports.log("\n".join(outcome_lines(outcome)))
    return outcome


def _check(case: EditCase, asked: Asked, recorded: bool) -> SelfCheck:
    fields = {"time": datetime.now(timezone.utc).isoformat(), "file": case.file}
    fields |= {"trigger": asked.trigger, "question": asked.question}
    fields |= {"rule_id": case.rule_id, "source": case.source}
    key = case.key if recorded else None
    return SelfCheck.model_validate(
        fields | {"answers": asked.answers, "case_key": key}
    )


def _settled_line(case: EditCase, asked: Asked, recorded: bool) -> str:
    said = ", ".join(f"{a.model} {'yes' if a.yes else 'no'}" for a in asked.answers)
    then = _then(case, asked.trigger) if recorded else "logged only"
    return f"self-check {case.rule_id} {case.file} ({asked.question}): {said}; {then}"


def _then(case: EditCase, trigger: Trigger) -> str:
    # An objection's agreement waits for a person; a merge's is recorded at once.
    if trigger == "argue":
        return f"holding a provisional {case.kind} case for a person"
    return f"recording {case.kind} case"


def _append_check(path: Path, check: SelfCheck) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(check.model_dump_json() + "\n")


def _check_or_none(line: str) -> SelfCheck | None:
    try:
        return SelfCheck.model_validate_json(line)
    except ValidationError:
        return None


def _read_quietly(read: Read, text: str) -> bool:
    try:
        return read(text) is True
    except Exception:
        return False


def _error_text(error: Exception) -> str:
    return f"error: {type(error).__name__}: {error}"
