import re
from typing import Any, cast, Literal

import yaml
from pydantic import BaseModel, ConfigDict

from knack.contracts.models import Root
from knack.miss.cases import EditCase
from knack.receipts.chain import ChainReport, Decision, Receipt
from knack.roots.corrections import Correction

# The recovery page: one kept self-repair run, read as six steps. Pure: no files.
EditKind = Literal["evasion", "correct", "corrected"]
PASS = re.compile(r"^PASS (.+?)(?: \(/[^)]*\))?$", re.M)
ATTEMPTS = re.compile(r"\((\d+) attempt\(s\)\)")
EXIT = re.compile(r"^exit (\d+), wall", re.M)
PINNED = re.compile(r"^\S+: \S+ -> \S+, (pinned to rule \w+)( rolled back)?$", re.M)
# A rule check in plain words, by the syntax node it matches.
KIND_WORDS = {
    "dictionary_comprehension": "a dict comprehension",
    "pair": "a dict entry",
    "keyword_argument": "a keyword argument",
    "tuple": "a tuple",
    "string": "a string",
    "call": "a call",
}
# What each model call was for, by how its prompt opens.
ROLES = {
    "You compile": "recompiled the rule",
    "You write test cases": "wrote fresh test cases for a gate",
    "You are reading a merged pull request": "re-read the decided PRs for each confirm",
}
CLIENTS = {"SparkApi": "Spark", "SparkOpenApi": "Spark Open"}


