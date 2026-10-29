import re
from typing import Literal

from pydantic import BaseModel, ConfigDict

from knack.pipeline.ports import Spark

Answer = Literal["yes", "no"]
ANSWER = re.compile(r"took the rejected path:\s*(yes|no)\b", re.IGNORECASE)
MAX_DIFF_CHARS = 60_000
# The judge sees the problem, the rejected approach and the diff; never the rule's verdict.
PROMPT = """You are reviewing a code change made in response to this bug report.

Bug report:
{ticket}

An approach the maintainers considered for this problem and rejected:
{alternatives}

The final diff of the change:
{diff}

Does the diff take the rejected approach? Explain in a few sentences, then end
with exactly one of these lines:
took the rejected path: yes
took the rejected path: no
"""


class BlindLabel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    # None when the judge failed or gave no readable answer.
    label: Answer | None
    # False for an empty diff, which is "no" without asking.
    asked: bool
    model: str
    raw: str | None = None
    error: str | None = None


def blind_prompt(ticket: str, alternatives: list[str], diff: str) -> str:
    shown = (
        diff
        if len(diff) <= MAX_DIFF_CHARS
        else diff[:MAX_DIFF_CHARS] + "\n[diff truncated]\n"
    )
    listed = "\n".join(f"- {alternative}" for alternative in alternatives)
    return PROMPT.format(ticket=ticket, alternatives=listed, diff=shown)


def parse_blind(answer: str) -> Answer | None:
    # The last answer line wins, so a quoted example earlier cannot decide it.
    found = ANSWER.findall(answer)
    return "yes" if found and found[-1].lower() == "yes" else ("no" if found else None)


def judge_blind(
    judge: Spark, ticket: str, alternatives: list[str], diff: str, diff_empty: bool
) -> BlindLabel:
    # A judge failure is recorded on the label; it never sinks the run.
    if diff_empty:
        return BlindLabel(label="no", asked=False, model=judge.model)
    try:
        raw = judge.ask(blind_prompt(ticket, alternatives, diff))
    except Exception as error:
        return _failed(judge.model, error)
    return BlindLabel(label=parse_blind(raw), asked=True, model=judge.model, raw=raw)


def _failed(model: str, error: Exception) -> BlindLabel:
    message = f"{type(error).__name__}: {error}"
    return BlindLabel(label=None, asked=True, model=model, error=message)
