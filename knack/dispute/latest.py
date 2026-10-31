from datetime import datetime, timezone
from pathlib import Path

from knack.contracts.models import Root, Ruling
from knack.dispute.argue import argue, Ask, SPARK_MODEL
from knack.dispute.rulings import RulingRecord
from knack.hooks.pretool_guard import rule_name
from knack.hooks.scope import hook_registry_path, scoped_registry
from knack.receipts.chain import load_receipts, Receipt
from knack.roots.store import load_roots
from knack.walk.registry import Registry

NO_CLONE = "{cwd} is not a clone with a knack registry; nothing to dispute"
NO_DENY = "no deny receipt for this clone in {path}; nothing to dispute"
HELD = "ESCALATE: held for a person"


class NothingToDispute(Exception):
    pass


def dispute(objection: str, cwd: Path, receipts: Path, ask: Ask) -> RulingRecord:
    # The clone's latest deny names the rule; its roots answer the objection.
    registry, root = _clone_registry(cwd)
    denied = latest_deny(receipts, registry.repo, root)
    asked: list[str] = []
    roots = rule_roots(registry, denied.rule_id)
    ruling = argue(objection, roots, ask=_noting_asks(ask, asked))
    return _record(denied.hash, objection, ruling, SPARK_MODEL if asked else None)


def ruling_text(ruling: RulingRecord) -> str:
    head = "HOLD" if ruling.decision == "hold" else HELD
    quotes = [f'  "{quote}"' for quote in ruling.cited_quotes]
    return "\n".join([head, ruling.reply, *quotes])


def latest_deny(receipts: Path, repo: str, root: Path) -> Receipt:
    mine = [r for r in load_receipts(receipts) if _denied_here(r, repo, root)]
    if not mine:
        raise NothingToDispute(NO_DENY.format(path=receipts))
    return mine[-1]


def rule_roots(registry: Registry, rule_id: str) -> list[Root]:
    # A rule gone from the registry has no roots, so argue escalates.
    by_id = {root.id: root for root in load_roots(registry.roots_dir)}
    entries = [e for e in registry.rules if rule_name(e.rule) == rule_id]
    ids = [root_id for entry in entries for root_id in entry.root_ids]
    return [by_id[root_id] for root_id in ids if root_id in by_id]


def _clone_registry(cwd: Path) -> tuple[Registry, Path]:
    # The same registry the hook would guard this clone with.
    event = {"cwd": str(cwd)}
    path = hook_registry_path(event)
    scoped = scoped_registry(event, path) if path else None
    if scoped is None:
        raise NothingToDispute(NO_CLONE.format(cwd=cwd))
    return scoped


def _denied_here(receipt: Receipt, repo: str, root: Path) -> bool:
    # Another clone of the same repo has its own denies.
    inside = Path(receipt.file).is_relative_to(root)
    return receipt.decision == "deny" and receipt.repo == repo and inside


def _record(
    receipt_hash: str, objection: str, ruling: Ruling, model: str | None
) -> RulingRecord:
    time = datetime.now(timezone.utc).isoformat()
    linked = {"time": time, "receipt_hash": receipt_hash, "objection": objection}
    return RulingRecord(**linked, model=model, **ruling.model_dump())


def _noting_asks(ask: Ask, asked: list[str]) -> Ask:
    # A ruling names the model only when the model was actually asked.
    def noted(prompt: str) -> str:
        asked.append(prompt)
        return ask(prompt)

    return noted
