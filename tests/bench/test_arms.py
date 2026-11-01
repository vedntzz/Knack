import hashlib
import json
import shlex
from pathlib import Path
from typing import Any

import pytest
from knack.bench.arms import ArmError, prepare_home
from knack.contracts.models import DecisionStatus, Root
from knack.roots.store import load_roots, write_root
from knack.walk.registry import load_registry, Registry, registry_dir_in, RegistryEntry

REPO = "acme/widgets"
AUTH = b'{"schema_version": 2, "providers": {"meta": {"storage": "keychain"}}}\n'
# The real settings carry a watch hook and more; no arm may inherit any of it.
REAL_SETTINGS = {
    "schema_version": 1,
    "hooks": {"PostToolBatch": [{"hooks": [{"type": "command", "command": "watch"}]}]},
}
ARM_EVENTS = {"none": set[str](), "veto": {"PreToolUse"}}
ARM_EVENTS["warn+veto"] = {"PreToolUse", "UserPromptSubmit"}
MODULES = {"PreToolUse": "knack.hooks.pretool", "UserPromptSubmit": "knack.hooks.warn"}


def root(root_id: str, status: DecisionStatus) -> Root:
    url = "https://github.com/acme/widgets/pull/9"
    fields: dict[str, Any] = {"id": root_id, "title": "t", "source_url": url}
    fields |= {"decision": "d", "why": "w", "decided_by": "maria", "quote": "q"}
    return Root.model_validate(fields | {"status": status, "rejected_alternative": "r"})


def make_registry(out: Path) -> Path:
    # A source registry with one Inferred and one Uncorroborated root.
    write_root(root("widgets-9-1", "Inferred"), out / "roots" / "widgets-9-1.json")
    write_root(
        root("widgets-9-2", "Uncorroborated"), out / "roots" / "widgets-9-2.json"
    )
    (out / "rules").mkdir(parents=True)
    (out / "rules" / "9.yml").write_text("id: widgets-9\nlanguage: python\n")
    entry = RegistryEntry(
        rule=Path("rules/9.yml"), root_ids=["widgets-9-1", "widgets-9-2"]
    )
    registry = Registry(repo=REPO, roots_dir=Path("roots"), rules=[entry])
    (out / "registry.json").write_text(registry.model_dump_json())
    return out / "registry.json"


@pytest.fixture
def real_home(tmp_path: Path) -> Path:
    # Stands in for the user's home: auth, settings and a home registry.
    home = tmp_path / "real"
    (home / ".config" / "muse").mkdir(parents=True)
    (home / ".config" / "muse" / "auth.json").write_bytes(AUTH)
    (home / ".config" / "muse" / "settings.json").write_text(json.dumps(REAL_SETTINGS))
    make_registry(home / ".knack" / "registries" / "acme-widgets")
    return home


@pytest.fixture
def runs(tmp_path: Path) -> Path:
    (tmp_path / "runs").mkdir()
    return tmp_path / "runs"


def source_registry(real_home: Path) -> Path:
    return real_home / ".knack" / "registries" / "acme-widgets" / "registry.json"


def prepare(arm: str, real_home: Path, runs: Path) -> Path:
    return prepare_home(arm, source_registry(real_home), runs)


def settings(home: Path) -> dict[str, Any]:
    return json.loads((home / ".config" / "muse" / "settings.json").read_text())


def bench_registry(home: Path) -> Path:
    return home / ".knack" / "registries" / "acme-widgets" / "registry.json"


def commands(home: Path, event: str) -> list[str]:
    entries = settings(home)["hooks"][event]
    return [hook["command"] for entry in entries for hook in entry["hooks"]]


def snapshot(*paths: Path) -> dict[str, str]:
    # A hash of every file under the paths, so any byte change shows.
    files = [f for p in paths for f in ([p] if p.is_file() else sorted(p.rglob("*")))]
    return {
        str(f): hashlib.sha256(f.read_bytes()).hexdigest() for f in files if f.is_file()
    }


