import fcntl
import hashlib
import json
import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, BinaryIO, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from knack.contracts.models import Root, Verdict
from knack.guard.check import GUARD_ERROR_REASON

JsonDict = dict[str, Any]
Decision = Literal["allow", "deny", "guard-error"]
# The prev of the first receipt.
GENESIS = "0" * 64
# Enough of the file's end to hold its last receipt whole.
TAIL_BYTES = 64 * 1024
PREV_BROKEN = "prev does not match the hash of the line before"
HASH_BROKEN = "hash does not match the record"


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


class ChainReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    # Receipts that verified before the break, or all of them.
    receipts: int
    broken_line: int | None = None
    problem: str | None = None


def receipts_path() -> Path:
    return Path.home() / ".knack" / "verdicts.jsonl"


def guard_receipt(
    repo: str, file: str, rule_id: str, root: Root | None, verdict: Verdict, time: str
) -> JsonDict:
    # The receipt's fields before chaining: the consulted root, hashed quote, outcome.
    roots = [root.id] if root else []
    quote = _sha256(root.quote) if root else None
    named = {"time": time, "repo": repo, "file": file, "rule_id": rule_id}
    decided = {"decision": decision_of(verdict), "latency_ms": verdict.latency_ms}
    return named | decided | {"root_ids": roots, "quote_sha256": quote}


def decision_of(verdict: Verdict) -> Decision:
    if not verdict.allowed:
        return "deny"
    failed = verdict.reason.startswith(GUARD_ERROR_REASON)
    return "guard-error" if failed else "allow"


def append_receipt(path: Path, fields: JsonDict) -> Receipt:
    # The lock spans read-last-hash and append, so parallel hooks never fork the chain.
    with _locked(path) as handle:
        receipt = _chained(fields, _last_hash(handle))
        handle.write((receipt.model_dump_json() + "\n").encode("utf-8"))
    return receipt


def receipt_hash(receipt: Receipt) -> str:
    # SHA-256 of sorted-key compact JSON of every field but hash.
    body = receipt.model_dump(mode="json", exclude={"hash"})
    text = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return _sha256(text)


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


def _receipt_or_none(line: str) -> Receipt | None:
    try:
        return Receipt.model_validate_json(line)
    except ValidationError:
        return None
