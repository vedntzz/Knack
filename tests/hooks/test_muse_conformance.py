import json
from pathlib import Path
from typing import Any

from knack.bench.arms import arm_settings, ARMS
from knack.bench.muse import exec_argv
from knack.watch.install import add_muse_hook

FIXTURES = Path(__file__).parent / "fixtures"
DOCUMENTED = json.loads(
    (FIXTURES / "muse_hook_events.json").read_text(encoding="utf-8")
)
EVENTS = set(DOCUMENTED["events"])


def undocumented_events(hooks_json: Path) -> list[str]:
    # Event keys in a written hook config that the Muse Code docs do not list.
    config: dict[str, Any] = json.loads(hooks_json.read_text(encoding="utf-8"))
    return sorted(set(config["hooks"]) - EVENTS)


def written_arm_config(tmp_path: Path) -> Path:
    path = tmp_path / "arms.json"
    hooks = [hook for arm in ARMS.values() for hook in arm]
    path.write_text(json.dumps(arm_settings(hooks, tmp_path / "registry.json")))
    return path


def test_bench_hook_config_uses_only_documented_events(tmp_path: Path) -> None:
    assert undocumented_events(written_arm_config(tmp_path)) == []


def test_watch_hook_config_uses_only_documented_events(tmp_path: Path) -> None:
    settings = tmp_path / "settings.json"
    add_muse_hook(settings, tmp_path / "registry.json", "python3")
    assert undocumented_events(settings) == []


def test_checker_flags_a_misspelled_event(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"hooks": {"PreToolUse": [], "PostToolBatches": []}}))
    assert undocumented_events(path) == ["PostToolBatches"]


def test_exec_argv_puts_options_before_session_id_and_prompt_last() -> None:
    argv = exec_argv("Continue the task.", "uuid-1")
    assert argv[:2] == ["muse", "exec"] and argv[-3:] == [
        "--session-id",
        "uuid-1",
        "Continue the task.",
    ]
    assert all(flag.startswith("--") for flag in argv[2:-3])
