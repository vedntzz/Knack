import json
import re
from html import escape
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pydantic import ValidationError

from knack.console.pages.verdict import COMMAND, copy_button, gap, shown_path, stamp
from knack.console.render import page
from knack.console.repair_facts import (
    Attempt,
    Edit,
    ModelCall,
    recovery_page,
    RecoveryPage,
    Repair,
    StepTrace,
    Worker,
)
from knack.console.verdict import NoSuchReceipt
from knack.contracts.models import Root
from knack.miss.cases import EditCase
from knack.receipts.chain import load_receipts, verify_chain
from knack.receipts.edits import EditSnapshot
from knack.roots.corrections import Correction

STYLES = '<link rel="stylesheet" href="/static/recovery.css">\n'
SCRIPTS = '<script type="module" src="/static/recovery.js"></script>\n'
# The driver names the correct file it replays, e.g. COMPLIANT_3 = … "compliant_3.py".
PROOF_NAME = re.compile(r'^COMPLIANT_\w+ = .*"([^"/]+\.py)"$', re.M)
NOTE = "Started by a person; the unattended repair path has run only with fake models."
SHORT = 8
PASS_BOTH = "The correct file and the corrected edit both pass."
PIN = 12


class NoSuchRepair(NoSuchReceipt):
    # No kept self-repair run is for that rule.
    pass


def recovery_router(repairs: Path | None) -> APIRouter:
    # Read per request from the kept run's folder; no folder means no recovery page.
    router = APIRouter()
    _add_recovery(router, repairs)
    return router


def _add_recovery(router: APIRouter, repairs: Path | None) -> None:
    @router.get("/recovery/{rule_id}", response_class=HTMLResponse)
    def recovery(rule_id: str) -> HTMLResponse:
        return HTMLResponse(recovery_html(kept_repair(repairs, rule_id), repairs))


def kept_repair(repairs: Path | None, rule_id: str) -> RecoveryPage:
    repair = load_repair(repairs) if repairs else None
    if repair is None or repair.rule_id != rule_id:
        raise NoSuchRepair(f"no kept repair for {rule_id}")
    return recovery_page(repair)


def repaired_roots(repairs: Path | None) -> dict[str, str]:
    # Root id to the rule its kept repair is for, so the day page can link it.
    repair = load_repair(repairs) if repairs else None
    return {repair.after.id: repair.rule_id} if repair else {}


def load_repair(folder: Path) -> Repair | None:
    # A folder missing its rule, roots or cases holds no repair; never a 500.
    try:
        return Repair.model_validate(read_run(folder))
    except (OSError, ValueError, ValidationError, StopIteration):
        return None


def read_run(folder: Path) -> dict[str, object]:
    # The rule before and after, then what the run logged.
    found = kept_rule(folder) | kept_receipts(folder)
    found |= {"calls": calls(folder), "steps": steps(folder)}
    found |= {"corrected": corrected(folder), "proof_name": proof_name(folder)}
    return found | {"confirm": confirm(folder)}


def kept_rule(folder: Path) -> dict[str, object]:
    # The cases name the rule; the roots and the two rule files are its versions.
    cases = list(map(case_at, sorted(folder.glob("cases/*.json"))))
    found: dict[str, object] = {"rule_id": cases[0].rule_id, "cases": cases}
    found |= {name: root_at(folder, name) for name in ("before", "after")}
    return found | {v: (folder / "rule" / f"{v}.yml").read_text() for v in ("v1", "v2")}


def case_at(path: Path) -> EditCase:
    return EditCase.model_validate_json(path.read_text(encoding="utf-8"))


def root_at(folder: Path, name: str) -> Root:
    return Root.model_validate_json((folder / "rule" / f"root_{name}.json").read_text())


def kept_receipts(folder: Path) -> dict[str, object]:
    path = folder / "receipts.jsonl"
    found: dict[str, object] = {"receipts": load_receipts(path)}
    found |= {"chain": verify_chain(path)}
    return found | {"snapshots": snapshots(folder / "traces" / "receipt_edits")}


