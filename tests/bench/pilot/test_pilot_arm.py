import json
import subprocess
from pathlib import Path

from bench.pilot.arm import (
    arm_prompt,
    ArmUsage,
    claude_command,
    parse_arm_output,
    run_arm,
    scrubbed_env,
)

RESULT = {
    "type": "result",
    "is_error": False,
    "num_turns": 7,
    "duration_ms": 41000,
    "total_cost_usd": 0.42,
    "usage": {
        "input_tokens": 120,
        "output_tokens": 900,
        "cache_read_input_tokens": 50000,
        "cache_creation_input_tokens": 8000,
    },
}


def test_claude_command_pins_model_and_turns_off_web_settings_and_mcp() -> None:
    command = claude_command("claude-opus-5-5", 4.0)
    assert command[:2] == ["claude", "-p"]
    joined = " ".join(command)
    for flag in ("--restricted", "--strict-mcp-config", "--no-session-persistence"):
        assert flag in command
    assert "--model claude-opus-5-5" in joined
    assert "--disallowedTools WebFetch WebSearch" in joined
    assert "--output-format json" in joined and "--max-budget-usd 4.0" in joined


def test_arm_prompt_is_the_ticket_plus_one_fixed_instruction() -> None:
    prompt = arm_prompt("The poller never pauses.")
    assert prompt.startswith("The poller never pauses.")
    assert prompt == arm_prompt("The poller never pauses.")
    assert "knack" not in prompt.lower() and "reject" not in prompt.lower()


def test_parse_arm_output_reads_cost_tokens_and_turns() -> None:
    usage = parse_arm_output(json.dumps(RESULT))
    assert usage == ArmUsage(
        cost_usd=0.42,
        input_tokens=120,
        output_tokens=900,
        cache_read_tokens=50000,
        cache_creation_tokens=8000,
        turns=7,
        duration_ms=41000,
        is_error=False,
    )


def test_parse_arm_output_marks_garbage_as_an_error_not_a_crash() -> None:
    usage = parse_arm_output("not json")
    assert usage.is_error and usage.error and usage.cost_usd is None


def test_scrubbed_env_drops_secrets_and_knack_settings() -> None:
    env = {
        "PATH": "/bin",
        "GITHUB_TOKEN": "t",
        "KNACK_HOME": "/k",
        "BASETEN_API_KEY": "b",
    }
    assert scrubbed_env(env) == {"PATH": "/bin"}


def test_run_arm_runs_in_the_sandbox_with_the_prompt_on_stdin(tmp_path: Path) -> None:
    seen: dict[str, object] = {}

    def fake_run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        seen.update(kwargs, command=command)
        return subprocess.CompletedProcess(command, 0, json.dumps(RESULT), "")

    usage = run_arm(tmp_path, "ticket text", "claude-opus-5-5", runner=fake_run)
    assert seen["cwd"] == tmp_path and seen["input"] == arm_prompt("ticket text")
    assert usage.turns == 7


def test_run_arm_records_a_timeout_as_an_error(tmp_path: Path) -> None:
    def slow_run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(command, 1)

    usage = run_arm(tmp_path, "ticket", "claude-opus-5-5", runner=slow_run)
    assert usage.is_error and usage.error == "timeout"
