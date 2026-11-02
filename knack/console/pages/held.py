from html import escape
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from knack.console.facts import held_page, HeldPage, SecondAnswer
from knack.console.pages.argue import (
    answered,
    BEATS,
    block_page,
    blocked_lines,
    objection,
    quoted,
    ruled,
    ruled_as,
    ruled_frame,
    said,
    Slots,
)
from knack.console.pages.verdict import gap, note, partial, stamp, tail
from knack.console.render import page
from knack.console.verdict import RegistryFor, ResolutionView
from knack.dispute.latest import RESOLVE_HINT
from knack.dispute.rulings import RulingRecord, rulings_for
from knack.miss.selfcheck import load_checks, SELF_CHECKS, self_checks_path, SelfCheck

DONE = {"allow": "Allowed", "retire": "Retired", "uphold": "Upheld"}
RESOLVE = 'knack resolve {hash} {action} --reason "<why>"'
DONE_LINE = {
    "allow": "A person let the edit through.",
    "retire": "A person retired the decision.",
    "uphold": "A person upheld the decision.",
}


def held_router(
    receipts: Path, warns: Path, rulings: Path, registry_for: RegistryFor
) -> APIRouter:
    router = APIRouter()
    _add_held(router, receipts, warns, rulings, registry_for)
    return router


def _add_held(
    router: APIRouter,
    receipts: Path,
    warns: Path,
    rulings: Path,
    registry_for: RegistryFor,
) -> None:
    @router.get("/verdict/{receipt_hash}/held", response_class=HTMLResponse)
    def held(receipt_hash: str) -> HTMLResponse:
        block = block_page(receipt_hash, receipts, warns, registry_for)
        checks = self_checks_of(receipts, registry_for(block.view.repo))
        found = held_page(block, rulings_for(rulings, receipt_hash), checks)
        return HTMLResponse(held_html(ruled(found), receipts))


def self_checks_of(receipts: Path, registry: Path | None) -> list[SelfCheck]:
    # The registry's self-check log; kept receipts keep it under traces/, as one_story froze it.
    kept = receipts.parent / "traces" / SELF_CHECKS
    found = kept if kept.exists() else self_checks_path(registry) if registry else None
    return load_checks(found) if found else []


def held_html(found: HeldPage, receipts: Path) -> str:
    view = found.block.view
    title = f"Held: {escape(tail(view.file))} · knack"
    frame = ruled_frame(view, receipts, "argued held")
    return page("held.html", title, **frame, **held_parts(found))


def held_parts(found: HeldPage) -> Slots:
    block, ruling = found.block, found.ruling
    parts = {"lines": blocked_lines(block), "note": note(block, False)}
    parts |= {"objection": objection(ruling), "ruling": escalation(ruling)}
    parts |= {"seconds": "".join(map(second_card, found.second))}
    parts |= {"headline": held_headline(block.view.resolution), "back": back(found)}
    return parts | {"rail": held_rail(found)}


def held_headline(resolution: ResolutionView | None) -> str:
    # Held until a person settles it; then the page says what they did.
    return DONE_LINE[resolution.action] if resolution else "Held for a person."


def back(found: HeldPage) -> str:
    said = "What the record answered" if found.answered else "The argument"
    return f'<a href="/verdict/{found.block.view.hash}/argue">{said}</a>'


def escalation(ruling: RulingRecord) -> str:
    return said(ruled_as(ruling), quoted(ruling.reply), "ruling")


def second_card(second: SecondAnswer) -> str:
    # The other model, asked on its own, in its own words.
    model = f"<b>{escape(second.model)}</b>, asked separately,"
    if second.reply is None:
        return said(model, f"<p>{gap(f'{second.model}’s answer')}</p>", "answer")
    ruled_as = f" ruled <b>{escape(second.decision)}</b>" if second.decision else ""
    return said(model + ruled_as, quoted(second.reply), "answer")


def held_rail(found: HeldPage) -> str:
    resolution = found.block.view.resolution
    person = resolved(resolution) if resolution else to_resolve(found.block.view.hash)
    return f'{person}<div class="answer">{answered(found.ruling, found.block)}</div>'


def resolved(resolution: ResolutionView) -> str:
    # A person wrote this, so it is paper; the reason is theirs, verbatim.
    title = f"{DONE[resolution.action]} by {escape(resolution.by)}"
    reason = f"<blockquote><p>{escape(resolution.reason)}</p></blockquote>"
    receipt = f"receipt <code>{resolution.receipt_hash[:8]}</code>"
    at = f'<p class="at">{escape(stamp(resolution.time))}, {receipt}</p>'
    return partial(
        "resolved.html", title=title, said=reason + at, at=str(BEATS["person"])
    )


def to_resolve(receipt_hash: str) -> str:
    # The command as knack argue prints it; each button copies one runnable line.
    shown = RESOLVE_HINT.removeprefix("To resolve: ").format(hash=receipt_hash)
    buttons = "".join(copy_action(receipt_hash, action) for action in DONE)
    well = f'<div class="well"><code>{escape(shown, quote=False)}</code></div>'
    return partial("resolve.html", well=well, buttons=buttons, at=str(BEATS["person"]))


def copy_action(receipt_hash: str, action: str) -> str:
    command = escape(RESOLVE.format(hash=receipt_hash, action=action))
    named = f'data-copy-text="{command}" aria-live="polite"'
    return f'<button type="button" class="copy" {named}>Copy {action}</button>'
