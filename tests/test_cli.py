import json
import subprocess
import sys
from pathlib import Path

import pytest
from knack.cli import main
from knack.contracts.models import Verdict

RULE = Path(__file__).parents[1] / "knack/guard/rules/no-alias-sort-keys.yml"
FIXTURES = Path(__file__).parent / "guard/fixtures"
KNACK = Path(sys.executable).parent / "knack"


def write_confirmed_root(directory: Path) -> Path:
    # Test-only root; values are illustrative, not quoted from a real thread.
    root = {
        "id": "root-001",
        "title": "Sort keys are column names",
        "decision": "Sort keys must be real column names, never aliases.",
        "why": "Aliased sort keys let callers sort on columns they cannot see.",
        "decided_by": "Alice Chen",
        "source_url": "https://github.com/example/repo/pull/42",
        "quote": "Do not alias sort keys; map them to columns explicitly.",
        "status": "Confirmed",
    }
    path = directory / "root.json"
    path.write_text(json.dumps(root))
    return path


def guard_args(fixture: str, root: Path) -> list[str]:
    return [
        "guard",
        "check",
        str(FIXTURES / fixture),
        "--rule",
        str(RULE),
        "--root",
        str(root),
    ]


@pytest.fixture(autouse=True)
def run_in_tmp(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Keeps .knack/guard_errors.log out of the repo.
    monkeypatch.chdir(tmp_path)


def test_pre_fix_with_confirmed_root_exits_1_and_prints_block(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(guard_args("pre_fix.py", write_confirmed_root(tmp_path)))
    assert exit_code == 1
    assert "Knack blocked this edit." in capsys.readouterr().out


def test_fixed_exits_0(tmp_path: Path) -> None:
    assert main(guard_args("fixed.py", write_confirmed_root(tmp_path))) == 0


def test_json_output_parses_as_verdict(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main([*guard_args("pre_fix.py", write_confirmed_root(tmp_path)), "--json"])
    verdict = Verdict.model_validate_json(capsys.readouterr().out)
    assert verdict.allowed is False


def test_missing_root_file_exits_0_as_guard_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    args = [*guard_args("pre_fix.py", tmp_path / "missing.json"), "--json"]
    assert main(args) == 0
    verdict = Verdict.model_validate_json(capsys.readouterr().out)
    assert verdict.reason.startswith("guard-error")


def test_installed_entry_point_blocks_pre_fix(tmp_path: Path) -> None:
    args = [str(KNACK), *guard_args("pre_fix.py", write_confirmed_root(tmp_path))]
    done = subprocess.run(args, capture_output=True, text=True, timeout=10)
    assert done.returncode == 1
    assert "Knack blocked this edit." in done.stdout
