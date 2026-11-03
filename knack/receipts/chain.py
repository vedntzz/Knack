import fcntl
import hashlib
import json
import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, BinaryIO, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from knack.contracts.models import MatchedCode, Root, Verdict
from knack.guard.check import GUARD_ERROR_REASON
from knack.home import knack_home

JsonDict = dict[str, Any]
Decision = Literal["allow", "deny", "guard-error"]
# The prev of the first receipt.
GENESIS = "0" * 64
# Enough of the file's end to hold its last receipt whole.
TAIL_BYTES = 64 * 1024
PREV_BROKEN = "prev does not match the hash of the line before"
HASH_BROKEN = "hash does not match the record"
# The file holds no whole receipt to chain on: never extended from a guess.
NO_WHOLE_RECEIPT = "no whole receipt in the chain to extend"
# Fields added after the first receipts: left off the line, and the hash, when unset.
LATER_FIELDS = ("branch", "session_id", "matched", "edit_sha256", "resolution", "agent")
# What a person decided about a deny after ESCALATE: allow that edit, retire, or uphold the decision.
ResolutionAction = Literal["allow", "retire", "uphold"]
# How a settled deny reads: "<hash>: <verb> by <person>".
RESOLVED_VERBS: dict[ResolutionAction, str] = {
    "allow": "allowed",
    "retire": "retired",
    "uphold": "upheld",
}


