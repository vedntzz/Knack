import re
import subprocess
from pathlib import Path

WORKFLOW = Path(__file__).parents[1] / ".github/workflows/knack-guard.yml"
# The changed-file filter: grep -Ev '<pattern>' on the PR's changed .py list.
FILTER = re.compile(r"grep -Ev '([^']+)'")
FIXTURES = [
    "scripts/fixtures/75025/base/airflow-core/src/airflow/api_fastapi/core_api/routes/public/dags.py",
    "tests/guard/fixtures/violating.py",
    "tests/fixtures/model_output.py",
    "tests/hooks/fixtures/edit.py",
]
REAL_CODE = [
    "knack/guard/check.py",
    "knack/fixtures/loader.py",
    "scripts/e2e_fakes.py",
    "tests/test_fixtures.py",
    "tests/guard/test_replay.py",
    "tests/foo_fixtures/x.py",
    "src/tests/fixtures/x.py",
]


def kept(paths: list[str]) -> list[str]:
    # The workflow's own pattern, run through grep as the workflow runs it.
    match = FILTER.search(WORKFLOW.read_text(encoding="utf-8"))
    assert match, "no grep -Ev filter in the workflow"
    lines = "".join(f"{p}\n" for p in paths)
    done = subprocess.run(
        ["grep", "-Ev", match.group(1)], input=lines, capture_output=True, text=True
    )
    return done.stdout.splitlines()


def test_fixture_paths_are_not_guarded() -> None:
    assert kept(FIXTURES) == []


def test_real_code_is_still_guarded() -> None:
    assert kept(REAL_CODE) == REAL_CODE
