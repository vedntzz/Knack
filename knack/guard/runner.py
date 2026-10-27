import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, PositiveInt

AST_GREP = Path(sys.executable).parent / "ast-grep"
TIMEOUT_SECONDS = 2
# ast-grep exits 1 when it finds error-severity matches; that is still a successful scan.
SUCCESS_EXIT_CODES = (0, 1)


class RuleMatch(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str
    file: str
    line: PositiveInt
    matched_text: str


class GuardRunnerError(Exception):
    pass


def scan_file_with_rule(file_path: Path, rule_path: Path) -> list[RuleMatch]:
    return _parse_matches(_run_ast_grep(file_path, rule_path))


def _run_ast_grep(file_path: Path, rule_path: Path) -> str:
    args = [str(AST_GREP), "scan", "--rule", str(rule_path), "--json", str(file_path)]
    done = _invoke_with_timeout(args)
    if done.returncode not in SUCCESS_EXIT_CODES:
        raise GuardRunnerError(f"ast-grep exited {done.returncode}: {done.stderr}")
    return done.stdout


def _invoke_with_timeout(args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args, capture_output=True, text=True, timeout=TIMEOUT_SECONDS
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise GuardRunnerError(f"ast-grep did not run: {error}") from error


def _parse_matches(stdout: str) -> list[RuleMatch]:
    try:
        return [_to_rule_match(raw) for raw in json.loads(stdout)]
    except (ValueError, KeyError, TypeError) as error:
        raise GuardRunnerError(f"ast-grep returned malformed JSON: {error}") from error


def _to_rule_match(raw: dict[str, Any]) -> RuleMatch:
    # ast-grep lines are 0-based; editors and Leaf.line are 1-based.
    line = raw["range"]["start"]["line"] + 1
    return RuleMatch(
        rule_id=raw["ruleId"], file=raw["file"], line=line, matched_text=raw["text"]
    )
