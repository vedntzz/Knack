import shutil
from dataclasses import dataclass
from pathlib import Path

from knack.pipeline.roots import reviewed_roots
from knack.roots.store import find_root, load_roots, write_root
from knack.walk.registry import (
    home_registry_dir,
    load_registry,
    Registry,
    RegistryEntry,
)

HOME_RULES = Path("rules")


class RegistryImportError(Exception):
    pass


@dataclass(frozen=True)
class Imported:
    repo: str
    home: Path
    rules_added: int
    rules_total: int
    roots_written: int
    roots_kept: int


def import_registry(source: Path) -> Imported:
    # Home wins: its rules and reviewed roots stay, and rejected roots back nothing.
    incoming = _incoming(source)
    home = home_registry_dir(incoming.repo) / "registry.json"
    _refuse_self(source, home)
    current = _current(home, incoming.repo)
    roots = _merge_roots(incoming.roots_dir, home.parent / current.roots_dir)
    added = _install_rules(incoming, current, home.parent)
    return _write(home, current, added, roots)


def import_lines(done: Imported) -> list[str]:
    rules = f"  rules: {done.rules_added} added, {done.rules_total} in registry"
    roots = f"  roots: {done.roots_written} written, {done.roots_kept} reviewed kept"
    return [f"knack import {done.repo} -> {done.home}", rules, roots]


def _incoming(source: Path) -> Registry:
    if not source.is_file():
        raise RegistryImportError(f"no registry at {source}")
    return load_registry(source)


def _refuse_self(source: Path, home: Path) -> None:
    if source.resolve() == home.resolve():
        raise RegistryImportError(f"{source} is already the home registry")


def _current(home: Path, repo: str) -> Registry:
    # The home registry as written, paths still relative; empty before any init.
    if not home.exists():
        return Registry(repo=repo, roots_dir=Path("roots"), rules=[])
    return Registry.model_validate_json(home.read_text(encoding="utf-8"))


def _merge_roots(source_dir: Path, home_dir: Path) -> tuple[int, int]:
    # A root a human reviewed in home, Confirmed or rejected, is never replaced.
    reviewed = reviewed_roots(home_dir)
    incoming = load_roots(source_dir)
    fresh = [root for root in incoming if root.id not in reviewed]
    for root in fresh:
        write_root(root, _root_file(home_dir, root.id))
    return len(fresh), len(incoming) - len(fresh)


def _root_file(home_dir: Path, root_id: str) -> Path:
    # An id already in home keeps its file name, so ids never duplicate.
    found = find_root(home_dir, root_id) if home_dir.is_dir() else None
    return found[0] if found else home_dir / f"{root_id}.json"


def _install_rules(
    incoming: Registry, current: Registry, home_dir: Path
) -> list[RegistryEntry]:
    # Home's entry wins on the same rule file; a rejected root backs no imported rule.
    taken = {entry.rule for entry in current.rules}
    rejected = _rejected_ids(home_dir / current.roots_dir)
    fresh = [_without(entry, rejected) for entry in incoming.rules]
    kept = [e for e in fresh if e.root_ids and HOME_RULES / e.rule.name not in taken]
    return [_copied(entry, home_dir) for entry in kept]


def _rejected_ids(roots_dir: Path) -> set[str]:
    roots = load_roots(roots_dir) if roots_dir.is_dir() else []
    return {root.id for root in roots if root.status == "Unknown"}


def _without(entry: RegistryEntry, root_ids: set[str]) -> RegistryEntry:
    remaining = [root_id for root_id in entry.root_ids if root_id not in root_ids]
    return entry.model_copy(update={"root_ids": remaining})


def _copied(entry: RegistryEntry, home_dir: Path) -> RegistryEntry:
    # The rule file moves into home, so the entry no longer points at the source.
    target = home_dir / HOME_RULES / entry.rule.name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(entry.rule, target)
    return entry.model_copy(update={"rule": HOME_RULES / entry.rule.name})


def _write(
    home: Path, current: Registry, added: list[RegistryEntry], roots: tuple[int, int]
) -> Imported:
    rules = [*current.rules, *added]
    home.parent.mkdir(parents=True, exist_ok=True)
    text = current.model_copy(update={"rules": rules}).model_dump_json(indent=2)
    home.write_text(text + "\n", encoding="utf-8")
    return Imported(current.repo, home, len(added), len(rules), *roots)
