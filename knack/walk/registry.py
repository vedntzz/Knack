from pathlib import Path

from pydantic import BaseModel, ConfigDict


class RegistryEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rule: Path
    root_ids: list[str]


class Registry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    repo: str
    roots_dir: Path
    rules: list[RegistryEntry]


def load_registry(path: Path) -> Registry:
    # Rule and roots paths in the file are relative to the registry file.
    registry = Registry.model_validate_json(path.read_text(encoding="utf-8"))
    rules = [_anchored(entry, path.parent) for entry in registry.rules]
    roots_dir = path.parent / registry.roots_dir
    return registry.model_copy(update={"rules": rules, "roots_dir": roots_dir})


def _anchored(entry: RegistryEntry, base: Path) -> RegistryEntry:
    return entry.model_copy(update={"rule": base / entry.rule})
