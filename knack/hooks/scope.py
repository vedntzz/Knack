import os
from pathlib import Path
from typing import Any

from knack.git import git_root, origin_repo, repo_slug
from knack.guard.check import log_error_quietly
from knack.walk.registry import clone_home_registry, load_registry, Registry

JsonDict = dict[str, Any]
REGISTRY_ENV = "KNACK_REGISTRY"


def event_cwd(event: JsonDict) -> Path:
    # tool_input.path is relative to the payload cwd, not the process cwd.
    return Path(str(event.get("cwd") or Path.cwd())).resolve()


def home_error_log() -> Path:
    # Knack files stay in the user's home, never inside the guarded repo.
    return Path.home() / ".knack" / "guard_errors.log"


def hook_registry_path(event: JsonDict) -> Path | None:
    # KNACK_REGISTRY wins; unset, the clone's home registry, when one is installed.
    value = os.environ.get(REGISTRY_ENV)
    if value:
        return Path(value).expanduser().resolve()
    path = clone_home_registry(event_cwd(event))
    return path if path is not None and path.exists() else None


def scoped_registry(event: JsonDict, path: Path) -> tuple[Registry, Path] | None:
    # The registry and git root, only when the cwd's origin is the registry's repo.
    registry = load_registry(path)
    root = git_root(event_cwd(event))
    if root is None or origin_repo(root) != repo_slug(registry.repo):
        return None
    return registry, root


def scoped_quietly(event: JsonDict) -> tuple[Registry, Path] | None:
    # No registry for this clone is silence; a broken one is logged, never blocking.
    try:
        path = hook_registry_path(event)
        return scoped_registry(event, path) if path else None
    except Exception as error:
        log_error_quietly(home_error_log(), error)
        return None
