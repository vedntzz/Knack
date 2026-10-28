from pathlib import Path

from pydantic import BaseModel, ConfigDict, TypeAdapter


class RegistryEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rule: Path
    root_ids: list[str]


REGISTRY = TypeAdapter(list[RegistryEntry])


def load_registry(path: Path) -> list[RegistryEntry]:
    # Rule paths in the file are relative to the registry file.
    entries = REGISTRY.validate_json(path.read_text(encoding="utf-8"))
    return [_anchored(entry, path.parent) for entry in entries]


def _anchored(entry: RegistryEntry, base: Path) -> RegistryEntry:
    return entry.model_copy(update={"rule": base / entry.rule})
