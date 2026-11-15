import json
import os
import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

ARM_TIMEOUT_SECONDS = 1800
MAX_BUDGET_USD = 5.0
# The only words the agent gets besides the ticket; frozen in PREREG-PILOT.md.
INSTRUCTION = "Fix this in the code in the current directory."
SECRET_NAMES = ("GITHUB_TOKEN", "BASETEN_API_KEY", "MODEL_API_KEY")
Runner = Callable[..., subprocess.CompletedProcess[str]]


class ArmUsage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    cost_usd: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_creation_tokens: int | None = None
    turns: int | None = None
    duration_ms: int | None = None
    is_error: bool
    error: str | None = None


def claude_command(model: str, budget_usd: float = MAX_BUDGET_USD) -> list[str]:
    # Plain Claude Code: no user/project settings, hooks, MCP, skills or web; edits auto-accepted.
    isolation = ["--restricted", "--strict-mcp-config", "--disable-slash-commands"]
    web_off = ["--disallowedTools", "WebFetch", "WebSearch"]
    output = ["--output-format", "json", "--no-session-persistence"]
    limits = ["--permission-mode", "acceptEdits", "--max-budget-usd", str(budget_usd)]
    return ["claude", "-p", "--model", model, *isolation, *web_off, *output, *limits]


def arm_prompt(ticket: str) -> str:
    return f"{ticket}\n\n{INSTRUCTION}"


def scrubbed_env(env: Mapping[str, str]) -> dict[str, str]:
    # The agent never sees bench keys or Knack configuration.
    kept = {k: v for k, v in env.items() if k not in SECRET_NAMES}
    return {k: v for k, v in kept.items() if not k.startswith("KNACK")}


def parse_arm_output(stdout: str) -> ArmUsage:
    try:
        return _usage_from(json.loads(stdout))
    except (ValueError, TypeError, AttributeError) as error:
        return ArmUsage(is_error=True, error=f"unreadable output: {error}")


def run_arm(
    sandbox: Path, ticket: str, model: str, runner: Runner = subprocess.run
) -> ArmUsage:
    # One headless Claude Code session in the sandbox; a timeout is an error, not a crash.
    try:
        done = runner(
            claude_command(model),
            cwd=sandbox,
            input=arm_prompt(ticket),
            capture_output=True,
            text=True,
            timeout=ARM_TIMEOUT_SECONDS,
            env=scrubbed_env(os.environ),
        )
    except subprocess.TimeoutExpired:
        return ArmUsage(is_error=True, error="timeout")
    return parse_arm_output(done.stdout)


def _usage_from(result: dict[str, Any]) -> ArmUsage:
    usage: dict[str, Any] = result.get("usage") or {}
    return ArmUsage(
        cost_usd=result.get("total_cost_usd"),
        input_tokens=usage.get("input_tokens"),
        output_tokens=usage.get("output_tokens"),
        cache_read_tokens=usage.get("cache_read_input_tokens"),
        cache_creation_tokens=usage.get("cache_creation_input_tokens"),
        turns=result.get("num_turns"),
        duration_ms=result.get("duration_ms"),
        is_error=bool(result.get("is_error")),
    )
