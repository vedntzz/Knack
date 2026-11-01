import hashlib
import os
from collections.abc import Callable
from datetime import datetime, UTC
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from knack.contracts.models import MatchedCode, Root, RuleProof
from knack.dispute.rulings import RulingRecord, rulings_for
from knack.hooks.pretool_guard import rule_name
from knack.hooks.scope import REGISTRY_ENV
from knack.receipts.chain import (
    Decision,
    load_receipts,
    Receipt,
    receipt_hash,
    ResolutionAction,
)
from knack.receipts.warns import load_warns, WarnRecord
from knack.roots.store import load_roots
from knack.walk.registry import home_registry_dir, load_registry, Registry

# The registry file that guards a repo, or None when it has none.
RegistryFor = Callable[[str], Path | None]
NO_RECEIPT = "no receipt with that hash"
TimedWarn = tuple[datetime, WarnRecord]
# What reading the registry yields: it, or None and why when it could not be read.
ReadRegistry = tuple[Registry | None, str | None]


class RootView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    status: str
    decision: str
    decided_by: str
    why: str
    quote: str
    source_url: str
    rejected_alternative: str | None
    # When the cited PR merged; None for a root stored before merge times were kept.
    merged_at: str | None
    # How long before (or after) this verdict the cited PR merged; None without merged_at.
    postmark: str | None
    # False when the root's quote changed since the receipt hashed it.
    quote_verified: bool
    seeded: bool
    # Who confirmed it and the sha256 of the rule they confirmed; None before KN-62.
    confirmed_by: str | None
    rule_sha: str | None


class OtherDecision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    hash: str
    time: str
    file: str
    outcome: Decision
    latency_ms: float


class WarnView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    time: str
    context: str
    # False when the warn came from another session in the clone, e.g. a replayed deny.
    same_session: bool


class ResolutionView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    # The deny settled, how, by whom and why, and the allow receipt that records it.
    of: str
    action: ResolutionAction
    by: str
    reason: str
    receipt_hash: str
    time: str


class VerdictView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    hash: str
    # False when the line no longer hashes to its own hash.
    hash_verified: bool
    time: str
    repo: str
    branch: str | None
    file: str
    rule_id: str
    outcome: Decision
    latency_ms: float
    # One entry per line range; the receipt itself keeps every match.
    matched: list[MatchedCode]
    root: RootView | None
    # What the rule was proven on at install; None when none was stored.
    proof: RuleProof | None
    other_decisions: list[OtherDecision]
    warn: WarnView | None
    # How a person settled this deny with knack resolve; None while unresolved.
    resolution: ResolutionView | None
    # Why the registry could not be read, so root and proof are None; None when it was.
    registry_error: str | None


class NoSuchReceipt(Exception):
    pass


def verdict_view(
    wanted: str, receipts: Path, warns: Path, registry_for: RegistryFor
) -> VerdictView:
    chain = load_receipts(receipts)
    receipt = _receipt_in(chain, wanted)
    registry, registry_error = _registry_of(receipt, registry_for)
    return VerdictView(
        hash=receipt.hash,
        hash_verified=receipt_hash(receipt) == receipt.hash,
        time=receipt.time,
        repo=receipt.repo,
        branch=receipt.branch,
        file=receipt.file,
        rule_id=receipt.rule_id,
        outcome=receipt.decision,
        latency_ms=receipt.latency_ms,
        matched=_one_per_line_range(receipt.matched or []),
        root=_root_view(receipt, registry),
        proof=_proof_of(receipt, registry),
        other_decisions=_others_on_branch(receipt, chain),
        warn=_warn_before(receipt, load_warns(warns)),
        resolution=_resolution_of(receipt, chain),
        registry_error=registry_error,
    )


def deny_rulings(wanted: str, receipts: Path, rulings: Path) -> list[RulingRecord]:
    # An unknown hash is 404, never an empty list that looks like "never argued".
    _receipt_in(load_receipts(receipts), wanted)
    return rulings_for(rulings, wanted)


def home_registry_for(repo: str) -> Path | None:
    # The registry the hook guards with: KNACK_REGISTRY, else the repo's home one.
    value = os.environ.get(REGISTRY_ENV)
    if value:
        return Path(value).expanduser().resolve()
    path = home_registry_dir(repo) / "registry.json"
    return path if path.exists() else None


def _receipt_in(chain: list[Receipt], wanted: str) -> Receipt:
    receipt = next((r for r in chain if r.hash == wanted), None)
    if receipt is None:
        raise NoSuchReceipt(NO_RECEIPT)
    return receipt


def _root_view(receipt: Receipt, registry: Registry | None) -> RootView | None:
    # The root as it reads now; quote_verified says if it still reads as receipted.
    root = _cited_root(receipt, registry)
    if root is None:
        return None
    quote = hashlib.sha256(root.quote.encode("utf-8")).hexdigest()
    return RootView(
        id=root.id,
        status=root.status,
        decision=root.decision,
        decided_by=root.decided_by,
        why=root.why,
        quote=root.quote,
        source_url=str(root.source_url),
        rejected_alternative=root.rejected_alternative,
        merged_at=root.merged_at,
        postmark=_postmark(root.merged_at, receipt.time),
        quote_verified=quote == receipt.quote_sha256,
        seeded=root.seeded,
        confirmed_by=root.confirmed_by,
        rule_sha=root.rule_sha,
    )


