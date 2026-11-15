import json
import shlex
from pathlib import Path
from typing import Any, cast

from knack.atomic import write_atomically
from knack.git import git_root
from knack.home import user_home

JsonDict = dict[str, Any]
EVENT = "PreToolUse"
PRETOOL_MODULE = "knack.hooks.pretool"
# Each agent's file-writing tools; Muse's bash is in for the person-only command check.
MATCHERS = {"claude-code": "Write|Edit|MultiEdit", "muse": "write_file|edit_file|bash"}
# Muse Code's settings file carries a schema version; Claude Code's has none.
NEW_SETTINGS: dict[str, JsonDict] = {"claude-code": {}, "muse": {"schema_version": 1}}


class HookInstallError(Exception):
    pass


def default_settings(agent: str, cwd: Path) -> Path:
    # Claude Code: the project's own settings; Muse Code: the user's.
    if agent == "muse":
        return user_home() / ".config" / "muse" / "settings.json"
    return (git_root(cwd) or cwd).resolve() / ".claude" / "settings.json"


def pretool_command(python: str) -> str:
    # sh -c '... || true': a hook crash never blocks the agent.
    return f"sh -c {shlex.quote(f'{shlex.quote(python)} -m {PRETOOL_MODULE} || true')}"


def install_hook(agent: str, settings: Path, python: str) -> bool:
    # False when already installed; our older entries are replaced, others kept.
    data = _read_settings(settings, agent)
    entries = _pretool_entries(data, settings)
    _refuse_foreign(entries, MATCHERS[agent], settings)
    updated = _with_ours(entries, MATCHERS[agent], pretool_command(python))
    if updated != entries:
        _save(settings, data, updated)
    return updated != entries


def _with_ours(entries: list[Any], matcher: str, command: str) -> list[Any]:
    return [entry for entry in entries if not _is_ours(entry)] + [
        _entry(matcher, command)
    ]


def _save(settings: Path, data: JsonDict, entries: list[Any]) -> None:
    data["hooks"][EVENT] = entries
    write_atomically(settings, json.dumps(data, indent=2) + "\n")


def _read_settings(settings: Path, agent: str) -> JsonDict:
    # A file we cannot read as a JSON object is left alone, never overwritten.
    if not settings.exists():
        return dict(NEW_SETTINGS[agent])
    data = _parsed(settings)
    if not isinstance(data, dict):
        raise HookInstallError(f"{settings} is not a JSON object, so it was left alone")
    return cast(JsonDict, data)


def _parsed(settings: Path) -> object:
    try:
        return json.loads(settings.read_text(encoding="utf-8"))
    except (ValueError, OSError) as error:
        raise HookInstallError(f"{settings} is not readable JSON: {error}") from error


def _pretool_entries(data: JsonDict, settings: Path) -> list[Any]:
    hooks: object = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise HookInstallError(f"{settings}: hooks is not an object")
    entries: object = cast(JsonDict, hooks).setdefault(EVENT, [])
    if not isinstance(entries, list):
        raise HookInstallError(f"{settings}: hooks.{EVENT} is not a list")
    return list(cast(list[Any], entries))


def _refuse_foreign(entries: list[Any], matcher: str, settings: Path) -> None:
    # Someone else's hook on our matcher is theirs to merge, not ours to replace.
    for entry in entries:
        if _matcher(entry) == matcher and not _is_ours(entry):
            message = f"{settings} has a {EVENT} {matcher} hook that is not knack's"
            raise HookInstallError(f"{message}; add knack's beside it by hand")


def _is_ours(entry: Any) -> bool:
    # Ours: every command in the entry runs the knack pretool module.
    commands = [hook.get("command") for hook in _hooks(entry)]
    marker = f"-m {PRETOOL_MODULE} "
    return bool(commands) and all(marker in str(c) for c in commands)


def _hooks(entry: Any) -> list[JsonDict]:
    hooks: object = (
        cast(JsonDict, entry).get("hooks") if isinstance(entry, dict) else None
    )
    items = cast(list[Any], hooks) if isinstance(hooks, list) else []
    return [cast(JsonDict, hook) for hook in items if isinstance(hook, dict)]


def _matcher(entry: Any) -> object:
    return cast(JsonDict, entry).get("matcher") if isinstance(entry, dict) else None


def _entry(matcher: str, command: str) -> JsonDict:
    return {"matcher": matcher, "hooks": [{"type": "command", "command": command}]}
