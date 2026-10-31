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

JsonDict = dict[str, Any]
Decision = Literal["allow", "deny", "guard-error"]
# The prev of the first receipt.
GENESIS = "0" * 64
# Enough of the file's end to hold its last receipt whole.
TAIL_BYTES = 64 * 1024
PREV_BROKEN = "prev does not match the hash of the line before"
HASH_BROKEN = "hash does not match the record"
# Fields added after the first receipts: left off the line, and the hash, when unset.
LATER_FIELDS = ("branch", "session_id", "matched", "edit_sha256", "resolution")
# What a person decided about a deny after ESCALATE: let that edit through, or retire the decision.
ResolutionAction = Literal["allow", "retire"]


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
    # The saved snapshot of the edit this verdict was on, under ~/.knack/edits.
    edit_sha256: str | None = None
    # Set only on the receipt knack resolve appends.
    resolution: Resolution | None = None


class ChainReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    # Receipts that verified before the break, or all of them.
    receipts: int
    broken_line: int | None = None
    problem: str | None = None


def receipts_path() -> Path:
    return Path.home() / ".knack" / "verdicts.jsonl"


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
) -> JsonDict:
    # The receipt's fields before chaining: the consulted root, hashed quote, outcome.
    roots = [root.id] if root else []
    quote = _sha256(root.quote) if root else None
    named = {"time": time, "repo": repo, "file": file, "rule_id": rule_id}
    decided = {"decision": decision_of(verdict), "latency_ms": verdict.latency_ms}
    kept = _set_later_fields(verdict, branch, session_id, edit_sha256)
    return named | decided | {"root_ids": roots, "quote_sha256": quote} | kept


def decision_of(verdict: Verdict) -> Decision:
    if not verdict.allowed:
        return "deny"
    failed = verdict.reason.startswith(GUARD_ERROR_REASON)
    return "guard-error" if failed else "allow"


def resolution_receipt(deny: Receipt, resolution: Resolution, time: str) -> JsonDict:
    # The deny's fields, now an allow by a person; the session was the agent's, not theirs.
    kept = deny.model_dump(mode="json", exclude={"prev", "hash", "session_id"})
    decided = {"decision": "allow", "latency_ms": 0.0, "time": time}
    return kept | decided | {"resolution": resolution.model_dump()}


def resolution_of(receipts: Path, deny_hash: str) -> Resolution | None:
    found = (r.resolution for r in load_receipts(receipts) if r.resolution)
    return next((r for r in found if r.of == deny_hash), None)


def human_allow(receipts: Path, rule_id: str, edit_sha256: str) -> Resolution | None:
    # A person allowed this exact edit under this rule; a retire allows nothing by edit.
    allowed = [r for r in load_receipts(receipts) if _allows(r, rule_id, edit_sha256)]
    return allowed[-1].resolution if allowed else None


def append_receipt(path: Path, fields: JsonDict) -> Receipt:
    # The lock spans read-last-hash and append, so parallel hooks never fork the chain.
    with _locked(path) as handle:
        receipt = _chained(fields, _last_hash(handle))
        handle.write((receipt_line(receipt) + "\n").encode("utf-8"))
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
    # A torn or foreign last line raises: the chain is never extended from a guess.
    size = handle.seek(0, os.SEEK_END)
    handle.seek(max(0, size - TAIL_BYTES))
    tail = handle.read().splitlines()
    return Receipt.model_validate_json(tail[-1]).hash if tail else GENESIS


def _lines(path: Path) -> list[str]:
    # A missing file is an empty chain; any other read failure propagates.
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8").splitlines()


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
) -> JsonDict:
    # Unset later fields stay off the line, so older receipts hash as they did.
    matched = [m.model_dump() for m in verdict.matched] or None
    later = {"branch": branch, "session_id": session_id, "matched": matched}
    later |= {"edit_sha256": edit_sha256}
    return {key: value for key, value in later.items() if value is not None}
