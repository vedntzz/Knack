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


class WatchInstallError(Exception):
    pass


def install_post_merge(root: Path, registry: Path, python: str) -> Path:
    # Ours is replaced on reinstall; someone else's hook is never touched.
    path = _hooks_dir(root) / "post-merge"
    _refuse_foreign(path, _hook_command(python, "post-merge", registry))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_post_merge_script(python, registry), encoding="utf-8")
    path.chmod(0o755)
    return path


def add_muse_hook(settings: Path, registry: Path, python: str) -> bool:
    # False when the same command is already there; other hooks are kept as they are.
    data = _read_settings(settings)
    added = _add_command(data, muse_command(python, registry))
    if added:
        _write_settings(settings, data)
    return added


def muse_command(python: str, registry: Path) -> str:
    # The same sh -c '... || true' shape as the guard hooks: a crash never blocks.
    inner = f"{_hook_command(python, 'tool-batch', registry)} || true"
    return f"sh -c {shlex.quote(inner)}"


def _hook_command(python: str, mode: str, registry: Path) -> str:
    argv = [*_pinned(python), "-m", HOOK_MODULE, mode, "--registry", str(registry)]
    return shlex.join(argv)


def _pinned(python: str) -> list[str]:
    # macOS: an x86_64 git starts a universal python as x86_64, unable to load arm64 wheels.
    if sys.platform != "darwin":
        return [python]
    return ["/usr/bin/arch", f"-{platform.machine()}", python]


def _post_merge_script(python: str, registry: Path) -> str:
    note = f"{MARKER}: runs knack on PRs this merge brought in; never fails the merge."
    return (
        f"#!/bin/sh\n{note}\n{_hook_command(python, 'post-merge', registry)} || true\n"
    )


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


def _has_command(batch: list[Any], command: str) -> bool:
    hooks = [hook for entry in batch for hook in entry.get("hooks", [])]
    return any(hook.get("command") == command for hook in hooks)


def _write_settings(settings: Path, data: dict[str, Any]) -> None:
    # Written beside the file, then swapped in, so a crash never leaves half a file.
    settings.parent.mkdir(parents=True, exist_ok=True)
    partial = settings.with_name(settings.name + ".knack-tmp")
    partial.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    partial.replace(settings)
