import json
from collections.abc import Callable
from functools import partial

from pydantic import TypeAdapter

from knack.pipeline.models import Decision, Extraction, ExtractStage, Post, PullRequest
from knack.pipeline.ports import GitHub, Spark

INSTRUCTIONS = """You are reading a merged pull request. Extract the engineering decisions it records,
including any alternatives that were considered and NOT chosen.
Return ONLY JSON, no prose:
{"decisions": [{"decision": str, "why": str, "decided_by": str,
  "rejected_alternatives": [{"alternative": str, "why_rejected": str, "quote": str}]}]}
Rules: every "quote" must be copied verbatim from the text, character for character.
If nothing was rejected, return an empty list. Do not guess.

"""
PR_HEADER = "PR TEXT:\n"
PROMPT = INSTRUCTIONS + PR_HEADER
DECISIONS = TypeAdapter(list[Decision])
# Called once per PR as it finishes: (number, extraction or None when it failed).
OnExtracted = Callable[[int, Extraction | None], None]
Read = Callable[[PullRequest], Extraction]


def _ignore(number: int, extraction: Extraction | None) -> None:
    pass


def extract_all(
    github: GitHub,
    spark: Spark,
    repo: str,
    prs: list[PullRequest],
    on_extracted: OnExtracted = _ignore,
    few_shot: str = "",
) -> ExtractStage:
    # A PR whose fetch or answer fails is listed, never fatal to the run.
    read = partial(extract_pr, github, spark, repo, few_shot=few_shot)
    extract = partial(_extract_reported, read, on_extracted)
    results = [(pr.number, extract(pr)) for pr in prs]
    extractions = [e for _, e in results if e is not None]
    failed = [number for number, e in results if e is None]
    return ExtractStage(extractions=extractions, failed=failed)


def extract_pr(
    github: GitHub, spark: Spark, repo: str, pr: PullRequest, few_shot: str = ""
) -> Extraction:
    # few_shot holds past human corrections, placed before the PR text.
    text = thread_text(pr, github.posts(repo, pr.number))
    answer = spark.ask(INSTRUCTIONS + few_shot + PR_HEADER + text)
    decisions = mark_verbatim(parse_decisions(answer), text)
    return Extraction(number=pr.number, title=pr.title, decisions=decisions)


def thread_text(pr: PullRequest, posts: list[Post]) -> str:
    parts = [f"Title: {pr.title}\nAuthor: {pr.author}", pr.body]
    parts += [f"{post.heading}: {post.body}" for post in posts]
    return "\n\n".join(parts)


def parse_decisions(answer: str) -> list[Decision]:
    # Raises ValueError unless the answer is JSON holding a decisions list.
    data = json.loads(strip_fences(answer, "json"))
    if not isinstance(data, dict) or "decisions" not in data:
        raise ValueError("answer has no decisions list")
    return DECISIONS.validate_python(data["decisions"])


def mark_verbatim(decisions: list[Decision], text: str) -> list[Decision]:
    # A quote counts only when it appears character for character in the thread.
    return [_marked(decision, text) for decision in decisions]


def strip_fences(answer: str, language: str) -> str:
    text = answer.strip().removeprefix(f"```{language}").removeprefix("```")
    return text.removesuffix("```").strip()


def _marked(decision: Decision, text: str) -> Decision:
    alternatives = [
        a.model_copy(update={"verbatim": bool(a.quote) and a.quote in text})
        for a in decision.rejected_alternatives
    ]
    return decision.model_copy(update={"rejected_alternatives": alternatives})


def _extract_reported(
    read: Read, on_extracted: OnExtracted, pr: PullRequest
) -> Extraction | None:
    extraction = _extract_or_none(read, pr)
    on_extracted(pr.number, extraction)
    return extraction


def _extract_or_none(read: Read, pr: PullRequest) -> Extraction | None:
    try:
        return read(pr)
    except Exception:
        return None
