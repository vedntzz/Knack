import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

RULE = Path(__file__).parents[2] / "knack/guard/rules/no-alias-sort-keys.yml"
FIXTURES = Path(__file__).parent / "fixtures"
AST_GREP = Path(sys.executable).parent / "ast-grep"


def scan(fixture: str) -> list[dict[str, Any]]:
    # Runs the real ast-grep CLI against one fixture, as the guard will.
    args = [
        str(AST_GREP),
        "scan",
        "--rule",
        str(RULE),
        "--json",
        str(FIXTURES / fixture),
    ]
    done = subprocess.run(args, capture_output=True, text=True)
    return json.loads(done.stdout)


@pytest.mark.parametrize("fixture", ["pre_fix.py", "rejected_alias.py"])
def test_aliased_sort_keys_are_flagged(fixture: str) -> None:
    assert len(scan(fixture)) > 0


@pytest.mark.parametrize(
    "fixture", ["fixed.py", "legit_last_run_state.py", "unrelated_state.py"]
)
def test_clean_code_produces_zero_matches(fixture: str) -> None:
    assert scan(fixture) == []


def test_violating_produces_exactly_two_errors() -> None:
    errors = [m for m in scan("violating.py") if m["severity"] == "error"]
    assert len(errors) == 2


def test_flags_point_at_the_aliased_keys() -> None:
    texts = sorted(m["text"] for m in scan("pre_fix.py"))
    assert texts == ['"start_date"', '"state"']
