import getpass
from datetime import datetime, UTC
from pathlib import Path
from typing import Literal

from knack.contracts.models import DecisionStatus, Root
from knack.git import git_output
from knack.roots.corrections import append_correction, Correction
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
    # Only a machine-labelled root is a guess a human can promote; its rule now blocks.
    found = _located(registry_path, root_id)
    if found[1].status not in CONFIRMABLE:
        allowed = ", ".join(CONFIRMABLE)
        raise CorrectionError(f"{root_id} is {found[1].status}; only {allowed} confirm")
    return _record(found, "confirm", None, by, log)


def reject_root(
    registry_path: Path, root_id: str, reason: str, by: str, log: Path
) -> Correction:
    # Unknown never blocks, and the root no longer backs any rule.
    found = _rejectable(registry_path, root_id, reason)
    correction = _record(found, "reject", reason, by, log)
    _drop_from_registry(registry_path, root_id)
    return correction


def reviewer_name(cwd: Path) -> str:
    return git_output(cwd, "config", "user.name") or getpass.getuser()


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
    found: Found, action: Action, reason: str | None, by: str, log: Path
) -> Correction:
    # The root file is rewritten in place, then the change is logged.
    path, before = found
    correction = _correction(before, action, reason, by)
    write_root(correction.after, path)
    append_correction(correction, log)
    return correction


def _correction(
    before: Root, action: Action, reason: str | None, by: str
) -> Correction:
    after = before.model_copy(update={"status": STATUS_AFTER[action]})
    fields = {"root_id": before.id, "action": action, "before": before, "after": after}
    fields |= {"reason": reason, "by": by, "at": _now()}
    return Correction.model_validate(fields)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _drop_from_registry(registry_path: Path, root_id: str) -> None:
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
