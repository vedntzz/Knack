import re
from html import escape
from pathlib import Path
from typing import TypeVar

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from knack.console.facts import (
    argue_page,
    ArguePage,
    LineSpan,
    verdict_page,
    VerdictPage,
)
from knack.console.pages.verdict import (
    bar,
    code_row,
    fix_lines,
    gap,
    lines_of,
    linked_names,
    note,
    partial,
    shown_path,
    snapshot_of,
    tail,
    verify,
)
from knack.console.render import page, PRELOAD, TURNS
from knack.console.verdict import (
    NO_RULING,
    NoSuchRuling,
    RegistryFor,
    verdict_view,
    VerdictView,
)
from knack.contracts.models import NOT_RECORDED
from knack.dispute.rulings import RulingRecord, rulings_for
from knack.receipts.chain import RESOLVED_VERBS

TICKED = re.compile(r"`([^`]+)`")
WORD = {"hold": "Hold", "escalate": "Escalate"}
# Beats in ms from load: one card rises per beat, then the page is still.
BEATS = {"objection": 160, "ruling": 760, "answer": 1360, "person": 1960}
Found = TypeVar("Found")
Slots = dict[str, str]


def argue_router(
    receipts: Path, warns: Path, rulings: Path, registry_for: RegistryFor
) -> APIRouter:
    # Read per request, so a ruling written after start is found.
    router = APIRouter()
    _add_argue(router, receipts, warns, rulings, registry_for)
    return router


def _add_argue(
    router: APIRouter,
    receipts: Path,
    warns: Path,
    rulings: Path,
    registry_for: RegistryFor,
) -> None:
    @router.get("/verdict/{receipt_hash}/argue", response_class=HTMLResponse)
    def argue(receipt_hash: str) -> HTMLResponse:
        block = block_page(receipt_hash, receipts, warns, registry_for)
        found = ruled(argue_page(block, rulings_for(rulings, receipt_hash)))
        return HTMLResponse(argue_html(found, receipts))


def block_page(
    wanted: str, receipts: Path, warns: Path, registry_for: RegistryFor
) -> VerdictPage:
    # The block page's own facts; an unknown hash raises the 404.
    view = verdict_view(wanted, receipts, warns, registry_for)
    return verdict_page(view, snapshot_of(receipts, view.hash))


def ruled(found: Found | None) -> Found:
    if found is None:
        raise NoSuchRuling(NO_RULING)
    return found


def argue_html(found: ArguePage, receipts: Path) -> str:
    view = found.block.view
    title = f"Argued: {escape(tail(view.file))} · knack"
    return page(
        "argue.html", title, **ruled_frame(view, receipts), **argue_parts(found)
    )


def ruled_frame(view: VerdictView, receipts: Path, layout: str = "argued") -> Slots:
    # Both ruling pages: the bar, the faces, the beats and the verify row; no deny listener.
    frame = {"layout": layout, "state": "ruled", "bar": bar(view)}
    frame |= {"preload": PRELOAD, "scripts": TURNS}
    return frame | {"verify": verify(view, shown_path(receipts))}


def argue_parts(found: ArguePage) -> Slots:
    block, ruling = found.block, found.ruling
    parts = {"lines": blocked_lines(block), "note": note(block, False)}
    parts |= {"objection": objection(ruling), "ruling": ruling_card(ruling, found)}
    return parts | {"headline": argued_headline(ruling), "rail": argue_rail(found)}


def blocked_lines(block: VerdictPage) -> str:
    # Only the matched lines, gold as on the block page; the bar already names the file.
    hits = [c for c in block.code or [] if c.kind == "hit"]
    rows = "".join(code_row(c, linked_names(block.view)) for c in hits)
    lost = f'<p class="lost">{gap("The blocked lines")}</p>'
    shown = f'<div class="code">{rows}</div>' if rows else lost
    return f'<section class="board" aria-label="The blocked lines">{shown}</section>'


def ticked(text: str) -> str:
    # Backticked spans in recorded words become code, as the note renders them.
    parts = TICKED.split(text)
    return "".join(
        f"<code>{escape(p)}</code>" if i % 2 else escape(p) for i, p in enumerate(parts)
    )


def said(who: str, body: str, beat: str) -> str:
    return partial("said.html", who=who, body=body, at=str(BEATS[beat]))


def quoted(text: str) -> str:
    return f"<blockquote><p>“{ticked(text)}”</p></blockquote>"