def snapshots(folder: Path) -> dict[str, str]:
    read = {
        p.stem: EditSnapshot.model_validate_json(p.read_text())
        for p in folder.glob("*.json")
    }
    return {digest: snapshot.after for digest, snapshot in read.items()}


def json_lines(path: Path) -> list[dict[str, object]]:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    return [json.loads(line) for line in lines if line.strip()]


def calls(folder: Path) -> list[ModelCall]:
    return [
        ModelCall.model_validate(line) for line in json_lines(folder / "models.jsonl")
    ]


def steps(folder: Path) -> list[StepTrace]:
    found = sorted((folder / "traces" / "steps").glob("*.txt"))
    return [StepTrace(name=p.stem, text=p.read_text(encoding="utf-8")) for p in found]


def corrected(folder: Path) -> str | None:
    path = folder / "edits" / "corrected.after.py"
    return path.read_text(encoding="utf-8") if path.exists() else None


def proof_name(folder: Path) -> str | None:
    texts = (
        p.read_text(encoding="utf-8") for p in sorted(folder.glob("driver/*/steps.py"))
    )
    named = (PROOF_NAME.search(text) for text in texts)
    return next((found.group(1) for found in named if found), None)


def confirm(folder: Path) -> Correction | None:
    # The confirm that stayed; a rolled-back confirm leaves no line.
    found = [
        Correction.model_validate(c) for c in json_lines(folder / "corrections.jsonl")
    ]
    return next((c for c in reversed(found) if c.action == "confirm"), None)


def recovery_html(found: RecoveryPage, folder: Path | None) -> str:
    title = f"Recovery: {escape(found.rule_id)} · knack"
    receipts = (folder or Path()) / "receipts.jsonl"
    frame = {"layout": "recovery", "state": "repaired", "bar": bar(found)}
    frame |= {"styles": STYLES, "scripts": SCRIPTS}
    parts = {"sub": sub(found), "steps": "".join(timeline(found))}
    return page("recovery.html", title, **frame, **parts, rail=rail(found, receipts))


def bar(found: RecoveryPage) -> str:
    repo = escape(found.repo) if found.repo else gap("Repo")
    branch = escape(found.branch) if found.branch else gap("Branch")
    where = f"{repo} <i>/</i> {branch} <i>/</i> <b>rule {escape(found.rule_id)}</b>"
    return f'<p class="where">{where}</p><p class="when">{last_seen(found)}</p>'


def last_seen(found: RecoveryPage) -> str:
    last = found.last
    if last is None:
        return gap("Last receipt")
    return f"<code>{last.hash[:PIN]}</code> <time>{escape(stamp(last.time))}</time>"


def sub(found: RecoveryPage) -> str:
    # Whose decision the rule keeps, by its honest label.
    root, url = found.root, escape(str(found.root.source_url))
    pr = re.search(r"/pull/(\d+)", url)
    link = f'<a href="{url}">#{pr.group(1)}</a>' if pr else gap("PR")
    return f"It keeps {link}’s decision · {escape(root.status)}, {seeded(root)}"


def seeded(root: Root) -> str:
    return "seeded" if root.seeded else "not seeded"


def timeline(found: RecoveryPage) -> list[str]:
    # The six steps, in the order they ran.
    return [shown(found) for shown in STEPS]


def step(title: str, meta: str, body: str) -> str:
    # The step's title and, on the same line, the receipt that proves it.
    said = f'<p class="meta">{meta}</p>' if meta else ""
    return (
        f'<li class="step"><div class="title"><h2>{title}</h2>{said}</div>{body}</li>'
    )


def receipt(edit: Edit | None, word: str, label: str) -> str:
    # The decision, the receipt's short hash and the second it was written.
    if edit is None:
        return gap(label)
    hashed = f"receipt <code>{edit.hash[:SHORT]}</code> · {clock(edit.time)}"
    return f'<span class="decided">{word}</span> · <span class="nowrap">{hashed}</span>'