def _postmark(merged_at: str | None, verdict_time: str) -> str | None:
    # Calendar days in UTC, so a PR merged before the edit visibly predates it.
    merged, decided = _parsed(merged_at or ""), _parsed(verdict_time)
    if merged is None or decided is None:
        return None
    days = (decided.astimezone(UTC).date() - merged.astimezone(UTC).date()).days
    return f"merged {merged.astimezone(UTC).date()}, {_relative(days)} this verdict"


def _relative(days: int) -> str:
    if days == 0:
        return "the same day as"
    return f"{_days(abs(days))} {'before' if days > 0 else 'after'}"


def _days(count: int) -> str:
    return "1 day" if count == 1 else f"{count} days"


def _registry_of(receipt: Receipt, registry_for: RegistryFor) -> ReadRegistry:
    path = registry_for(receipt.repo)
    return _read_registry(path) if path is not None and path.exists() else (None, None)


def _read_registry(path: Path) -> ReadRegistry:
    # A registry this console cannot read, e.g. one a newer knack wrote, is never a 500.
    try:
        return load_registry(path), None
    except (ValueError, OSError) as error:
        return None, f"cannot read {path}: {str(error).splitlines()[0]}"


def _resolution_of(receipt: Receipt, chain: list[Receipt]) -> ResolutionView | None:
    # The allow that resolved this deny, or this receipt when it is that allow.
    found = (
        r for r in chain if r.resolution and receipt.hash in (r.hash, r.resolution.of)
    )
    return next((_resolution_view(r) for r in found), None)


def _resolution_view(allow: Receipt) -> ResolutionView:
    assert allow.resolution is not None
    fields = allow.resolution.model_dump() | {"time": allow.time}
    return ResolutionView.model_validate(fields | {"receipt_hash": allow.hash})


def _cited_root(receipt: Receipt, registry: Registry | None) -> Root | None:
    # A receipt cites at most one root; a root gone from the store is None.
    if registry is None or not receipt.root_ids:
        return None
    by_id = {root.id: root for root in load_roots(registry.roots_dir)}
    return by_id.get(receipt.root_ids[0])


def _proof_of(receipt: Receipt, registry: Registry | None) -> RuleProof | None:
    # The installed rule whose id the receipt names; a rule since removed has none.
    entries = registry.rules if registry else []
    found = (e for e in entries if rule_name(e.rule) == receipt.rule_id)
    return next((entry.proof for entry in found), None)


def _one_per_line_range(matched: list[MatchedCode]) -> list[MatchedCode]:
    # Nested or repeated matches over the same lines show once, first one kept.
    by_range: dict[tuple[int, int], MatchedCode] = {}
    for match in matched:
        by_range.setdefault((match.line, match.line + match.text.count("\n")), match)
    return list(by_range.values())


def _others_on_branch(receipt: Receipt, chain: list[Receipt]) -> list[OtherDecision]:
    # Same repo, rule and branch, in chain order, without the receipt itself.
    return [
        OtherDecision(
            hash=other.hash,
            time=other.time,
            file=other.file,
            outcome=other.decision,
            latency_ms=other.latency_ms,
        )
        for other in chain
        if _same_branch(receipt, other) and other.hash != receipt.hash
    ]


def _same_branch(receipt: Receipt, other: Receipt) -> bool:
    same = (other.repo, other.rule_id, other.branch)
    return same == (receipt.repo, receipt.rule_id, receipt.branch)


def _warn_before(receipt: Receipt, warns: list[WarnRecord]) -> WarnView | None:
    # The session's latest warn before the deny, else the clone's (a replayed deny).
    earlier = _clone_warns_before(receipt, warns)
    ours = [pair for pair in earlier if _same_session(receipt, pair[1])]
    last = max(ours or earlier, key=lambda pair: pair[0], default=None)
    return None if last is None else _warn_view(receipt, last[1])


def _clone_warns_before(receipt: Receipt, warns: list[WarnRecord]) -> list[TimedWarn]:
    # Warns in the receipt's clone at or before its time; unparseable times never match.
    decided = _parsed(receipt.time)
    if decided is None:
        return []
    timed = [(_parsed(w.time), w) for w in warns if _in_clone(receipt, w)]
    return [(at, w) for at, w in timed if at is not None and at <= decided]


def _in_clone(receipt: Receipt, warn: WarnRecord) -> bool:
    same_repo = receipt.repo == warn.repo
    return same_repo and Path(receipt.file).is_relative_to(warn.root)


def _same_session(receipt: Receipt, warn: WarnRecord) -> bool:
    return receipt.session_id is not None and warn.session_id == receipt.session_id


def _warn_view(receipt: Receipt, warn: WarnRecord) -> WarnView:
    same = _same_session(receipt, warn)
    return WarnView(time=warn.time, context=warn.context, same_session=same)


def _parsed(time: str) -> datetime | None:
    try:
        return datetime.fromisoformat(time)
    except ValueError:
        return None
