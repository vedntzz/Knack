import re
from datetime import datetime
from html import escape
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

from knack.console.facts import (
    CodeLine,
    Figures,
    LineSpan,
    Person,
    verdict_page,
    VerdictPage,
)
from knack.console.render import EVENTS, page, partial, PRELOAD, SCRIPTS, wants_html
from knack.console.verdict import (
    deny_rulings,
    RegistryFor,
    RootView,
    verdict_view,
    VerdictView,
)
from knack.dispute.rulings import RulingRecord
from knack.receipts.chain import load_receipts
from knack.receipts.edits import edits_dir, EditSnapshot, load_edit

STATUS = {"deny": "Blocked", "allow": "Allowed", "guard-error": "Guard error"}
# Backticked spans in the human's words become code, as GitHub rendered them.
TICKED = re.compile(r"`([^`]+)`")
EDIT = "The agent’s edit"


def verdict_router(
    receipts: Path, warns: Path, rulings: Path, registry_for: RegistryFor
) -> APIRouter:
    # Files are read per request, so a deny or ruling made after start is found.
    router = APIRouter()
    _add_verdict(router, receipts, warns, registry_for)
    _add_rulings(router, receipts, rulings)
    return router


def _add_verdict(
    router: APIRouter, receipts: Path, warns: Path, registry_for: RegistryFor
) -> None:
    @router.get("/verdict/{receipt_hash}", response_model=VerdictView)
    def verdict(receipt_hash: str, request: Request) -> Response:
        view = verdict_view(receipt_hash, receipts, warns, registry_for)
        return _shown(view, receipts) if wants_html(request) else _json(view)


def _add_rulings(router: APIRouter, receipts: Path, rulings: Path) -> None:
    @router.get("/verdict/{receipt_hash}/rulings")
    def rulings_of(receipt_hash: str) -> list[RulingRecord]:
        return deny_rulings(receipt_hash, receipts, rulings)


def _shown(view: VerdictView, receipts: Path) -> HTMLResponse:
    snapshot = snapshot_of(receipts, view.hash)
    return HTMLResponse(verdict_html(verdict_page(view, snapshot), receipts))


def _json(view: VerdictView) -> JSONResponse:
    return JSONResponse(view.model_dump(mode="json"))


def snapshot_of(receipts: Path, wanted: str) -> EditSnapshot | None:
    # The edit snapshot the receipt line names, kept beside the receipts file.
    found = (r.edit_sha256 for r in load_receipts(receipts) if r.hash == wanted)
    digest = next(found, None)
    return load_edit(edits_dir(receipts), digest) if digest else None


def gap(label: str) -> str:
    # A missing field: its label and "not recorded", never an invented value.
    return f'<span class="gap">{escape(label)} not recorded</span>'


def lines_of(span: LineSpan) -> str:
    low, high = span
    return f"line {low}" if low == high else f"lines {low}–{high}"


def tail(path: str, parts: int = 3) -> str:
    return "/".join(path.split("/")[-parts:])


def stamp(time: str) -> str:
    try:
        moment = datetime.fromisoformat(time)
    except ValueError:
        return time
    return f"{moment:%b} {moment.day} {moment.year}, {moment:%H:%M:%S} UTC"


def verdict_html(found: VerdictPage, receipts: Path) -> str:
    view = found.view
    title = f"{STATUS[view.outcome]}: {tail(view.file)} · knack"
    frame = {"layout": "verdict", "state": view.outcome, "bar": bar(view)}
    frame |= {"preload": PRELOAD, "scripts": SCRIPTS, "events": EVENTS}
    parts = {"head": head(found), "board": board(found), "rail": rail(found)}
    shown = verify(view, shown_path(receipts))
    return page("verdict.html", escape(title), **frame, **parts, verify=shown)


