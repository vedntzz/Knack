from datetime import date
from html import escape
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from knack.console.facts import (
    day_page,
    DayPage,
    DecisionLine,
    Graph,
    graph,
    GraphDay,
    Memory,
    ReceiptLine,
    resolution_label,
    TodayLine,
)
from knack.console.pages.verdict import (
    COMMAND,
    copy_button,
    gap,
    RECEIPT,
    shown_path,
    stamp,
    STATUS,
)
from knack.console.render import EVENTS, LIVE, page, partial, waiting_html
from knack.console.verdict import ReadRegistry, registry_at
from knack.contracts.models import Root
from knack.day.feed import day_feed
from knack.day.models import Day
from knack.day.receipts import same_repo
from knack.day.when import moment
from knack.git import origin_repo
from knack.receipts.chain import load_receipts
from knack.roots.store import load_roots, RootStoreError

STYLES = '<link rel="stylesheet" href="/static/day.css">\n'
SCRIPTS = LIVE + "".join(
    f'<script type="module" src="/static/{name}.js"></script>\n'
    for name in ("day", "console")
)
MARKS = {"block": "mark block", "resolution": "mark person"}
# The repo the registry names, its roots, and why they could not be read.
Remembered = tuple[str | None, list[Root] | None, str | None]


def day_router(receipts: Path, day: Day) -> APIRouter:
    # GET / is the repo's memory; GET /graph the per-day counts its squares show.
    router = APIRouter()
    router.get("/", response_class=HTMLResponse)(lambda: home(receipts, day))
    router.get("/graph", response_model=Graph)(lambda: graph_of(receipts, day))
    return router


def home(receipts: Path, day: Day) -> HTMLResponse:
    # A store the feed cannot read is never a 500: the page waits instead.
    try:
        found = day_page(memory(receipts, day), day_feed(day))
    except OSError:
        return HTMLResponse(waiting_html(), status_code=503)
    return HTMLResponse(day_html(found, receipts))


def graph_of(receipts: Path, day: Day) -> Graph:
    return graph(memory(receipts, day))


def memory(receipts: Path, day: Day) -> Memory:
    # The registry the console reads, its roots, and the repo's whole chain.
    repo, roots, error = remembered(day, origin_repo(day.clone))
    chain = [r for r in load_receipts(receipts) if repo and same_repo(r.repo, repo)]
    found = {"repo": repo, "known": roots is not None, "roots": roots or []}
    found |= {"chain": chain, "now": day.clock(), "registry_error": error}
    return Memory.model_validate(found)


def remembered(day: Day, clone_repo: str | None) -> Remembered:
    # The registry's repo and roots; roots are None when no registry could be read.
    registry, error = registry_of(day, clone_repo)
    if registry is None:
        return clone_repo, None, error
    roots, error = roots_of(registry.roots_dir)
    return registry.repo, None if error else roots, error


def registry_of(day: Day, repo: str | None) -> ReadRegistry:
    # Outside git or without an origin there is no repo to ask a registry for.
    return registry_at(day.registry_for(repo)) if repo else (None, None)


def roots_of(roots_dir: Path) -> tuple[list[Root], str | None]:
    try:
        return load_roots(roots_dir), None
    except (RootStoreError, OSError) as failed:
        return [], str(failed).splitlines()[0]


def day_html(found: DayPage, receipts: Path) -> str:
    title = f"{escape(found.repo or 'Day')} · knack"
    frame = {"layout": "day", "state": "home", "bar": bar(found), "styles": STYLES}
    frame |= {"scripts": SCRIPTS, "events": EVENTS, "verify": verify(found, receipts)}
    return page("day.html", title, **frame, **parts_of(found))


def parts_of(found: DayPage) -> dict[str, str]:
    parts = {"headline": headline(found), "sub": sub(found)}
    parts |= {"record": record(found), "decisions": decisions(found.decisions)}
    return parts | {"today": today(found)}


def bar(found: DayPage) -> str:
    branch = escape(found.branch) if found.branch else gap("Branch")
    repo = f"<b>{escape(found.repo)}</b>" if found.repo else gap("Repo")
    return f'<p class="where">{repo} <i>/</i> {branch}</p><p class="when">{last_seen(found.last)}</p>'


def last_seen(last: ReceiptLine | None) -> str:
    if last is None:
        return gap("Last receipt")
    said = f"<span>Last receipt: {escape(lowered(receipt_label(last)))}</span>"
    return (
        f"{said} <code>{last.hash[:12]}</code> <time>{escape(stamp(last.time))}</time>"
    )


def receipt_label(last: ReceiptLine) -> str:
    # A person's resolution by its kind; otherwise what the guard decided.
    return (
        resolution_label(last.resolution) if last.resolution else STATUS[last.decision]
    )


def lowered(label: str) -> str:
    return label[:1].lower() + label[1:]


def headline(found: DayPage) -> str:
    if not found.known:
        return gap("Decisions")
    repo = escape(found.repo or "This repo")
    return f'{repo} remembers <span class="nowrap">{plural(found.total, "decision")}</span>.'


def sub(found: DayPage) -> str:
    if not found.known:
        return escape(found.registry_error or "No registry guards this repo.")
    advisory = found.total - found.confirmed
    return f"{found.confirmed} confirmed to block · {advisory} advise only"


def plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def record(found: DayPage) -> str:
    shown = found.graph
    slots = {"counts": counts(shown) + undated(found), "months": months(shown.days)}
    return partial("graph.html", **slots, weeks=weeks(shown), legend=LEGEND)


def counts(found: Graph) -> str:
    # What happened over the squares; the decisions are already counted above.
    blocks = sum(d.blocks for d in found.days)
    settled = sum(len(d.resolutions) for d in found.days)
    events = f"<b>{plural(blocks, 'block')}</b>, {settled} resolved by a person"
    return f"In {found.weeks} weeks: {events}."


