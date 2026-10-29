import os
from pathlib import Path
from typing import Any

from knack.git import git_root, origin_repo, repo_slug
from knack.guard.check import log_error_quietly
from knack.walk.registry import load_registry, Registry

JsonDict = dict[str, Any]
REGISTRY_ENV = "KNACK_REGISTRY"


def event_cwd(event: JsonDict) -> Path:
    # tool_input.path is relative to the payload cwd, not the process cwd.
    return Path(str(event.get("cwd") or Path.cwd())).resolve()


def home_error_log() -> Path:
    # Knack files stay in the user's home, never inside the guarded repo.
    return Path.home() / ".knack" / "guard_errors.log"


def registry_path_from_env() -> Path:
    # A missing hook env is operator error: loud on stderr, silent on stdout.
    value = os.environ.get(REGISTRY_ENV)
    if not value:
        raise FileNotFoundError(f"{REGISTRY_ENV} is not set")
    return Path(value).expanduser().resolve()


def scoped_registry(event: JsonDict, path: Path) -> tuple[Registry, Path] | None:
    # The registry and git root, only when the cwd's origin is the registry's repo.
    registry = load_registry(path)
    root = git_root(event_cwd(event))
    if root is None or origin_repo(root) != repo_slug(registry.repo):
        return None
    return registry, root


def scoped_quietly(event: JsonDict, path: Path) -> tuple[Registry, Path] | None:
    # A broken registry is our failure: logged to home, never blocking.
    try:
        return scoped_registry(event, path)
    except Exception as error:
        log_error_quietly(home_error_log(), error)
        return None
