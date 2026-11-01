from datetime import datetime
from pathlib import Path

from knack.day.models import Day, ReceiptEvent, ReceiptKind
from knack.day.roots import registry_roots
from knack.day.when import on_day
from knack.dispute.rulings import load_rulings
from knack.receipts.chain import load_receipts, Receipt
from knack.receipts.warns import load_warns

# Root id to its decided_by.
Deciders = dict[str, str]
RULED: dict[str, ReceiptKind] = {"hold": "held", "escalate": "argue"}


def todays_receipts(day: Day, repo: str, now: datetime) -> list[ReceiptEvent]:
    # Blocks and learns from the chain, warns, and rulings on this repo's denies.
    chain = [r for r in load_receipts(day.receipts) if same_repo(r.repo, repo)]
    deciders = _deciders(day.registry_for(repo))
    found = _chain_events(chain, deciders) + _warn_events(day.warns, repo)
    found += _ruling_events(day.rulings, chain, deciders)
    return [event for event in found if on_day(event.time, now)]


def same_repo(stored: str, repo: str) -> bool:
    # The hook guards any clone whose origin names the registry's repo, case aside.
    return stored.lower() == repo.lower()


def _deciders(registry: Path | None) -> Deciders:
    return {root.id: root.decided_by for root in registry_roots(registry)[0]}


def _chain_events(chain: list[Receipt], deciders: Deciders) -> list[ReceiptEvent]:
    # A deny is a block, a knack resolve allow a learn; other allows are no event.
    found: list[tuple[ReceiptKind | None, Receipt]] = [
        (_chain_kind(receipt), receipt) for receipt in chain
    ]
    return [_event(kind, r.time, r, deciders) for kind, r in found if kind]


def _chain_kind(receipt: Receipt) -> ReceiptKind | None:
    if receipt.resolution is not None:
        return "learn"
    return "block" if receipt.decision == "deny" else None


def _warn_events(warns: Path, repo: str) -> list[ReceiptEvent]:
    # A warn cites no root and has no hash.
    found = [w for w in load_warns(warns) if same_repo(w.repo, repo)]
    return [_unhashed_warn(warn.time) for warn in found]


def _unhashed_warn(time: str) -> ReceiptEvent:
    return ReceiptEvent(
        kind="warn", time=time, root_id=None, decider=None, receipt_hash=None
    )


def _ruling_events(
    rulings: Path, chain: list[Receipt], deciders: Deciders
) -> list[ReceiptEvent]:
    # A ruling cites the deny it answers; one on another repo's deny is not ours.
    denies = {r.hash: r for r in chain if r.decision == "deny"}
    found = [
        (ruling, denies.get(ruling.receipt_hash)) for ruling in load_rulings(rulings)
    ]
    return [
        _event(RULED[ruling.decision], ruling.time, deny, deciders)
        for ruling, deny in found
        if deny
    ]


def _event(
    kind: ReceiptKind, time: str, receipt: Receipt, deciders: Deciders
) -> ReceiptEvent:
    root_id = receipt.root_ids[0] if receipt.root_ids else None
    decider = deciders.get(root_id) if root_id else None
    return ReceiptEvent(
        kind=kind,
        time=time,
        root_id=root_id,
        decider=decider,
        receipt_hash=receipt.hash,
    )