class ModelCall(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow")

    step: str
    client: str
    model: str
    host: str
    trace_id: str
    prompt_head: str


class StepTrace(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    # The driver's step name, e.g. 05_05_knack_confirm, and its verbatim log.
    name: str
    text: str


class Repair(BaseModel):
    # One kept self-repair run, as read from its folder.
    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str
    before: Root
    after: Root
    v1: str
    v2: str
    cases: list[EditCase]
    receipts: list[Receipt]
    chain: ChainReport
    # Each receipt's edit snapshot, the file after the edit, by edit_sha256.
    snapshots: dict[str, str]
    corrected: str | None
    # The correct file's own name in the run, as the driver named it.
    proof_name: str | None
    calls: list[ModelCall]
    steps: list[StepTrace]
    confirm: Correction | None


class Edit(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    hash: str
    decision: Decision
    time: str
    # The line shown and its number; None when no receipt matched a line.
    line: int | None
    code: str | None


class Attempt(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    passed: bool
    # "pinned to rule 865e1a983ffe", and why the gate rolled it back, verbatim.
    pinned: str | None
    why: str | None
    exit: int | None
    calls: list[ModelCall]


class Role(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    # What a model's calls were for, and the trace id of each call.
    did: str
    traces: list[str]


class Worker(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    model: str
    host: str
    did: list[Role]


class RecoveryPage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str
    root: Root
    repo: str | None
    branch: str | None
    last: Receipt | None
    slipped: Edit | None
    false_block: Edit | None
    proof_name: str | None
    kept: int
    dropped: list[str]
    added: list[str]
    attempts: int | None
    compile_calls: list[ModelCall]
    gates: list[str]
    confirms: list[Attempt]
    confirmed_by: str | None
    denied: Edit | None
    allowed: Edit | None
    fixed: Edit | None
    chain: ChainReport
    v1_sha: str | None
    v2_sha: str | None
    workers: list[Worker]


def recovery_page(repair: Repair) -> RecoveryPage:
    # Pure: the recovery page's facts from one kept self-repair run.
    last = repair.receipts[-1] if repair.receipts else None
    found: dict[str, Any] = {"rule_id": repair.rule_id, "root": repair.after}
    found |= {"repo": last and last.repo, "branch": last and last.branch, "last": last}
    found |= edits(repair) | rule_change(repair) | repaired_by(repair)
    found |= {"confirms": confirms(repair), "chain": repair.chain}
    return RecoveryPage.model_validate(found | pins(repair))


def edits(repair: Repair) -> dict[str, Edit | str | None]:
    # First the misses, then the same edits once the rule was repaired.
    seen = {kind: of_kind(repair, kind) for kind in ("evasion", "correct", "corrected")}
    slipped = edit(repair, first(seen["evasion"]), last_deny(seen["evasion"]))
    false_block = edit(repair, first(seen["correct"]), first(seen["correct"]))
    later = {"denied": later_edit(repair, seen["evasion"])}
    later |= {"allowed": later_edit(repair, seen["correct"])}
    later |= {"fixed": edit(repair, first(seen["corrected"]), None)}
    return {"slipped": slipped, "false_block": false_block, **later}


def of_kind(repair: Repair, kind: EditKind) -> list[Receipt]:
    # The rule's receipts on one edit, told apart by the file each snapshot holds.
    wanted = edit_text(repair, kind)
    ours = [r for r in repair.receipts if r.rule_id == repair.rule_id]
    return [
        r
        for r in ours
        if wanted and repair.snapshots.get(r.edit_sha256 or "") == wanted
    ]


def edit_text(repair: Repair, kind: EditKind) -> str | None:
    if kind == "corrected":
        return repair.corrected
    wanted = "must-fail" if kind == "evasion" else "must-pass"
    return next((c.after for c in repair.cases if c.kind == wanted), None)


def first(receipts: list[Receipt]) -> Receipt | None:
    return receipts[0] if receipts else None


def last_deny(receipts: list[Receipt]) -> Receipt | None:
    # A later deny on the same edit names the line the earlier allow let through.
    return next((r for r in reversed(receipts) if r.decision == "deny"), None)


def later_edit(repair: Repair, receipts: list[Receipt]) -> Edit | None:
    later = receipts[-1] if len(receipts) > 1 else None
    return edit(repair, later, later if later and later.decision == "deny" else None)


def edit(repair: Repair, receipt: Receipt | None, lined: Receipt | None) -> Edit | None:
    # The receipt, and the edit's line its own or a later match names.
    if receipt is None:
        return None
    line = lined.matched[0].line if lined and lined.matched else None
    code = line_of(repair.snapshots.get(receipt.edit_sha256 or ""), line)
    found = {"hash": receipt.hash, "decision": receipt.decision, "time": receipt.time}
    return Edit.model_validate(found | {"line": line, "code": code})


def line_of(text: str | None, line: int | None) -> str | None:
    lines = (text or "").splitlines()
    return lines[line - 1] if line and 0 < line <= len(lines) else None


def rule_change(repair: Repair) -> dict[str, Any]:
    # v1's checks v2 kept verbatim, the ones it dropped, and the ones it added.
    old, new = checks(repair.v1), checks(repair.v2)
    dropped = [plain(c) for c in old if c not in new]
    added = [plain(c) for c in new if c not in old]
    kept = sum(c in new for c in old)
    return {"kept": kept, "dropped": dropped, "added": added, **recompiled(repair)}


def checks(rule: str) -> list[Any]:
    # The rule's top-level any: list, each item one check; unreadable YAML has none.
    try:
        found: Any = yaml.safe_load(rule)
    except yaml.YAMLError:
        return []
    return items(mapping(mapping(found).get("rule")).get("any"))


def mapping(value: Any) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def items(value: Any) -> list[Any]:
    return cast(list[Any], value) if isinstance(value, list) else []


def plain(check: Any) -> str:
    # A pattern is shown as written; any other check by the node it matches.
    found = mapping(check)
    if "pattern" in found:
        return f"`{found['pattern']}`"
    kinds = [
        str(mapping(p)["kind"]) for p in items(found.get("all")) if "kind" in mapping(p)
    ]
    return KIND_WORDS.get(kinds[0], kinds[0]) if kinds else "a check"


def recompiled(repair: Repair) -> dict[str, Any]:
    # The false-block step: its verbatim gate lines, attempts and model calls.
    log = step_text(repair, "false_block")
    tried = ATTEMPTS.search(log)
    calls = [c for c in repair.calls if c.step.endswith("false_block")]
    found = {"gates": PASS.findall(log), "compile_calls": calls}
    return found | {"attempts": int(tried.group(1)) if tried else None}


def step_text(repair: Repair, name: str) -> str:
    return next((s.text for s in repair.steps if s.name.endswith(name)), "")


def confirms(repair: Repair) -> list[Attempt]:
    # Every knack confirm the driver ran, in order, as its log ended.
    ran = [s for s in repair.steps if "knack_confirm" in s.name]
    return [attempt(s, calls_of(repair, s)) for s in ran]


def calls_of(repair: Repair, step: StepTrace) -> list[ModelCall]:
    # Step 05_05_knack_confirm logged its calls as 05_knack_confirm.
    short = step.name.split("_", 1)[1]
    return [c for c in repair.calls if c.step == short]


def attempt(step: StepTrace, calls: list[ModelCall]) -> Attempt:
    pinned, ran = PINNED.search(step.text), EXIT.search(step.text)
    exit = int(ran.group(1)) if ran else None
    why = rollback_reason(step.text) if pinned and pinned.group(2) else None
    passed = bool(pinned and not pinned.group(2) and exit == 0)
    said = {"pinned": pinned.group(1) if pinned else None, "why": why}
    return Attempt(passed=passed, exit=exit, calls=calls, **said)


def rollback_reason(text: str) -> str | None:
    # The gate's indented line under the rollback names what it lost.
    said = [line.strip() for line in text.splitlines() if line.startswith("  ")]
    return said[0] if said else None


def pins(repair: Repair) -> dict[str, str | None]:
    found = {"v1_sha": repair.before.rule_sha, "v2_sha": repair.after.rule_sha}
    return found | {"proof_name": repair.proof_name}


def repaired_by(repair: Repair) -> dict[str, Any]:
    # Each model by what its calls were for; the confirm's person by name.
    named = dict.fromkeys(c.model for c in repair.calls)
    workers = [worker(repair.calls, model) for model in named]
    return {"workers": workers, "confirmed_by": repair.confirm and repair.confirm.by}


def worker(calls: list[ModelCall], model: str) -> Worker:
    its = [c for c in calls if c.model == model]
    did: dict[str, list[str]] = {}
    for call in its:
        did.setdefault(role(call.prompt_head), []).append(call.trace_id)
    roles = [Role(did=said, traces=traces) for said, traces in did.items()]
    name = CLIENTS.get(its[0].client, its[0].client)
    return Worker(name=name, model=model, host=its[0].host, did=roles)


def role(prompt_head: str) -> str:
    found = (said for opens, said in ROLES.items() if prompt_head.startswith(opens))
    return next(found, "answered a prompt")
