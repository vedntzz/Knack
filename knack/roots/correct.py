import getpass
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Literal

from knack.contracts.models import DecisionStatus, Root
from knack.git import git_output
from knack.roots.corrections import append_correction, Correction
from knack.roots.pin import cited_rule_sha
from knack.roots.store import find_root, write_root
from knack.walk.registry import load_registry, Registry, RegistryEntry

Found = tuple[Path, Root]
Action = Literal["confirm", "reject"]
STATUS_AFTER: dict[Action, DecisionStatus] = {
    "confirm": "Confirmed",
    "reject": "Unknown",
}


# Every machine label a human can promote.
CONFIRMABLE = ("Inferred", "Corroborated", "Uncorroborated")


class CorrectionError(Exception):
    pass


def confirm_root(registry_path: Path, root_id: str, by: str, log: Path) -> Correction:
    # A machine guess is promoted, or a Confirmed root re-pinned; the pinned rule blocks.
    found = _located(registry_path, root_id)
    sha = cited_rule_sha(load_registry(registry_path), root_id)
    _require_confirmable(found[1], sha)
    return _record(found, "confirm", None, by, log, sha)


def reject_root(
    registry_path: Path, root_id: str, reason: str, by: str, log: Path
) -> Correction:
    # Unknown never blocks, and the root no longer backs any rule.
    found = _rejectable(registry_path, root_id, reason)
    correction = _record(found, "reject", reason, by, log)
    drop_from_registry(registry_path, root_id)
    return correction


def reviewer_name(cwd: Path) -> str:
    return git_output(cwd, "config", "user.name") or getpass.getuser()


def _require_confirmable(root: Root, sha: str | None) -> None:
    # Confirmed passes only to re-pin a rule recompiled since, or never pinned.
    if root.status == "Confirmed" and root.rule_sha == sha:
        raise CorrectionError(f"{root.id} is already Confirmed and pinned to {sha}")
    if root.status not in (*CONFIRMABLE, "Confirmed"):
        allowed = ", ".join(CONFIRMABLE)
        raise CorrectionError(f"{root.id} is {root.status}; only {allowed} confirm")


def _rejectable(registry_path: Path, root_id: str, reason: str) -> Found:
    if not reason.strip():
        raise CorrectionError("reject needs a --reason")
    found = _located(registry_path, root_id)
    if found[1].status == "Unknown":
        raise CorrectionError(f"{root_id} is already Unknown")
    return found


def _located(registry_path: Path, root_id: str) -> Found:
    if not registry_path.exists():
        raise CorrectionError(f"no registry at {registry_path}")
    roots_dir = load_registry(registry_path).roots_dir
    found = find_root(roots_dir, root_id)
    if found is None:
        raise CorrectionError(f"no root {root_id} in {roots_dir}")
    return found


def _record(
    found: Found,
    action: Action,
    reason: str | None,
    by: str,
    log: Path,
    sha: str | None = None,
) -> Correction:
    # The root file is rewritten in place, then the change is logged.
    path, before = found
    correction = _correction(before, action, reason, by, sha)
    write_root(correction.after, path)
    append_correction(correction, log)
    return correction


def _correction(
    before: Root, action: Action, reason: str | None, by: str, sha: str | None
) -> Correction:
    after = before.model_copy(update=_labels_after(action, by, sha))
    fields = {"root_id": before.id, "action": action, "before": before, "after": after}
    fields |= {"reason": reason, "by": by, "at": _now()}
    return Correction.model_validate(fields)


def _labels_after(action: Action, by: str, sha: str | None) -> dict[str, Any]:
    # A confirm records who and which rule; a reject clears both, since Unknown never blocks.
    confirmed = action == "confirm"
    pin = {"confirmed_by": by, "rule_sha": sha} if confirmed else {}
    return {
        "status": STATUS_AFTER[action],
        "confirmed_by": None,
        "rule_sha": None,
    } | pin


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def drop_from_registry(registry_path: Path, root_id: str) -> None:
    # A rule backed only by this root goes; a shared rule just stops citing it.
    registry = Registry.model_validate_json(registry_path.read_text("utf-8"))
    kept = [_without(e, root_id) for e in registry.rules if e.root_ids != [root_id]]
    if kept == registry.rules:
        return
    updated = registry.model_copy(update={"rules": kept})
    registry_path.write_text(updated.model_dump_json(indent=2) + "\n", encoding="utf-8")


def _without(entry: RegistryEntry, root_id: str) -> RegistryEntry:
    remaining = [other for other in entry.root_ids if other != root_id]
    return entry.model_copy(update={"root_ids": remaining})
