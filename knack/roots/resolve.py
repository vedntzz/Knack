from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path

from knack.contracts.models import Root
from knack.miss.provisional import promote_provisional
from knack.receipts.chain import (
    append_receipt,
    load_receipts,
    Receipt,
    Resolution,
    resolution_of,
    resolution_receipt,
    ResolutionAction,
)
from knack.roots.correct import drop_from_registry
from knack.roots.corrections import append_correction, Correction
from knack.roots.store import find_root
from knack.walk.registry import home_registry_dir, load_registry


class ResolveError(Exception):
    pass


@dataclass(frozen=True)
class Resolved:
    correction: Correction
    # The allow appended to the chain, citing the deny it resolves.
    receipt: Receipt
    # The provisional argue case an allow made must-pass; None when there was none.
    promoted: Path | None = None


def resolve_deny(
    receipts: Path,
    receipt_hash: str,
    action: ResolutionAction,
    reason: str,
    by: str,
    log: Path,
    registry_path: Path | None = None,
) -> Resolved:
    # A person settles a deny: allow lets that exact edit through, retire drops the rule.
    deny = _unresolved_deny(receipts, receipt_hash, reason)
    registry = registry_path or home_registry_dir(deny.repo) / "registry.json"
    resolution = Resolution(of=deny.hash, action=action, by=by, reason=reason)
    correction = _correction(_cited_root(registry, deny), resolution)
    _apply(registry, correction, log)
    receipt = append_receipt(
        receipts, resolution_receipt(deny, resolution, correction.at)
    )
    return Resolved(correction, receipt, _promoted(registry, resolution))


def _promoted(registry_path: Path, resolution: Resolution) -> Path | None:
    # Only a person's allow turns two models' agreement into a must-pass case.
    if resolution.action != "allow":
        return None
    named = (resolution.of, resolution.by, resolution.reason)
    return promote_provisional(registry_path, *named)


def _unresolved_deny(receipts: Path, receipt_hash: str, reason: str) -> Receipt:
    if not reason.strip():
        raise ResolveError("resolve needs a --reason")
    deny = _receipt(receipts, receipt_hash)
    done = resolution_of(receipts, deny.hash)
    if done is not None:
        raise ResolveError(
            f"{receipt_hash} already resolved: {done.action} by {done.by}"
        )
    return deny


def _receipt(receipts: Path, receipt_hash: str) -> Receipt:
    found = next((r for r in load_receipts(receipts) if r.hash == receipt_hash), None)
    if found is None:
        raise ResolveError(f"no receipt {receipt_hash} in {receipts}")
    if found.decision != "deny" or found.resolution is not None:
        raise ResolveError(f"{receipt_hash} is not a deny: it records {found.decision}")
    return found


def _cited_root(registry_path: Path, deny: Receipt) -> Root:
    if not registry_path.exists():
        raise ResolveError(f"no registry at {registry_path}; pass --registry")
    roots_dir, cited = load_registry(registry_path).roots_dir, deny.root_ids
    found = find_root(roots_dir, cited[0]) if cited else None
    if found is None:
        raise ResolveError(f"no root {', '.join(cited)} in {roots_dir}")
    return found[1]


def _correction(root: Root, resolution: Resolution) -> Correction:
    # The root itself is unchanged: an allow excuses one edit, a retire ends its rule.
    fields = {"root_id": root.id, "action": resolution.action, "before": root}
    fields |= {"after": root, "reason": resolution.reason, "by": resolution.by}
    at = datetime.now(UTC).isoformat(timespec="seconds")
    return Correction.model_validate(fields | {"at": at, "receipt_hash": resolution.of})


def _apply(registry_path: Path, correction: Correction, log: Path) -> None:
    if correction.action == "retire":
        drop_from_registry(registry_path, correction.root_id)
    append_correction(correction, log)