def undated(found: DayPage) -> str:
    # A decision with no merge day in the span has no square; say so, never drop it.
    shown = sum(d.confirmed + d.advisory for d in found.graph.days)
    missing = found.total - shown if found.known else 0
    return f" {gap(plural(missing, 'merge date'))}" if missing else ""


LEGEND = (
    '<li><span class="swatch s1"></span>advise only</li>'
    '<li><span class="swatch s2"></span>one confirmed</li>'
    '<li><span class="swatch s3"></span>confirmed among more</li>'
    '<li><span class="mark block"></span>a block</li>'
    '<li><span class="mark person"></span>a person resolved one</li>'
)


def months(days: list[GraphDay]) -> str:
    # One slot a week; a month's name sits over the week its first day falls in.
    columns = [days[n : n + 7] for n in range(0, len(days), 7)]
    return "".join(f"<span>{month_of(week)}</span>" for week in columns)


def month_of(week: list[GraphDay]) -> str:
    first = next((d for d in week if d.date.endswith("-01")), None)
    return f"{date.fromisoformat(first.date):%b}" if first else ""


def weeks(found: Graph) -> str:
    columns = [found.days[n : n + 7] for n in range(0, len(found.days), 7)]
    cells = ("".join(cell(d, d.date == found.today) for d in week) for week in columns)
    return "".join(f'<div class="week">{week}</div>' for week in cells)


def cell(day: GraphDay, today: bool) -> str:
    stop = "0" if today else "-1"
    said = f'role="img" tabindex="{stop}" aria-label="{escape(tip(day))}"'
    return f'<span class="cell s{day.step}" data-date="{day.date}" {said}>{marks(day)}</span>'


def marks(day: GraphDay) -> str:
    block = '<span class="mark block"></span>' if day.blocks else ""
    person = '<span class="mark person"></span>' if day.resolutions else ""
    return block + person


def tip(day: GraphDay) -> str:
    # date · count · PR · author, then the day's blocks and resolutions.
    count = day.confirmed + day.advisory
    said = [day_name(day.date), plural(count, "decision") if count else "no decisions"]
    said += [", ".join(day.prs), ", ".join(day.authors)] if count else []
    said += [plural(day.blocks, "block")] if day.blocks else []
    said += [RESOLVED[action] for action in day.resolutions]
    return " · ".join(part for part in said if part)


RESOLVED = {
    "allow": "allowed by a person",
    "retire": "retired by a person",
    "uphold": "upheld by a person",
}


def day_name(iso: str) -> str:
    on = date.fromisoformat(iso)
    return f"{on:%b} {on.day} {on.year}"


def decisions(lines: list[DecisionLine]) -> str:
    if not lines:
        return f"<p>{gap('Confirmed decisions')}</p>"
    return f'<ul class="notes">{"".join(map(decision, lines))}</ul>'


def decision(line: DecisionLine) -> str:
    pr = f'<a href="{escape(line.url)}">{escape(line.pr)}</a>' if line.pr else gap("PR")
    merged = f"merged {escape(line.merged_on)}" if line.merged_on else gap("Merge date")
    by = line.confirmed_by
    confirmed = f"confirmed by {escape(by)}" if by else gap("Confirmer")
    who = f"<b>{escape(line.author)}</b> · {pr} · {merged} · {confirmed}"
    return partial("decision.html", decision=escape(line.decision), who=who)


def today(found: DayPage) -> str:
    zone = f' <span class="zone">{escape(found.zone)}</span>' if found.zone else ""
    title = f"Today, {day_name(found.date)}{zone}"
    lines = [today_line(line) for line in found.today] + pulls_gap(found.pulls_error)
    shown = "".join(lines) or "<li><p>Nothing yet today.</p></li>"
    return f'<h2 id="today">{title}</h2><ol class="events">{shown}</ol>'


def pulls_gap(error: str | None) -> list[str]:
    return (
        [f"<li><span></span><p>{gap('Pull requests')}: {escape(error)}</p></li>"]
        if error
        else []
    )


def today_line(line: TodayLine) -> str:
    mark = f'<span class="{MARKS[line.kind]}"></span>' if line.kind in MARKS else ""
    detail = f" <span>{escape(line.detail)}</span>" if line.detail else ""
    return f"<li>{clock(line.time)}<p>{mark}{escape(line.what)}{detail}</p></li>"


def clock(time: str) -> str:
    at = moment(time)
    shown = f"{at:%H:%M:%S}" if at else escape(time)
    return f'<time datetime="{escape(time)}">{shown}</time>'


def verify(found: DayPage, receipts: Path) -> str:
    # The last receipt and the command that checks the chain, each copyable in full.
    command = f"knack receipts verify --path {shown_path(receipts)}"
    last = found.last
    if last is None:
        return unreceipted(command)
    said = {"short": last.hash[:8], "copy_receipt": copy_button(last.hash, RECEIPT)}
    said |= {"command": escape(command), "copy_command": copy_button(command, COMMAND)}
    return partial("verify.html", **said, rule=escape(last.rule_id), label=label(last))


def unreceipted(command: str) -> str:
    # No receipt yet: the gap, and the command still checks the empty chain.
    said = f"<p>{gap('Last receipt')}</p><p><code>{escape(command)}</code>{copy_button(command, COMMAND)}</p>"
    return f'<section class="verify" aria-labelledby="verify"><h2 id="verify">Verify it</h2>{said}</section>'


def label(last: ReceiptLine) -> str:
    if last.root_status is None:
        return gap("Decision")
    seeded = ", seeded" if last.seeded else ""
    return f"decision {escape(last.root_status.lower())}{seeded}"
