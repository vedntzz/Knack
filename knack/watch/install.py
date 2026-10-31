import json
import platform
import shlex
import sys
from pathlib import Path
from typing import Any

from knack.git import git_output

MARKER = "# installed by knack watch"
HOOK_MODULE = "knack.watch.hook"
MUSE_EVENT = "PostToolBatch"
# (corroborate, self_check): --corroborate, the default, --no-corroborate.
SETTINGS = ((True, True), (False, True), (False, False))


class WatchInstallError(Exception):
    pass


def install_post_merge(
    root: Path,
    registry: Path,
    python: str,
    corroborate: bool = False,
    self_check: bool = True,
) -> Path:
    # Ours is replaced on reinstall; someone else's hook is never touched.
    path = _hooks_dir(root) / "post-merge"
    command = _hook_command(python, "post-merge", registry, (corroborate, self_check))
    _refuse_foreign(path, command)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_post_merge_script(command), encoding="utf-8")
    path.chmod(0o755)
    return path


def add_muse_hook(
    settings: Path,
    registry: Path,
    python: str,
    corroborate: bool = False,
    self_check: bool = True,
) -> bool:
    # False when the same command is already there; other hooks are kept as they are.
    data = _read_settings(settings)
    command = muse_command(python, registry, corroborate, self_check)
    dropped = _drop_commands(data, _our_others(python, registry, command))
    added = _add_command(data, command)
    if added or dropped:
        _write_settings(settings, data)
    return added


def muse_command(
    python: str, registry: Path, corroborate: bool = False, self_check: bool = True
) -> str:
    # The same sh -c '... || true' shape as the guard hooks: a crash never blocks.
    hooked = _hook_command(python, "tool-batch", registry, (corroborate, self_check))
    return f"sh -c {shlex.quote(hooked + ' || true')}"


def second_model_flags(corroborate: bool, self_check: bool) -> list[str]:
    # --corroborate wins; --no-corroborate turns off the default Spark Open self-check.
    if corroborate:
        return ["--corroborate"]
    return [] if self_check else ["--no-corroborate"]


def _hook_command(
    python: str, mode: str, registry: Path, second: tuple[bool, bool]
) -> str:
    argv = [*_pinned(python), "-m", HOOK_MODULE, mode, "--registry", str(registry)]
    return shlex.join(argv + second_model_flags(*second))


def _our_others(python: str, registry: Path, command: str) -> list[str]:
    commands = [muse_command(python, registry, *setting) for setting in SETTINGS]
    return [other for other in commands if other != command]


def _pinned(python: str) -> list[str]:
    # macOS: an x86_64 git starts a universal python as x86_64, unable to load arm64 wheels.
    if sys.platform != "darwin":
        return [python]
    return ["/usr/bin/arch", f"-{platform.machine()}", python]


def _post_merge_script(command: str) -> str:
    note = f"{MARKER}: runs knack on PRs this merge brought in; never fails the merge."
    return f"#!/bin/sh\n{note}\n{command} || true\n"


def _hooks_dir(root: Path) -> Path:
    # Honors core.hooksPath; git prints the path relative to root.
    hooks = git_output(root, "rev-parse", "--git-path", "hooks")
    return root / (hooks or ".git/hooks")


def _refuse_foreign(path: Path, command: str) -> None:
    if path.exists() and MARKER not in path.read_text(encoding="utf-8"):
        message = f"{path} is not knack's, so it was left alone; add this line to it:"
        raise WatchInstallError(f"{message}\n  {command} || true")


def _read_settings(settings: Path) -> dict[str, Any]:
    if not settings.exists():
        return {"schema_version": 1, "hooks": {}}
    data: dict[str, Any] = json.loads(settings.read_text(encoding="utf-8"))
    return data


def _add_command(data: dict[str, Any], command: str) -> bool:
    batch: list[Any] = data.setdefault("hooks", {}).setdefault(MUSE_EVENT, [])
    if _has_command(batch, command):
        return False
    batch.append({"hooks": [{"type": "command", "command": command}]})
    return True


def _drop_commands(data: dict[str, Any], commands: list[str]) -> bool:
    # Our hook with any other second-model setting goes, so one run fires per batch.
    batch: list[Any] = data.get("hooks", {}).get(MUSE_EVENT, [])
    before = len(batch)
    batch[:] = [entry for entry in batch if not _has_any(entry, commands)]
    return len(batch) != before


def _has_any(entry: Any, commands: list[str]) -> bool:
    return any(_has_command([entry], command) for command in commands)


def _has_command(batch: list[Any], command: str) -> bool:
    hooks = [hook for entry in batch for hook in entry.get("hooks", [])]
    return any(hook.get("command") == command for hook in hooks)


def _write_settings(settings: Path, data: dict[str, Any]) -> None:
    # Written beside the file, then swapped in, so a crash never leaves half a file.
    settings.parent.mkdir(parents=True, exist_ok=True)
    partial = settings.with_name(settings.name + ".knack-tmp")
    partial.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    partial.replace(settings)