def objection(ruling: RulingRecord) -> str:
    # Labelled with the agent the deny's payload named, never guessed.
    named = ruling.agent != NOT_RECORDED
    agent = f"The agent, <b>{escape(ruling.agent)}</b>, objected" if named else ""
    agent = agent or f"The agent objected. {gap('Agent')}"
    return said(agent, quoted(ruling.objection), "objection")


def ruling_card(ruling: RulingRecord, found: ArguePage) -> str:
    who = f"{ruled_as(ruling)}{citing(ruling, found.block)}"
    slips = "".join(
        f'<blockquote class="slip paper"><p>“{ticked(q)}”</p></blockquote>'
        for q in ruling.cited_quotes
    )
    return said(who, slips + reply_unless_cited(ruling), "ruling")


def ruled_as(ruling: RulingRecord) -> str:
    return f"{model_name(ruling.model)} ruled <b>{escape(ruling.decision)}</b>"


def model_name(model: str | None) -> str:
    return f"<b>{escape(model)}</b>" if model else gap("Model")


def citing(ruling: RulingRecord, block: VerdictPage) -> str:
    if not ruling.cited_quotes:
        return ", citing no quote."
    return f", citing {escape(block.pr or 'the decision')}:"


def reply_unless_cited(ruling: RulingRecord) -> str:
    # A reply that is word for word a cited quote is read once, on its slip.
    if ruling.reply in ruling.cited_quotes:
        return ""
    return f'<p class="reply">{ticked(ruling.reply)}</p>'


def argued_headline(ruling: RulingRecord) -> str:
    if ruling.decision == "hold":
        return "The agent objected. The record answered."
    return "The agent objected. A person will decide."


def argue_rail(found: ArguePage) -> str:
    word = f'<h2 id="outcome" class="word">{WORD[found.ruling.decision]}</h2>'
    then = f"{word}<p>{consequence(found)}</p>{later_held(found)}"
    outcome = f'<section class="outcome" aria-labelledby="outcome">{then}</section>'
    by = answered(found.ruling, found.block)
    answer = f'<div class="answer" data-at="{BEATS["answer"]}">{outcome}{by}</div>'
    return answer + fix_card(found)


def consequence(found: ArguePage) -> str:
    # What the ruling means for the edit; an escalation leads to its held page.
    if found.ruling.decision == "escalate":
        return f'<a href="{held_href(found)}">Held for a person</a>.'
    return f"{stays(found.block.delete)} blocked."


def stays(delete: LineSpan | None) -> str:
    return f"{lines_of(delete).capitalize()} stay" if delete else "The edit stays"


def later_held(found: ArguePage) -> str:
    # A hold shown here while a later objection escalated: say so and link it.
    if not found.held or found.ruling.decision == "escalate":
        return ""
    link = f'<a href="{held_href(found)}">held for a person</a>'
    return f'<p class="next">A later objection was {link}{settled(found)}.</p>'


def settled(found: ArguePage) -> str:
    resolution = found.block.view.resolution
    return f", who {RESOLVED_VERBS[resolution.action]} it" if resolution else ""


def fix_card(found: ArguePage) -> str:
    # A hold leaves the block page's instruction standing; the page ends on it.
    if found.ruling.decision != "hold":
        return ""
    todo, kept = fix_lines(found.block)
    head = f'aria-labelledby="fix" data-at="{BEATS["person"]}"'
    return f'<section class="fix" {head}><h2 id="fix">{todo}</h2>{kept}</section>'


def held_href(found: ArguePage) -> str:
    return f"/verdict/{found.block.view.hash}/held"


def answered(ruling: RulingRecord, block: VerdictPage) -> str:
    # Every model the ruling names, in the order asked; the block itself ran none.
    rows = "".join(model_row(m.model, m.host, ruling.timed_out) for m in ruling.models)
    ran = f"The block itself ran no model: {block.view.latency_ms:.1f} ms to decide."
    return partial(
        "answered.html", models=rows or f"<li>{gap('Models')}</li>", block=ran
    )


def model_row(model: str, host: str, timed_out: list[str]) -> str:
    where = gap("Host") if host == NOT_RECORDED else f"at {escape(host)}"
    late = ", gave no answer in time" if model in timed_out else ""
    return f"<li><b>{escape(model)}</b> <span>{where}{late}</span></li>"
