import os
import subprocess
import sys
from pathlib import Path

from knack.contracts.models import Root

REPO = Path(__file__).parents[1]
SCRIPT = REPO / ".github/scripts/guard_changed.sh"
RULE = REPO / "knack/guard/rules/no-alias-sort-keys.yml"
ROOT_JSON = REPO / "tests/guard/fixtures/replay/root_75025.json"
FIXTURES = REPO / "tests/guard/fixtures"
KNACK = Path(sys.executable).parent / "knack"


def run_script(cwd: Path, *files: Path) -> subprocess.CompletedProcess[str]:
    # Runs the CI loop with the installed knack, as the workflow does.
    args = ["bash", str(SCRIPT), str(RULE), str(ROOT_JSON), *map(str, files)]
    env = {**os.environ, "KNACK": str(KNACK)}
    return subprocess.run(
        args, capture_output=True, text=True, timeout=30, cwd=cwd, env=env
    )


def test_no_changed_files_passes(tmp_path: Path) -> None:
    assert run_script(tmp_path).returncode == 0


def test_only_allowed_files_pass(tmp_path: Path) -> None:
    done = run_script(tmp_path, FIXTURES / "fixed.py", FIXTURES / "unrelated_state.py")
    assert done.returncode == 0


def test_one_blocked_file_fails_and_prints_citation(tmp_path: Path) -> None:
    run3 = FIXTURES / "replay/run3_public_dags.py"
    done = run_script(tmp_path, FIXTURES / "fixed.py", run3)
    root = Root.model_validate_json(ROOT_JSON.read_text())
    assert done.returncode == 1
    assert "Knack blocked this edit." in done.stdout
    assert root.decided_by in done.stdout
    assert root.quote in done.stdout
    assert str(root.source_url) in done.stdout


def test_blocked_output_names_the_file(tmp_path: Path) -> None:
    run3 = FIXTURES / "replay/run3_public_dags.py"
    assert str(run3) in run_script(tmp_path, run3).stdout


def test_every_file_is_checked_after_a_block(tmp_path: Path) -> None:
    run3 = FIXTURES / "replay/run3_public_dags.py"
    done = run_script(tmp_path, run3, FIXTURES / "fixed.py")
    assert str(FIXTURES / "fixed.py") in done.stdout