@pytest.mark.parametrize("arm", sorted(ARM_EVENTS))
def test_each_arm_installs_only_its_hooks(
    arm: str, real_home: Path, runs: Path
) -> None:
    home = prepare(arm, real_home, runs)
    assert set(settings(home)["hooks"]) == ARM_EVENTS[arm]
    assert settings(home)["schema_version"] == REAL_SETTINGS["schema_version"]


@pytest.mark.parametrize("arm", ["veto", "warn+veto"])
def test_hooks_run_knack_against_the_bench_registry(
    arm: str, real_home: Path, runs: Path
) -> None:
    home = prepare(arm, real_home, runs)
    for event in ARM_EVENTS[arm]:
        [command] = commands(home, event)
        inner = shlex.split(command)[2]
        assert f"KNACK_REGISTRY={shlex.quote(str(bench_registry(home)))} " in inner
        assert f"-m {MODULES[event]} || true" in inner


def test_veto_hook_matches_file_writes_only(real_home: Path, runs: Path) -> None:
    [entry] = settings(prepare("veto", real_home, runs))["hooks"]["PreToolUse"]
    assert entry["matcher"] == "write_file|edit_file"


def test_muse_config_holds_the_arm_settings_and_no_credential(
    real_home: Path, runs: Path
) -> None:
    # The key reaches muse through its environment, never as a file in the home.
    home = prepare("veto", real_home, runs)
    assert sorted(p.name for p in (home / ".config" / "muse").iterdir()) == [
        "settings.json"
    ]
    assert not [p for p in home.rglob("auth.json")]


def test_bench_registry_confirms_every_root(real_home: Path, runs: Path) -> None:
    registry = load_registry(bench_registry(prepare("veto", real_home, runs)))
    roots = load_roots(registry.roots_dir)
    assert [r.id for r in roots] == ["widgets-9-1", "widgets-9-2"]
    # Seeded marks the bench's promotion, so no root passes as human-reviewed.
    assert {(r.status, r.seeded) for r in roots} == {("Confirmed", True)}


def test_bench_registry_copies_the_rules_into_the_run_home(
    real_home: Path, runs: Path
) -> None:
    home = prepare("veto", real_home, runs)
    [entry] = load_registry(bench_registry(home)).rules
    assert entry.rule.is_relative_to(home)
    assert (
        entry.rule.read_bytes()
        == (source_registry(real_home).parent / "rules/9.yml").read_bytes()
    )


def test_real_settings_and_home_registry_are_untouched(
    real_home: Path, runs: Path
) -> None:
    before = snapshot(real_home)
    for arm in ARM_EVENTS:
        prepare_home(arm, source_registry(real_home), runs)
    assert snapshot(real_home) == before


def test_your_real_settings_and_home_registry_are_byte_identical(
    runs: Path, real_home: Path, real_knack_home: Path
) -> None:
    real = registry_dir_in(real_knack_home, "apache/airflow")
    if not (real / "registry.json").exists():
        pytest.skip("needs the apache/airflow home registry")
    watched = [real_home / ".config" / "muse", real]
    before = snapshot(*watched)
    home = prepare_home("warn+veto", real / "registry.json", runs)
    assert home.is_relative_to(runs)
    assert snapshot(*watched) == before


def test_two_runs_never_share_a_home(real_home: Path, runs: Path) -> None:
    first, second = prepare("veto", real_home, runs), prepare("veto", real_home, runs)
    (first / ".config" / "muse" / "settings.json").write_text("{}")
    assert first != second
    assert not first.is_relative_to(second) and not second.is_relative_to(first)
    assert set(settings(second)["hooks"]) == {"PreToolUse"}


def test_unknown_arm_raises(real_home: Path, runs: Path) -> None:
    with pytest.raises(ArmError, match="warn-only"):
        prepare("warn-only", real_home, runs)
