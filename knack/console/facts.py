import difflib
import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from knack.bench.heldout_pr import HeldOutPr, Score
from knack.bench.proof_grid import GATES, SIDE_GATES
from knack.console.verdict import RootView, VerdictView
from knack.contracts.models import HeldOutScore, RuleProof, SideProof
from knack.dispute.rulings import RulingRecord
from knack.miss.selfcheck import answer_json, SelfCheck
from knack.pipeline.prove import MIN_FLAGGED, MUST_FLAG
from knack.receipts.edits import EditSnapshot

# Lines shown above the first matched line and below the last right one.
ABOVE, BELOW = 3, 2
# How far from the matched lines a line with the decision's names is looked for.
NEAR = 8
SNAKE = re.compile(r"\b[a-z]+(?:_[a-z]+)+\b")
LineSpan = tuple[int, int]


class CodeLine(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    number: int
    text: str
    # hit: a matched line; right: already uses the decision's names; else context.
    kind: str
    added: bool


class Figures(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    passed: int
    gates: int
    false_alarms: int | None
    release: str | None


class Person(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    # Who wrote it and, when decided_by names one, who merged it.
    author: str
    merged_by: str | None


class VerdictPage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    view: VerdictView
    blocked: bool
    pr: str | None
    person: Person | None
    merged_on: str | None
    delete: LineSpan | None
    right: LineSpan | None
    # The agent's proposed lines around the match; None without an edit snapshot.
    code: list[CodeLine] | None
    figures: Figures | None


def verdict_page(view: VerdictView, snapshot: EditSnapshot | None) -> VerdictPage:
    # Pure: the block page's facts from the verdict, its root, its proof and the edit.
    delete, root = matched_span(view), view.root
    right = right_span(snapshot, root, view) if snapshot and delete else None
    code = code_lines(snapshot, delete, right) if snapshot and delete else None
    found = {"view": view, "blocked": view.outcome == "deny", "delete": delete}
    found |= {"right": right, "code": code, "figures": figures(view.proof)}
    return VerdictPage.model_validate(found | root_facts(root))


def root_facts(root: RootView | None) -> dict[str, Any]:
    # The PR, the people and the merge day, each None when the root lacks it.
    if root is None:
        return {"pr": None, "person": None, "merged_on": None}
    pr = re.search(r"/pull/(\d+)", root.source_url)
    found = {"pr": f"#{pr.group(1)}" if pr else None, "person": person(root.decided_by)}
    return found | {"merged_on": day_of(root.merged_at)}


def person(decided_by: str) -> Person:
    # "Name (author); approved and merged by handle": the name, then the merger.
    merger = re.search(r"merged by (\S+)", decided_by)
    author = re.split(r" \(|;", decided_by)[0].strip() or decided_by
    return Person(author=author, merged_by=merger.group(1) if merger else None)


def day_of(stamp: str | None) -> str | None:
    try:
        moment = datetime.fromisoformat(stamp or "")
    except ValueError:
        return None
    return f"{moment:%b} {moment.day} {moment.year}"


def matched_span(view: VerdictView) -> LineSpan | None:
    # A match spanning lines counts to its last line.
    ends = [(m.line, m.line + m.text.count("\n")) for m in view.matched]
    return (min(e[0] for e in ends), max(e[1] for e in ends)) if ends else None


def right_span(
    snapshot: EditSnapshot, root: RootView | None, view: VerdictView
) -> LineSpan | None:
    # Near the match, the lines that spell a name the decision uses and the match lacks.
    names = decision_names(root, view)
    near = window(snapshot.after, matched_span(view), NEAR)
    found = [n for n, text in near if any(f'"{name}"' in text for name in names)]
    return (min(found), max(found)) if found else None


def decision_names(root: RootView | None, view: VerdictView) -> set[str]:
    matched = " ".join(match.text for match in view.matched)
    spelled = set(SNAKE.findall(root.decision)) if root else set[str]()
    return {name for name in spelled if name not in matched}


def window(text: str, span: LineSpan | None, reach: int) -> list[tuple[int, str]]:
    lines = text.splitlines()
    low, high = span or (1, len(lines))
    first, last = max(1, low - reach), min(len(lines), high + reach)
    return [(n, lines[n - 1]) for n in range(first, last + 1)]


def code_lines(
    snapshot: EditSnapshot, delete: LineSpan, right: LineSpan | None
) -> list[CodeLine]:
    low, high = delete[0] - ABOVE, max(delete[1], right[1] if right else 0) + BELOW
    shown = window(snapshot.after, (low, high), 0)
    added = added_lines(snapshot)
    return [code_line(n, text, delete, right, added) for n, text in shown]


def code_line(
    n: int, text: str, delete: LineSpan, right: LineSpan | None, added: set[int]
) -> CodeLine:
    kind = "hit" if inside(n, delete) else "right" if inside(n, right) else "context"
    return CodeLine(number=n, text=text, kind=kind, added=n in added)


def inside(n: int, span: LineSpan | None) -> bool:
    return span is not None and span[0] <= n <= span[1]


def added_lines(snapshot: EditSnapshot) -> set[int]:
    # Line numbers in the proposed file that the edit inserted or rewrote.
    before, after = (snapshot.before or "").splitlines(), snapshot.after.splitlines()
    blocks = difflib.SequenceMatcher(a=before, b=after, autojunk=False).get_opcodes()
    changed = [(j1, j2) for tag, _, _, j1, j2 in blocks if tag in ("insert", "replace")]
    return {n + 1 for j1, j2 in changed for n in range(j1, j2)}


def figures(proof: RuleProof | None) -> Figures | None:
    # The proof grid's eight gates, scored the way bench/proof_grid scores them.
    if proof is None:
        return None
    marks = [*side_marks(proof), tree_clean(proof), release_clean(proof)]
    passed = sum(marks) + heldout_passed(proof)
    alarms, release = false_alarms(proof)
    counted = {"passed": passed, "gates": len(GATES)}
    return Figures(false_alarms=alarms, release=release, **counted)


def side_marks(proof: RuleProof) -> list[bool]:
    sides = {side.side: side for side in proof.sides}
    return [
        all(side_holds(sides.get(n)) for n in names) for names in SIDE_GATES.values()
    ]


def side_holds(side: SideProof | None) -> bool:
    if side is None or not side.files or side.errors:
        return False
    needed = MIN_FLAGGED.get(side.side, 1)
    return side.flagged >= needed if MUST_FLAG[side.side] else side.flagged == 0


def tree_clean(proof: RuleProof) -> bool:
    return proof.tree_error is None and proof.false_positives == 0


def release_clean(proof: RuleProof) -> bool:
    old = proof.old_release
    return old is not None and old.error is None and old.false_positives == 0


def heldout_passed(proof: RuleProof) -> bool:
    sets = proof.heldout_sets
    same, cross = score(sets.get("same")), score(sets.get("cross"))
    scored = HeldOutPr(repo="", pr="", same=same, cross=cross)
    return scored.passed("same") and scored.passed("cross")


def score(held: HeldOutScore | None) -> Score:
    if held is None or held.error:
        return None
    return (held.caught, held.violations, held.allowed, held.compliant)


def false_alarms(proof: RuleProof) -> tuple[int | None, str | None]:
    # Tree and release false alarms together; unknown when either scan did not finish.
    old = proof.old_release
    if old is None or old.error or proof.tree_error:
        return None, old.ref if old else None
    return proof.false_positives + old.false_positives, old.ref


class SecondAnswer(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    # A model asked beside the ruling's own, and what it said, verbatim.
    model: str
    # None when no self-check recorded its answer or the answer did not read.
    decision: str | None
    reply: str | None


class ArguePage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    block: VerdictPage
    ruling: RulingRecord
    # True when the deny's latest ruling escalated, so a held page exists.
    held: bool


class HeldPage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    block: VerdictPage
    ruling: RulingRecord
    second: list[SecondAnswer]
    # True when an earlier objection was held by the record, so argue shows that answer.
    answered: bool


def argue_page(block: VerdictPage, rulings: list[RulingRecord]) -> ArguePage | None:
    # Pure: the latest hold is the record answering; with none, the latest ruling.
    if not rulings:
        return None
    holds = [r for r in rulings if r.decision == "hold"]
    held = rulings[-1].decision == "escalate"
    return ArguePage(block=block, ruling=(holds or rulings)[-1], held=held)


def held_page(
    block: VerdictPage, rulings: list[RulingRecord], checks: list[SelfCheck]
) -> HeldPage | None:
    # Pure: the latest escalation, and what each other model it asked answered.
    escalated = [r for r in rulings if r.decision == "escalate"]
    if not escalated:
        return None
    ruling, answered = escalated[-1], any(r.decision == "hold" for r in rulings)
    second = second_answers(ruling, checks)
    return HeldPage(block=block, ruling=ruling, second=second, answered=answered)


def second_answers(ruling: RulingRecord, checks: list[SelfCheck]) -> list[SecondAnswer]:
    # The latest argue self-check on this receipt holds each model's verbatim answer.
    asked = [
        c for c in checks if c.trigger == "argue" and ruling.receipt_hash in c.source
    ]
    answers = {a.model: a.answer for check in asked for a in check.answers}
    others = [m.model for m in ruling.models if m.model != ruling.model]
    return [second_answer(model, answers.get(model)) for model in others]


def second_answer(model: str, text: str | None) -> SecondAnswer:
    said = said_json(text)
    words = {"decision": text_of(said, "decision"), "reply": text_of(said, "reply")}
    return SecondAnswer(model=model, **words)


def text_of(said: dict[str, Any], key: str) -> str | None:
    value = said.get(key)
    return value if isinstance(value, str) else None


def said_json(text: str | None) -> dict[str, Any]:
    # An answer that is not a JSON object reads as nothing said.
    try:
        return answer_json(text or "")
    except ValueError:
        return {}
