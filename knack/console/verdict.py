import hashlib
import os
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from knack.contracts.models import MatchedCode, Root
from knack.hooks.scope import REGISTRY_ENV
from knack.receipts.chain import Decision, load_receipts, Receipt, receipt_hash
from knack.receipts.warns import load_warns, WarnRecord
from knack.roots.store import load_roots
from knack.walk.registry import home_registry_dir, load_registry

# The registry file that guards a repo, or None when it has none.
RegistryFor = Callable[[str], Path | None]
NO_RECEIPT = "no receipt with that hash"


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
    # False when the root's quote changed since the receipt hashed it.
    quote_verified: bool


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
    matched: list[MatchedCode]
    root: RootView | None
    other_decisions: list[OtherDecision]
    warn: WarnView | None


class NoSuchReceipt(Exception):
    pass


def verdict_view(
    wanted: str, receipts: Path, warns: Path, registry_for: RegistryFor
) -> VerdictView:
    chain = load_receipts(receipts)
    receipt = next((r for r in chain if r.hash == wanted), None)
    if receipt is None:
        raise NoSuchReceipt(NO_RECEIPT)
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
        matched=receipt.matched or [],
        root=_root_view(receipt, registry_for),
        other_decisions=_others_on_branch(receipt, chain),
        warn=_warn_before(receipt, load_warns(warns)),
    )


def home_registry_for(repo: str) -> Path | None:
    # The registry the hook guards with: KNACK_REGISTRY, else the repo's home one.
    value = os.environ.get(REGISTRY_ENV)
    if value:
        return Path(value).expanduser().resolve()
    path = home_registry_dir(repo) / "registry.json"
    return path if path.exists() else None


def _root_view(receipt: Receipt, registry_for: RegistryFor) -> RootView | None:
    # The root as it reads now; quote_verified says if it still reads as receipted.
    root = _cited_root(receipt, registry_for)
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
        quote_verified=quote == receipt.quote_sha256,
    )


def _cited_root(receipt: Receipt, registry_for: RegistryFor) -> Root | None:
    # A receipt cites at most one root; a root gone from the store is None.
    path = registry_for(receipt.repo)
    if path is None or not path.exists() or not receipt.root_ids:
        return None
    by_id = {root.id: root for root in load_roots(load_registry(path).roots_dir)}
    return by_id.get(receipt.root_ids[0])


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
    # The latest warning the agent had in this clone and session when it was denied.
    decided = _parsed(receipt.time)
    if decided is None:
        return None
    timed = [(_parsed(w.time), w) for w in warns if _warned_this_agent(receipt, w)]
    before = [(at, w) for at, w in timed if at is not None and at <= decided]
    if not before:
        return None
    last = max(before, key=lambda pair: pair[0])[1]
    return WarnView(time=last.time, context=last.context)


def _warned_this_agent(receipt: Receipt, warn: WarnRecord) -> bool:
    # A receipt from before sessions were recorded takes any warn in its clone.
    if receipt.repo != warn.repo or not Path(receipt.file).is_relative_to(warn.root):
        return False
    return receipt.session_id is None or warn.session_id == receipt.session_id


def _parsed(time: str) -> datetime | None:
    try:
        return datetime.fromisoformat(time)
    except ValueError:
        return None
