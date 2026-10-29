import json
import shlex
import shutil
import sys
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from knack.contracts.models import Root
from knack.hooks.scope import REGISTRY_ENV
from knack.roots.store import load_roots, write_root
from knack.walk.registry import home_registry_dir, load_registry, Registry

MUSE_DIR = Path(".config") / "muse"
AUTH = MUSE_DIR / "auth.json"
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


def prepare_home(
    arm: str, registry: Path, root: Path, real_home: Path | None = None
) -> Path:
    # A fresh HOME: the Muse auth copy, the arm's hooks, an all-Confirmed registry.
    hooks = _arm_hooks(arm)
    home = Path(tempfile.mkdtemp(prefix="home_", dir=root))
    bench = install_bench_registry(registry, home)
    _copy_auth(real_home or Path.home(), home)
    _write_json(home / SETTINGS, arm_settings(hooks, bench))
    return home


def end_run(home: Path) -> None:
    # The auth copy goes; settings, registry and logs stay for inspection.
    (home / AUTH).unlink(missing_ok=True)


@contextmanager
def isolated_home(
    arm: str, registry: Path, root: Path, real_home: Path | None = None
) -> Generator[Path]:
    home = prepare_home(arm, registry, root, real_home)
    try:
        yield home
    finally:
        end_run(home)


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
    out = home / home_registry_dir(registry.repo).relative_to(Path.home())
    for root in load_roots(registry.roots_dir):
        write_root(_bench_confirmed(root), out / "roots" / f"{root.id}.json")
    rules = [_copied_rule(entry.rule, out) for entry in registry.rules]
    return _write_registry(registry, rules, out)


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


def _copy_auth(real_home: Path, home: Path) -> None:
    # Only auth.json; the real settings.json and its hooks never reach the run.
    source = real_home / AUTH
    if not source.is_file():
        raise ArmError(f"no Muse login at {source}; run muse auth first")
    _write_private(home / AUTH, source.read_bytes())


def _write_private(path: Path, data: bytes) -> None:
    # Created 0600 before any byte lands, so the secret is never world-readable.
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(mode=0o600, exist_ok=False)
    path.write_bytes(data)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")