def bar(view: VerdictView) -> str:
    branch = escape(view.branch) if view.branch else gap("Branch")
    where = f"{escape(view.repo)} <i>/</i> {branch} <i>/</i> <b>{escape(tail(view.file))}</b>"
    when = f"<code>{view.hash[:12]}</code> <time>{escape(stamp(view.time))}</time>"
    return f'<p class="where">{where}</p><p class="when">{when}</p>'


def head(found: VerdictPage) -> str:
    seal = f'<p class="seal" data-beat="seal">{STATUS[found.view.outcome]}</p>'
    title = f"<h1>{headline(found)}</h1>"
    return (
        f'{seal}<div class="claim">{title}<p class="stopped">{stopped(found)}</p></div>'
    )


def headline(found: VerdictPage) -> str:
    if not found.blocked:
        return f"This edit was {STATUS[found.view.outcome].lower()}."
    if found.pr is None:
        return f"This edit breaks rule {escape(found.view.rule_id)}."
    return f"This edit brings back what {escape(found.pr)} removed."


def stopped(found: VerdictPage) -> str:
    # The bar and the board already name the file; this line names the lines.
    file = escape(tail(found.view.file))
    span = lines_of(found.delete).capitalize() if found.delete else file
    after = " Stopped before it was written." if found.blocked else ""
    return f"{span}.{after}"


def board(found: VerdictPage) -> str:
    rows = code_rows(found) if found.code else f'<p class="lost">{gap(EDIT)}</p>'
    path = escape(tail(found.view.file, 6))
    return partial("code.html", edit=EDIT, path=path, rows=rows)


def code_rows(found: VerdictPage) -> str:
    # The note hangs under the last forbidden line, above the correct ones.
    code, marks = found.code or [], linked_names(found.view)
    last = max((c.number for c in code if c.kind == "hit"), default=0)
    rows = [
        code_row(c, marks) + (note(found) if c.number == last else "") for c in code
    ]
    return f'<div class="code">{"".join(rows)}</div>'


def code_row(line: CodeLine, marks: list[str]) -> str:
    sign = "+" if line.added else " "
    text = marked(line.text, marks) if line.kind == "hit" else escape(line.text)
    number = f'<span class="n">{line.number}</span><span class="sign">{sign}</span>'
    return f'<div class="line {line.kind}">{number}<code>{text}</code></div>'


def linked_names(view: VerdictView) -> list[str]:
    # The quote's code spans that the matched code spells: the gold link's two ends.
    ticked = TICKED.findall(view.root.quote) if view.root else []
    matched = " ".join(m.text for m in view.matched)
    found = [name for name in ticked if name in matched]
    return found or [max((m.text for m in view.matched), key=len, default="")]


def marked(text: str, names: list[str]) -> str:
    # Each linked name in a line is wrapped once, in gold.
    pattern = "|".join(re.escape(name) for name in names if name)
    if not pattern:
        return escape(text)
    parts = enumerate(re.split(f"({pattern})", text))
    return "".join(
        f"<mark>{escape(p)}</mark>" if i % 2 else escape(p) for i, p in parts
    )


def note(found: VerdictPage) -> str:
    root = found.view.root
    if root is None:
        return f'<figure class="note paper" data-beat="note">{gap("The decision")}</figure>'
    said = {"url": escape(root.source_url), "quote": quote(root, found.view)}
    said |= {"attribution": attribution(found, root), "offered": offered(root)}
    return partial("note.html", **said)


def quote(root: RootView, view: VerdictView) -> str:
    # The full verbatim quote; linked code spans carry the gold underline.
    linked = set(linked_names(view))
    parts = TICKED.split(root.quote)
    words = (
        code_span(p, p in linked) if i % 2 else escape(p) for i, p in enumerate(parts)
    )
    return "".join(words)


def code_span(name: str, linked: bool) -> str:
    code = f"<code>{escape(name)}</code>"
    return f"<mark>{code}</mark>" if linked else code


