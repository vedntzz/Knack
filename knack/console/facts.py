import difflib
import re
from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, ConfigDict

from knack.bench.heldout_pr import HeldOutPr, Score
from knack.bench.proof_grid import GATES, SIDE_GATES
from knack.console.verdict import RootView, VerdictView
from knack.contracts.models import HeldOutScore, Root, RuleProof, SideProof
from knack.day.models import CommitEvent, DayFeed, PullEvent, ReceiptEvent
from knack.day.when import moment
from knack.dispute.rulings import RulingRecord
from knack.miss.selfcheck import answer_json, SelfCheck
from knack.pipeline.prove import MIN_FLAGGED, MUST_FLAG
from knack.receipts.chain import (
    Decision,
    Receipt,
    Resolution,
    ResolutionAction,
    RESOLVED_VERBS,
)
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


# The day page: weeks of decisions as squares, the confirmed ones, and today.
WEEKS = 53
T = TypeVar("T")
TodayKind = Literal["commit", "pr", "block", "resolution"]


class GraphDay(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    date: str
    # Roots whose PR merged this day: Confirmed ones block, the rest advise only.
    confirmed: int
    advisory: int
    # Denies the guard made this day; a person's uphold is a resolution, not a block.
    blocks: int
    resolutions: list[ResolutionAction]
    prs: list[str]
    authors: list[str]
    # 0 empty, 1 advise only, 2 one confirmed, 3 confirmed among more.
    step: int


class Graph(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    repo: str | None
    today: str
    weeks: int
    # Every day from the Sunday WEEKS - 1 weeks back to today, oldest first.
    days: list[GraphDay]
    registry_error: str | None


class Memory(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    # The registry's repo, else the clone's; None when neither is known.
    repo: str | None
    # False when no registry guards the repo, so no decision count is known.
    known: bool
    roots: list[Root]
    # The repo's whole receipt chain, oldest first.
    chain: list[Receipt]
    now: datetime
    registry_error: str | None
    # Root id to the rule a kept self-repair run is for.
    repaired: dict[str, str] = {}


class DecisionLine(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    decision: str
    author: str
    pr: str | None
    url: str
    merged_on: str | None
    confirmed_by: str | None
    # The recovery page of the rule that keeps this decision, when a repair was kept.
    recovery: str | None = None


class ReceiptLine(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    hash: str
    time: str
    rule_id: str
    decision: Decision
    resolution: Resolution | None
    # The cited root's honest label; None when the root is not in the registry.
    root_status: str | None
    seeded: bool


class TodayLine(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    time: str
    kind: TodayKind
    what: str
    detail: str | None


class DayPage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    repo: str | None
    branch: str | None
    known: bool
    total: int
    confirmed: int
    graph: Graph
    decisions: list[DecisionLine]
    date: str
    # The clock's zone, which every time under today is shown in.
    zone: str | None
    today: list[TodayLine]
    last: ReceiptLine | None
    pulls_error: str | None
    registry_error: str | None


def day_page(memory: Memory, feed: DayFeed) -> DayPage:
    # Pure: the home page's facts from the registry, the chain and the day feed.
    roots = memory.roots
    confirmed = sum(root.status == "Confirmed" for root in roots)
    found: dict[str, Any] = {"repo": memory.repo, "branch": feed.branch}
    found |= {"known": memory.known, "total": len(roots), "confirmed": confirmed}
    found |= {"graph": graph(memory), "decisions": decision_lines(memory)}
    found |= {"today": today_lines(memory, feed), "last": last_receipt(memory)}
    return DayPage.model_validate(found | feed_facts(memory, feed))


def feed_facts(memory: Memory, feed: DayFeed) -> dict[str, Any]:
    # The day, the zone every time under today is shown in, and what could not be read.
    found = {"date": feed.date, "zone": memory.now.tzname()}
    return found | {
        "pulls_error": feed.pulls_error,
        "registry_error": memory.registry_error,
    }


def graph(memory: Memory) -> Graph:
    today = memory.now.date()
    merged = by_day(memory.roots, lambda root: root.merged_at, memory.now)
    receipted = by_day(memory.chain, lambda receipt: receipt.time, memory.now)
    days = [graph_day(d, merged.get(d, []), receipted.get(d, [])) for d in span(today)]
    found: dict[str, Any] = {"repo": memory.repo, "today": today.isoformat()}
    found |= {"weeks": WEEKS, "days": days, "registry_error": memory.registry_error}
    return Graph.model_validate(found)


def span(today: date) -> list[date]:
    # Columns start on Sunday, as GitHub's do; the last column ends today.
    start = today - timedelta(days=(today.weekday() + 1) % 7 + 7 * (WEEKS - 1))
    return [start + timedelta(days=n) for n in range((today - start).days + 1)]


def by_day(
    items: list[T], when: Callable[[T], str | None], now: datetime
) -> dict[date, list[T]]:
    # Each item under its calendar day in now's timezone; undated items are left out.
    found: dict[date, list[T]] = {}
    for item in items:
        at = moment(when(item) or "")
        if at is not None:
            found.setdefault(at.astimezone(now.tzinfo).date(), []).append(item)
    return found


def graph_day(day: date, roots: list[Root], receipts: list[Receipt]) -> GraphDay:
    confirmed = sum(root.status == "Confirmed" for root in roots)
    prs = unique(pr_of(str(root.source_url)) for root in roots)
    authors = unique(person(root.decided_by).author for root in roots)
    found: dict[str, Any] = {"confirmed": confirmed, "advisory": len(roots) - confirmed}
    found |= {"prs": prs, "authors": authors, "step": step(confirmed, len(roots))}
    found |= {"date": day.isoformat(), **receipt_counts(receipts)}
    return GraphDay.model_validate(found)


def receipt_counts(receipts: list[Receipt]) -> dict[str, Any]:
    blocks = sum(is_block(receipt) for receipt in receipts)
    settled = [r.resolution.action for r in receipts if r.resolution is not None]
    return {"blocks": blocks, "resolutions": settled}


def is_block(receipt: Receipt) -> bool:
    # The guard's own deny; an uphold records a deny but blocks nothing new.
    return receipt.decision == "deny" and receipt.resolution is None


def step(confirmed: int, total: int) -> int:
    # One meaning per step, so a confirmed day always reads a step above any other.
    if confirmed == 0:
        return min(total, 1)
    return 2 if total == 1 else 3


def unique(found: Any) -> list[str]:
    return list(dict.fromkeys(item for item in found if item))


def pr_of(url: str) -> str | None:
    found = re.search(r"/pull/(\d+)", url)
    return f"#{found.group(1)}" if found else None


def decision_lines(memory: Memory) -> list[DecisionLine]:
    # Confirmed roots only, the latest merge first; undated ones last.
    confirmed = [root for root in memory.roots if root.status == "Confirmed"]
    latest = sorted(confirmed, key=lambda root: root.merged_at or "", reverse=True)
    return [decision_line(root, memory.repaired.get(root.id)) for root in latest]


def decision_line(root: Root, repaired: str | None = None) -> DecisionLine:
    url = str(root.source_url)
    found = {"decision": root.decision, "author": person(root.decided_by).author}
    found |= {"pr": pr_of(url), "url": url, "merged_on": day_of(root.merged_at)}
    found |= {"recovery": f"/recovery/{repaired}" if repaired else None}
    return DecisionLine.model_validate(found | {"confirmed_by": root.confirmed_by})


def last_receipt(memory: Memory) -> ReceiptLine | None:
    if not memory.chain:
        return None
    last = memory.chain[-1]
    found: dict[str, Any] = {"hash": last.hash, "time": last.time}
    found |= {"rule_id": last.rule_id, "decision": last.decision}
    found |= {"resolution": last.resolution, **cited(memory.roots, last)}
    return ReceiptLine.model_validate(found)


def cited(roots: list[Root], receipt: Receipt) -> dict[str, Any]:
    # The cited root's honest label and seeded flag, as it reads in the registry now.
    root = next((r for r in roots if r.id in receipt.root_ids[:1]), None)
    return {"root_status": root and root.status, "seeded": bool(root and root.seeded)}


def today_lines(memory: Memory, feed: DayFeed) -> list[TodayLine]:
    # The feed's commits and PRs, and today's blocks and resolutions from the chain.
    work = [work_line(e) for e in feed.events if not isinstance(e, ReceiptEvent)]
    today = by_day(memory.chain, lambda r: r.time, memory.now).get(
        memory.now.date(), []
    )
    found = work + [line for line in map(receipt_today, today) if line]
    timed = sorted(found, key=lambda line: moment(line.time) or memory.now)
    return [in_zone(line, memory.now) for line in timed]


def in_zone(line: TodayLine, now: datetime) -> TodayLine:
    # One clock for the whole list: a commit's offset and a receipt's UTC both become now's.
    at = moment(line.time)
    return (
        line.model_copy(update={"time": at.astimezone(now.tzinfo).isoformat()})
        if at
        else line
    )


def work_line(event: CommitEvent | PullEvent) -> TodayLine:
    if isinstance(event, CommitEvent):
        detail = f"{event.author}, commit {event.sha[:8]}"
        return TodayLine(
            time=event.time, kind="commit", what=event.message, detail=detail
        )
    what = f"#{event.number} {event.title}"
    return TodayLine(time=event.time, kind="pr", what=what, detail=event.state)


def receipt_today(receipt: Receipt) -> TodayLine | None:
    # A block and a person's resolution are events; a plain allow is not.
    if receipt.resolution is not None:
        return resolution_line(receipt.time, receipt.resolution)
    if not is_block(receipt):
        return None
    against = receipt.root_ids[0] if receipt.root_ids else receipt.rule_id
    what = f"Blocked an edit against {against}"
    return TodayLine(time=receipt.time, kind="block", what=what, detail=None)


def resolution_line(time: str, resolution: Resolution) -> TodayLine:
    what = resolution_label(resolution)
    return TodayLine(time=time, kind="resolution", what=what, detail=resolution.reason)


def resolution_label(resolution: Resolution) -> str:
    # Each kind by its own verb: allowed, retired or upheld; never "learned".
    return f"{RESOLVED_VERBS[resolution.action].capitalize()} by {resolution.by}"
