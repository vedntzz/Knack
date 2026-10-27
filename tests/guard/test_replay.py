import subprocess
import sys
from pathlib import Path

from knack.contracts.models import Root, Verdict

REPLAY = Path(__file__).parent / "fixtures/replay"
RULE = Path(__file__).parents[2] / "knack/guard/rules/no-alias-sort-keys.yml"
ROOT_JSON = REPLAY / "root_75025.json"
KNACK = Path(sys.executable).parent / "knack"


def run_cli_on_run3(cwd: Path) -> tuple[int, Verdict]:
    # Runs the installed knack CLI on the replayed agent edit.
    file = str(REPLAY / "run3_public_dags.py")
    args = [str(KNACK), "guard", "check", file, "--rule", str(RULE)]
    args += ["--root", str(ROOT_JSON), "--json"]
    done = subprocess.run(args, capture_output=True, text=True, timeout=10, cwd=cwd)
    return done.returncode, Verdict.model_validate_json(done.stdout)


def test_run3_is_blocked_citing_state_and_start_date(tmp_path: Path) -> None:
    exit_code, verdict = run_cli_on_run3(tmp_path)
    assert exit_code == 1
    assert verdict.allowed is False
    assert '"state"' in verdict.reason
    assert '"start_date"' in verdict.reason


def test_run3_reason_cites_who_quote_and_source(tmp_path: Path) -> None:
    root = Root.model_validate_json(ROOT_JSON.read_text())
    _, verdict = run_cli_on_run3(tmp_path)
    assert root.decided_by in verdict.reason
    assert root.quote in verdict.reason
    assert str(root.source_url) in verdict.reason


def test_run3_latency_under_100ms(tmp_path: Path) -> None:
    _, verdict = run_cli_on_run3(tmp_path)
    print(f"run3 replay latency_ms={verdict.latency_ms:.2f}")
    assert verdict.latency_ms < 100