def clock(time: str) -> str:
    at = stamp(time).split(", ")[-1]
    return f'<time datetime="{escape(time)}">{escape(at)}</time>'


def code(edit: Edit | None) -> str:
    if edit is None or edit.code is None:
        return f'<p class="line">{gap("The edit’s line")}</p>'
    number, text = f'<span class="n">{edit.line}</span>', escape(edit.code.strip())
    return f'<p class="line">{number}<code title="{text}">{text}</code></p>'


def slipped(found: RecoveryPage) -> str:
    meta = receipt(found.slipped, "Allowed", "The allow receipt")
    return step("An edit slipped past the rule.", meta, code(found.slipped))


def false_block(found: RecoveryPage) -> str:
    edit = found.false_block
    name = escape(found.proof_name) if found.proof_name else gap("File name")
    said = f"<figcaption><b>{name}</b></figcaption>"
    proof = f'<figure class="proof paper">{said}{code(edit)}</figure>'
    meta = receipt(edit, "Denied", "The deny receipt")
    return step("Spark Open’s test found the rule blocking correct code.", meta, proof)


def recompiled(found: RecoveryPage) -> str:
    out = f"Dropped: {listed(found.dropped)}, the one proven wrong."
    new = f"Added: {listed(found.added)}."
    body = f"<p>{counts(found)}{tries(found)} {out} {new}</p>"
    return step("Spark recompiled the rule.", "", body + called(found.compile_calls))


def counts(found: RecoveryPage) -> str:
    kept, dropped, added = found.kept, len(found.dropped), len(found.added)
    return (
        f"Kept {kept} checks that were still right, dropped {dropped}, added {added}."
    )


def tries(found: RecoveryPage) -> str:
    return f" Installed after {found.attempts} attempts." if found.attempts else ""


def listed(words: list[str]) -> str:
    # Patterns as code, other checks in words, joined as a sentence.
    shown = [ticked(w) for w in words] or [gap("Checks")]
    last = shown.pop()
    return f"{', '.join(shown)} and {last}" if shown else last


def ticked(word: str) -> str:
    if word.startswith("`") and word.endswith("`"):
        return f"<code>{escape(word[1:-1])}</code>"
    return escape(word)


def called(calls: list[ModelCall]) -> str:
    # Each model once, with its host and every trace id it answered under.
    if not calls:
        return f"<p>{gap('Model calls')}</p>"
    models = dict.fromkeys(c.model for c in calls)
    return (
        f'<p class="calls">By {"; ".join(model_traces(calls, m) for m in models)}.</p>'
    )


def model_traces(calls: list[ModelCall], model: str) -> str:
    # Each call's trace id is beside its model under Who did the work.
    its = [c for c in calls if c.model == model]
    return (
        f"<b>{escape(model)}</b> at {escape(its[0].host)}, {plural(len(its), 'call')}"
    )


def plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def traced(ids: list[str]) -> str:
    return ", ".join(f"<code>{escape(i)}</code>" for i in ids)


def gated(found: RecoveryPage) -> str:
    rows = "".join(f"<li>{gate_line(g)}</li>" for g in found.gates)
    shown = f'<ul class="gates">{rows}</ul>' if rows else f"<p>{gap('Gate lines')}</p>"
    return step("Every gate passed.", "", shown)


def gate_line(line: str) -> str:
    # The gate's name, then its verbatim result.
    name, _, result = line.partition(": ")
    return f"<b>{escape(name)}:</b> {escape(result)}" if result else escape(line)


def reconfirmed(found: RecoveryPage) -> str:
    named = found.confirmed_by
    by = f"by <b>{escape(named)}</b>" if named else gap("Confirmer")
    tried = "".join(map(confirm_line, found.confirms)) or f"<p>{gap('Confirm')}</p>"
    return step(f"A person re-confirmed it, {by}.", "", tried)


