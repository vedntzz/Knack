import json
import shlex
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from knack.contracts.models import Root
from knack.hooks.scope import REGISTRY_ENV
from knack.roots.store import load_roots, write_root
from knack.walk.registry import load_registry, Registry, registry_dir_in

MUSE_DIR = Path(".config") / "muse"
SETTINGS = MUSE_DIR / "settings.json"
SETTINGS_SCHEMA = 1
WRITE_TOOLS = "write_file|edit_file"
# A Muse hook: (event, knack hook module, tool matcher or None).
Hook = tuple[str, str, str | None]
VETO: Hook = ("PreToolUse", "knack.hooks.pretool", WRITE_TOOLS)
WARN: Hook = ("UserPromptSubmit", "knack.hooks.warn", None)
ARMS: dict[str, list[Hook]] = {"none": [], "veto": [VETO], "warn+veto": [VETO, WARN]}


class ArmError(Exception):
    pass


def prepare_home(arm: str, registry: Path, root: Path) -> Path:
    # A fresh HOME: the arm's hooks and an all-Confirmed registry, no credential.
    hooks = _arm_hooks(arm)
    home = Path(tempfile.mkdtemp(prefix="home_", dir=root))
    bench = install_bench_registry(registry, home)
    _write_json(home / SETTINGS, arm_settings(hooks, bench))
    return home


def arm_settings(hooks: list[Hook], registry: Path) -> dict[str, Any]:
    entries = {
        event: [_entry(module, matcher, registry)] for event, module, matcher in hooks
    }
    return {"schema_version": SETTINGS_SCHEMA, "hooks": entries}


def hook_command(module: str, registry: Path) -> str:
    # The guard hooks' sh -c '... || true' shape, pointed at the bench registry.
    env = f"{REGISTRY_ENV}={shlex.quote(str(registry))}"
    inner = f"{env} {shlex.quote(sys.executable)} -m {module} || true"
    return f"sh -c {shlex.quote(inner)}"


def install_bench_registry(source: Path, home: Path) -> Path:
    # The source's rules and roots under home's .knack, every root Confirmed.
    registry = load_registry(source)
    out = registry_in(home, registry.repo)
    for root in load_roots(registry.roots_dir):
        write_root(_bench_confirmed(root), out / "roots" / f"{root.id}.json")
    rules = [_copied_rule(entry.rule, out) for entry in registry.rules]
    return _write_registry(registry, rules, out)


def registry_in(home: Path, repo: str) -> Path:
    # The folder home_registry_dir names, under any home rather than the user's.
    return registry_dir_in(home / ".knack", repo)


def _arm_hooks(arm: str) -> list[Hook]:
    if arm not in ARMS:
        raise ArmError(f"unknown arm {arm!r}; arms are {sorted(ARMS)}")
    return ARMS[arm]


def _entry(module: str, matcher: str | None, registry: Path) -> dict[str, Any]:
    hooks = [{"type": "command", "command": hook_command(module, registry)}]
    return {"matcher": matcher, "hooks": hooks} if matcher else {"hooks": hooks}


def _bench_confirmed(root: Root) -> Root:
    # Seeded marks the bench's promotion, so no root passes as human-reviewed.
    return root.model_copy(update={"status": "Confirmed", "seeded": True})


def _copied_rule(rule: Path, out: Path) -> Path:
    target = out / "rules" / rule.name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(rule, target)
    return Path("rules") / rule.name


def _write_registry(registry: Registry, rules: list[Path], out: Path) -> Path:
    entries = [e.model_copy(update={"rule": r}) for e, r in zip(registry.rules, rules)]
    bench = registry.model_copy(update={"roots_dir": Path("roots"), "rules": entries})
    (out / "registry.json").write_text(bench.model_dump_json(indent=2) + "\n")
    return out / "registry.json"


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")
