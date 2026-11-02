import re
from datetime import datetime
from html import escape
from pathlib import Path
from string import Template

from knack.console.facts import CodeLine, Figures, LineSpan, Person, VerdictPage
from knack.console.verdict import RootView, VerdictView

TEMPLATES = Path(__file__).parent / "templates"
STATUS = {"deny": "Blocked", "allow": "Allowed", "guard-error": "Guard error"}
# Backticked spans in the human's words become code, as GitHub rendered them.
TICKED = re.compile(r"`([^`]+)`")
EDIT = "The agent’s edit"


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


def render(name: str, **slots: str) -> str:
    return Template((TEMPLATES / name).read_text(encoding="utf-8")).substitute(slots)


def verdict_html(page: VerdictPage, receipts: Path) -> str:
    view = page.view
    title = f"{STATUS[view.outcome]}: {tail(view.file)} · knack"
    slots = {"title": escape(title), "state": view.outcome, "bar": bar(view)}
    slots |= {"head": head(page), "board": board(page), "rail": rail(page)}
    return render("verdict.html", **slots, verify=verify(view, shown_path(receipts)))


def waiting_html() -> str:
    return render("waiting.html")


def missing_html() -> str:
    return render("missing.html")


def bar(view: VerdictView) -> str:
    branch = escape(view.branch) if view.branch else gap("Branch")
    where = f"{escape(view.repo)} <i>/</i> {branch} <i>/</i> <b>{escape(tail(view.file))}</b>"
    when = f"<code>{view.hash[:12]}</code> <time>{escape(stamp(view.time))}</time>"
    return f'<p class="where">{where}</p><p class="when">{when}</p>'


def head(page: VerdictPage) -> str:
    seal = f'<p class="seal" data-beat="seal">{STATUS[page.view.outcome]}</p>'
    title = f"<h1>{headline(page)}</h1>"
    return (
        f'{seal}<div class="claim">{title}<p class="stopped">{stopped(page)}</p></div>'
    )


def headline(page: VerdictPage) -> str:
    if not page.blocked:
        return f"This edit was {STATUS[page.view.outcome].lower()}."
    if page.pr is None:
        return f"This edit breaks rule {escape(page.view.rule_id)}."
    return f"This edit brings back what {escape(page.pr)} removed."


def stopped(page: VerdictPage) -> str:
    # The bar and the board already name the file; this line names the lines.
    span = (
        lines_of(page.delete).capitalize()
        if page.delete
        else escape(tail(page.view.file))
    )
    after = " Stopped before it was written." if page.blocked else ""
    return f"{span}.{after}"


def board(page: VerdictPage) -> str:
    path = f'<p class="path"><code>{escape(tail(page.view.file, 6))}</code></p>'
    lost = f'<p class="lost">{gap(EDIT)}</p>'
    rows = code_rows(page) if page.code else lost
    return f'<section class="board" aria-label="{EDIT}">{path}{rows}</section>'


def code_rows(page: VerdictPage) -> str:
    # The note hangs under the last forbidden line, above the correct ones.
    code, marks = page.code or [], linked_names(page.view)
    last = max((c.number for c in code if c.kind == "hit"), default=0)
    rows = [code_row(c, marks) + (note(page) if c.number == last else "") for c in code]
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
    parts = re.split(f"({pattern})", text)
    return "".join(
        f"<mark>{escape(p)}</mark>" if i % 2 else escape(p) for i, p in enumerate(parts)
    )


def note(page: VerdictPage) -> str:
    root = page.view.root
    if root is None:
        return f'<figure class="note paper" data-beat="note">{gap("The decision")}</figure>'
    said = f'<blockquote cite="{escape(root.source_url)}">{quote(root, page.view)}</blockquote>'
    caption = f"<figcaption>{attribution(page, root)}</figcaption>"
    return f'<figure class="note paper" data-beat="note">{said}{caption}{offered(root)}</figure>'


def quote(root: RootView, view: VerdictView) -> str:
    # The full verbatim quote; linked code spans carry the gold underline.
    linked = set(linked_names(view))
    parts = TICKED.split(root.quote)
    words = [
        code_span(p, p in linked) if i % 2 else escape(p) for i, p in enumerate(parts)
    ]
    return f"<p>“{''.join(words)}”</p>"


def code_span(name: str, linked: bool) -> str:
    code = f"<code>{escape(name)}</code>"
    return f"<mark>{code}</mark>" if linked else code


def attribution(page: VerdictPage, root: RootView) -> str:
    # Who wrote it, who merged it, when, and the PR, each a gap when missing.
    when = escape(page.merged_on) if page.merged_on else gap("Merge date")
    parts = [*people(page.person), when, pr_link(page.pr, root.source_url)]
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


def rail(page: VerdictPage) -> str:
    if not page.blocked:
        return ""
    return f'<aside class="rail">{fix(page)}{figures(page)}</aside>'


def fix(page: VerdictPage) -> str:
    todo = f"Delete {lines_of(page.delete)}." if page.delete else gap("Matched lines")
    kept = f"<p>{already_right(page.right)}</p>"
    pr = escape(page.pr or "the decision")
    return render("fix.html", todo=todo, kept=kept, pr=pr)


def already_right(span: LineSpan | None) -> str:
    if span is None:
        return gap("Lines with the right names")
    return f"{lines_of(span).capitalize()} already use the right names."


def figures(page: VerdictPage) -> str:
    rows = [
        checks(page.figures),
        alarms(page.figures, page.view.repo),
        timing(page.view),
    ]
    return f'<ul class="figures" data-beat="figures">{"".join(rows)}</ul>'


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
    return figure(
        f"{view.latency_ms:.1f}", "\u2009ms", "to decide, no AI model in the check"
    )


def shown_path(receipts: Path) -> str:
    # The receipts file as a command run from here would name it.
    try:
        return str(receipts.relative_to(Path.cwd()))
    except ValueError:
        return str(receipts)


def verify(view: VerdictView, receipts: str) -> str:
    # The receipt, the command that checks it, and the rule, each copyable in full.
    command = f"knack receipts verify --path {receipts}"
    receipt = (
        f"<span>Receipt <code>{view.hash[:8]}</code></span>{copy_button(view.hash)}"
    )
    check = f"<code>{escape(command)}</code>{copy_button(command)}"
    rule = f"Rule {escape(view.rule_id)} · {decision_label(view.root)}"
    return f"<p>{receipt}</p><p>{check}</p><p>{rule}</p>"


def copy_button(text: str) -> str:
    named = f'data-copy-text="{escape(text)}" aria-live="polite"'
    return f'<button type="button" class="copy" {named}>Copy</button>'


def decision_label(root: RootView | None) -> str:
    # The root's honest status in plain words; seeded is said only when it is.
    if root is None:
        return gap("Decision")
    seeded = ", seeded" if root.seeded else ""
    return f"decision {escape(root.status.lower())}{seeded}"