def confirm_line(tried: Attempt) -> str:
    if tried.passed:
        return f"<p>Second attempt passed, {escape(tried.pinned or '')}.</p>"
    why = f": <q>{ticked_spans(tried.why)}</q>" if tried.why else ""
    return f"<p>First attempt rolled back by the regression gate, exit {tried.exit}{why}.</p>"


def ticked_spans(text: str) -> str:
    # The gate's verbatim words; its backticked spans render as code.
    parts = enumerate(re.split(r"`([^`]+)`", text))
    return "".join(
        f"<code>{escape(p)}</code>" if i % 2 else escape(p) for i, p in parts
    )


def held(found: RecoveryPage) -> str:
    # The peak: the evasion blocked; then the right code passing, and the chain.
    blocked = '<b class="blocked">Blocked</b> the evasion'
    denied = receipt(found.denied, blocked, "The evasion’s deny")
    shown = f"<p>{passes(found.allowed, found.fixed)}</p><p>{chained(found)}</p>"
    return step("The same evasion is now denied.", denied, shown)


def passes(allowed: Edit | None, fixed: Edit | None) -> str:
    # Outcome first, then the two allow receipts that prove it.
    if allowed is None or fixed is None:
        return gap("The correct file’s and the corrected edit’s allows")
    hashes = (
        f"<code>{allowed.hash[:SHORT]}</code> and <code>{fixed.hash[:SHORT]}</code>"
    )
    proof = f'<span class="nowrap">receipts {hashes} · {clock(fixed.time)}</span>'
    return f"<b>{PASS_BOTH}</b> {proof}"


def chained(found: RecoveryPage) -> str:
    chain = found.chain
    if chain.broken_line is None:
        return f"{chain.receipts} receipts, chain intact."
    return f"{chain.receipts} receipts, chain broken at line {chain.broken_line}."


def rail(found: RecoveryPage, receipts: Path) -> str:
    v1, v2 = pin(found.v1_sha, "v1"), pin(found.v2_sha, "v2")
    rule = f'<section class="pins" aria-labelledby="pins"><h2 id="pins">The rule</h2><p>v1 {v1} → v2 {v2}</p></section>'
    return rule + who(found) + f'<p class="plain">{NOTE}</p>' + verify(receipts)


def pin(sha: str | None, label: str) -> str:
    return f"<code>{escape(sha[:PIN])}</code>" if sha else gap(label)


def who(found: RecoveryPage) -> str:
    rows = [worker_row(w) for w in found.workers]
    rows += ["<li><b>Plain code</b>, no model: ran every gate and decided it.</li>"]
    rows += [person_row(found.confirmed_by)]
    heading = '<h2 id="who">Who did the work</h2>'
    return f'<section class="by" aria-labelledby="who">{heading}<ul>{"".join(rows)}</ul></section>'


def worker_row(worker: Worker) -> str:
    # The model, then each thing it did with the trace id of every call.
    named = f"<b>{escape(worker.name)}</b>, {escape(worker.model)} at {escape(worker.host)}:"
    did = "; ".join(f"{escape(r.did)}, {traced(r.traces)}" for r in worker.did)
    return f"<li>{named} {did}.</li>"


def person_row(by: str | None) -> str:
    named = escape(by) if by else gap("Confirmer")
    return f"<li><b>A person</b>, {named}: started the repair and confirmed it.</li>"


def verify(receipts: Path) -> str:
    # The command that checks the kept run's whole chain, copyable in full.
    command = f"knack receipts verify --path {shown_path(receipts)}"
    shown = f'<p>{copy_button(command, COMMAND)}<code title="{escape(command)}">{escape(command)}</code></p>'
    return f'<section class="verify" aria-labelledby="verify"><h2 id="verify">Verify it</h2>{shown}</section>'


STEPS = (slipped, false_block, recompiled, gated, reconfirmed, held)