def attribution(found: VerdictPage, root: RootView) -> str:
    # Who wrote it, who merged it, when, and the PR, each a gap when missing.
    when = escape(found.merged_on) if found.merged_on else gap("Merge date")
    parts = [*people(found.person), when, pr_link(found.pr, root.source_url)]
    return " · ".join(part for part in parts if part)


def people(person: Person | None) -> list[str]:
    if person is None:
        return [gap("Decider")]
    merged = f"merged by {escape(person.merged_by)}" if person.merged_by else ""
    return [f"<b>{escape(person.author)}</b>", merged]


def pr_link(pr: str | None, url: str) -> str:
    return f'<a href="{escape(url)}">{escape(pr)}</a>' if pr else gap("PR")


def offered(root: RootView) -> str:
    if root.rejected_alternative is None:
        return f'<p class="offered">{gap("Rejected alternative")}</p>'
    return f'<p class="offered"><b>Offered, not taken:</b> {escape(root.rejected_alternative)}</p>'


def rail(found: VerdictPage) -> str:
    if not found.blocked:
        return ""
    return f'<aside class="rail">{fix(found)}{figures(found)}</aside>'


def fix(found: VerdictPage) -> str:
    todo = f"Delete {lines_of(found.delete)}." if found.delete else gap("Matched lines")
    kept = f"<p>{already_right(found.right)}</p>"
    pr = escape(found.pr or "the decision")
    return partial("fix.html", todo=todo, kept=kept, pr=pr)


def already_right(span: LineSpan | None) -> str:
    if span is None:
        return gap("Lines with the right names")
    return f"{lines_of(span).capitalize()} already use the right names."


def figures(found: VerdictPage) -> str:
    alarm = alarms(found.figures, found.view.repo)
    rows = [checks(found.figures), alarm, timing(found.view)]
    return partial("figures.html", rows="".join(rows))


def figure(number: str, unit: str, label: str) -> str:
    small = f"<small>{unit}</small>" if unit else ""
    big = f'<b><span data-count="{number}">{number}</span>{small}</b>'
    return f"<li>{big} <span>{label}</span></li>"


def checks(found: Figures | None) -> str:
    if found is None:
        return f"<li>{gap('Checks')}</li>"
    return figure(str(found.passed), f"/{found.gates}", "checks passed")


def alarms(found: Figures | None, repo: str) -> str:
    if found is None or found.false_alarms is None:
        return f"<li>{gap('False alarms')}</li>"
    name = escape(repo.split("/")[-1].capitalize())
    on = f" and release {escape(found.release)}" if found.release else ""
    return figure(str(found.false_alarms), "", f"false alarms on {name}’s code{on}")


def timing(view: VerdictView) -> str:
    latency = f"{view.latency_ms:.1f}"
    return figure(latency, " ms", "to decide, no AI model in the check")


def shown_path(receipts: Path) -> str:
    # The receipts file as a command run from here would name it.
    try:
        return str(receipts.relative_to(Path.cwd()))
    except ValueError:
        return str(receipts)


def verify(view: VerdictView, receipts: str) -> str:
    # The receipt, the command that checks it, and the rule, each copyable in full.
    command = f"knack receipts verify --path {receipts}"
    receipt = {"short": view.hash[:8], "copy_receipt": copy_button(view.hash)}
    check = {"command": escape(command), "copy_command": copy_button(command)}
    rule = {"rule": escape(view.rule_id), "label": decision_label(view.root)}
    return partial("verify.html", **receipt, **check, **rule)


def copy_button(text: str) -> str:
    named = f'data-copy-text="{escape(text)}" aria-live="polite"'
    return f'<button type="button" class="copy" {named}>Copy</button>'


def decision_label(root: RootView | None) -> str:
    # The root's honest status in plain words; seeded is said only when it is.
    if root is None:
        return gap("Decision")
    seeded = ", seeded" if root.seeded else ""
    return f"decision {escape(root.status.lower())}{seeded}"
