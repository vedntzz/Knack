from pathlib import Path

from pydantic import BaseModel, ConfigDict

from knack.contracts.models import RuleProof
from knack.git import git_root, origin_repo


class RegistryEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rule: Path
    root_ids: list[str]
    # Stored at install; None for rules installed before KN-60 or imported by hand.
    proof: RuleProof | None = None


class Registry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    repo: str
    roots_dir: Path
    rules: list[RegistryEntry]


def home_registry_dir(repo: str) -> Path:
    # Where knack init installs by default, and where knack watch looks.
    return Path.home() / ".knack" / "registries" / repo.replace("/", "-").lower()


class NoCloneRegistry(Exception):
    pass


def clone_home_registry(cwd: Path) -> Path | None:
    # The home registry for cwd's clone origin; None outside a clone with an origin.
    root = git_root(cwd)
    repo = origin_repo(root) if root else None
    return home_registry_dir(repo) / "registry.json" if repo else None


def required_clone_registry(cwd: Path) -> Path:
    path = clone_home_registry(cwd)
    if path is None:
        raise NoCloneRegistry(f"{cwd} is not a git clone of a repo; pass --registry")
    return path


def load_registry(path: Path) -> Registry:
    # Rule and roots paths in the file are relative to the registry file.
    registry = Registry.model_validate_json(path.read_text(encoding="utf-8"))
    rules = [_anchored(entry, path.parent) for entry in registry.rules]
    roots_dir = path.parent / registry.roots_dir
    return registry.model_copy(update={"rules": rules, "roots_dir": roots_dir})


def _anchored(entry: RegistryEntry, base: Path) -> RegistryEntry:
    return entry.model_copy(update={"rule": base / entry.rule})