class Resolution(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    # The hash of the deny receipt this resolves.
    of: str
    action: ResolutionAction
    by: str
    reason: str


class Receipt(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    time: str
    repo: str
    file: str
    rule_id: str
    root_ids: list[str]
    decision: Decision
    # SHA-256 of the cited root's quote; None when no root was on record.
    quote_sha256: str | None
    latency_ms: float
    # The previous line's hash, so an edit, deletion or reorder breaks the chain.
    prev: str
    hash: str
    # The clone's branch, the agent session and the new matches, when known.
    branch: str | None = None
    session_id: str | None = None
    matched: list[MatchedCode] | None = None
    # The saved snapshot of the edit this verdict was on, under <knack home>/edits.
    edit_sha256: str | None = None
    # Set only on the receipt knack resolve appends.
    resolution: Resolution | None = None
    # The coding agent the PreToolUse payload named, when it named one.
    agent: str | None = None


class ChainReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    # Receipts that verified before the break, or all of them.
    receipts: int
    broken_line: int | None = None
    problem: str | None = None


def receipts_path() -> Path:
    return knack_home() / "verdicts.jsonl"


def guard_receipt(
    repo: str,
    file: str,
    rule_id: str,
    root: Root | None,
    verdict: Verdict,
    time: str,
    branch: str | None = None,
    session_id: str | None = None,
    edit_sha256: str | None = None,
    agent: str | None = None,
) -> JsonDict:
    # The receipt's fields before chaining: the consulted root, hashed quote, outcome.
    roots = [root.id] if root else []
    quote = _sha256(root.quote) if root else None
    named = {"time": time, "repo": repo, "file": file, "rule_id": rule_id}
    decided = {"decision": decision_of(verdict), "latency_ms": verdict.latency_ms}
    kept = _set_later_fields(verdict, branch, session_id, edit_sha256, agent)
    return named | decided | {"root_ids": roots, "quote_sha256": quote} | kept


def decision_of(verdict: Verdict) -> Decision:
    if not verdict.allowed:
        return "deny"
    failed = verdict.reason.startswith(GUARD_ERROR_REASON)
    return "guard-error" if failed else "allow"


def resolution_receipt(deny: Receipt, resolution: Resolution, time: str) -> JsonDict:
    # The deny's fields, decided by a person; session and agent were the agent's.
    dropped = {"prev", "hash", "session_id", "agent"}
    kept = deny.model_dump(mode="json", exclude=dropped)
    outcome = "deny" if resolution.action == "uphold" else "allow"
    decided = {"decision": outcome, "latency_ms": 0.0, "time": time}
    return kept | decided | {"resolution": resolution.model_dump()}


class SettledError(Exception):
    pass


def settled_by(chain: list[Receipt], deny_hash: str) -> Resolution | None:
    # The one rule for "is this deny settled": its first resolution wins; None while open.
    found = (r.resolution for r in chain if r.resolution)
    return next((r for r in found if r.of == deny_hash), None)


def resolution_of(receipts: Path, deny_hash: str) -> Resolution | None:
    return settled_by(load_receipts(receipts), deny_hash)


def human_allow(receipts: Path, rule_id: str, edit_sha256: str) -> Resolution | None:
    # A person allowed this exact edit, and that allow is what settled its deny.
    chain = load_receipts(receipts)
    allowed = [r.resolution for r in chain if _allows(r, rule_id, edit_sha256)]
    settling = [a for a in allowed if a and settled_by(chain, a.of) == a]
    return settling[-1] if settling else None


def append_receipt(path: Path, fields: JsonDict) -> Receipt:
    # The lock spans read-last-hash and append, so parallel hooks never fork the chain.
    with _locked(path) as handle:
        return _append_locked(handle, fields)


def append_resolution(
    path: Path, deny: Receipt, resolution: Resolution, time: str
) -> Receipt:
    # Settled-or-open is re-read under the chain lock, so one deny is settled once.
    with _locked(path) as handle:
        _refuse_settled(load_receipts(path), deny.hash)
        return _append_locked(handle, resolution_receipt(deny, resolution, time))


def _refuse_settled(chain: list[Receipt], deny_hash: str) -> None:
    done = settled_by(chain, deny_hash)
    if done is not None:
        raise SettledError(f"{deny_hash} already resolved: {done.action} by {done.by}")


def _append_locked(handle: BinaryIO, fields: JsonDict) -> Receipt:
    receipt = _chained(fields, _last_hash(handle))
    line = fresh_line(handle) + receipt_line(receipt) + "\n"
    handle.write(line.encode("utf-8"))
    return receipt


def receipt_line(receipt: Receipt) -> str:
    # The body that was hashed, plus the hash.
    line = _hashed_body(receipt) | {"hash": receipt.hash}
    return json.dumps(line, separators=(",", ":"), ensure_ascii=False)


def receipt_hash(receipt: Receipt) -> str:
    # SHA-256 of sorted-key compact JSON of every field on the line but hash.
    body = _hashed_body(receipt)
    text = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return _sha256(text)


def _hashed_body(receipt: Receipt) -> JsonDict:
    # Unset later fields are absent, so older receipts hash as they always did.
    unset = {name for name in LATER_FIELDS if getattr(receipt, name) is None}
    return receipt.model_dump(mode="json", exclude={"hash"} | unset)


def load_receipts(path: Path) -> list[Receipt]:
    # A missing file has no receipts; a torn or foreign line is skipped.
    return [receipt for receipt in map(_receipt_or_none, _lines(path)) if receipt]


def verify_chain(path: Path) -> ChainReport:
    prev, count = GENESIS, 0
    for count, line in enumerate(_lines(path), 1):
        problem = _link_problem(line, prev)
        if problem is not None:
            return ChainReport(receipts=count - 1, broken_line=count, problem=problem)
        prev = Receipt.model_validate_json(line).hash
    return ChainReport(receipts=count)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _chained(fields: JsonDict, prev: str) -> Receipt:
    unhashed = Receipt.model_validate(fields | {"prev": prev, "hash": ""})
    return unhashed.model_copy(update={"hash": receipt_hash(unhashed)})


@contextmanager
def _locked(path: Path) -> Generator[BinaryIO, None, None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield handle


def _last_hash(handle: BinaryIO) -> str:
    # The last whole receipt; a torn line after it is skipped, and verify names it.
    found = _last_receipt(handle, TAIL_BYTES) or _last_receipt(handle, None)
    if found is None and handle.seek(0, os.SEEK_END):
        raise ValueError(NO_WHOLE_RECEIPT)
    return found.hash if found else GENESIS


def _last_receipt(handle: BinaryIO, limit: int | None) -> Receipt | None:
    # The tail, or the whole file when one receipt outgrows the tail; bad bytes read as U+FFFD.
    size = handle.seek(0, os.SEEK_END)
    handle.seek(max(0, size - limit) if limit else 0)
    lines = handle.read().decode("utf-8", errors="replace").splitlines()
    return next(filter(None, map(_receipt_or_none, reversed(lines))), None)


def fresh_line(handle: BinaryIO) -> str:
    # A torn last line has no newline; the next receipt starts a line of its own.
    size = handle.seek(0, os.SEEK_END)
    if size == 0:
        return ""
    handle.seek(size - 1)
    return "" if handle.read(1) == b"\n" else "\n"


def _lines(path: Path) -> list[str]:
    # A missing file is an empty chain; a line cut mid-character reads as U+FFFD, never raises.
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def _link_problem(line: str, prev: str) -> str | None:
    receipt = _receipt_or_none(line)
    if receipt is None:
        return "not a receipt"
    # The first failing check, prev before hash, names the break.
    failed = [(PREV_BROKEN, receipt.prev != prev)]
    failed += [(HASH_BROKEN, receipt.hash != receipt_hash(receipt))]
    return next((problem for problem, broken in failed if broken), None)


def _allows(receipt: Receipt, rule_id: str, edit_sha256: str) -> bool:
    resolution = receipt.resolution
    if resolution is None or resolution.action != "allow":
        return False
    return (receipt.rule_id, receipt.edit_sha256) == (rule_id, edit_sha256)


def _receipt_or_none(line: str) -> Receipt | None:
    try:
        return Receipt.model_validate_json(line)
    except ValidationError:
        return None


def _set_later_fields(
    verdict: Verdict,
    branch: str | None,
    session_id: str | None,
    edit_sha256: str | None,
    agent: str | None,
) -> JsonDict:
    # Unset later fields stay off the line, so older receipts hash as they did.
    matched = [m.model_dump() for m in verdict.matched] or None
    later = {"branch": branch, "session_id": session_id, "matched": matched}
    later |= {"edit_sha256": edit_sha256, "agent": agent}
    return {key: value for key, value in later.items() if value is not None}
