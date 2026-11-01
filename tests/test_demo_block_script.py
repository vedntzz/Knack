import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parents[1]
SCRIPT = REPO_ROOT / "scripts" / "demo_block.sh"
ROOT_75025 = REPO_ROOT / "data" / "roots" / "airflow" / "75025.json"
PAYLOAD_HEADER = "== deny payload =="
# Measured each run: the two latencies and the receipt hash, which chains a timestamp.
MEASURED = [
    re.compile(r"(?<=guard verdict: )\d+\.\d+(?= ms)"),
    re.compile(r"(?<=hook round trip: )\d+(?= ms)"),
    re.compile(r"(?<=/verdict/)[0-9a-f]{64}"),
]
LATENCY_LINES = [
    re.compile(r"^guard verdict: \d+\.\d+ ms ", re.M),
    re.compile(r"^hook round trip: \d+ ms ", re.M),
]


def run_demo(home: Path) -> subprocess.CompletedProcess[str]:
    # CI's shape: an empty HOME, a bare PATH, no credential of any kind.
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin", "PYTHON": sys.executable}
    return subprocess.run(
        ["bash", str(SCRIPT)], capture_output=True, text=True, timeout=120, env=env
    )


def deny_envelope(out: str) -> dict[str, str]:
    # The line under the header is the hook's stdout, verbatim.
    lines = out.splitlines()
    payload: dict[str, dict[str, str]] = json.loads(
        lines[lines.index(PAYLOAD_HEADER) + 1]
    )
    return payload["hookSpecificOutput"]


def unmeasured(out: str) -> str:
    for pattern in MEASURED:
        out = pattern.sub("<measured>", out)
    return out


def test_demo_denies_citing_75025_and_the_verbatim_quote(tmp_path: Path) -> None:
    done = run_demo(tmp_path)
    assert done.returncode == 0, done.stdout + done.stderr
    inner = deny_envelope(done.stdout)
    assert inner["hookEventName"] == "PreToolUse"
    assert inner["permissionDecision"] == "deny"
    reason = inner["permissionDecisionReason"]
    assert "https://github.com/apache/airflow/pull/75025" in reason
    assert f'Quote: "{json.loads(ROOT_75025.read_text())["quote"]}"' in reason


def test_demo_prints_both_measured_latencies(tmp_path: Path) -> None:
    out = run_demo(tmp_path).stdout
    assert [bool(p.search(out)) for p in LATENCY_LINES] == [True, True]


def test_demo_output_is_identical_every_run_but_the_measurements(
    tmp_path: Path,
) -> None:
    first = run_demo(tmp_path / "a").stdout
    second = run_demo(tmp_path / "b").stdout
    assert unmeasured(first) == unmeasured(second)
    assert unmeasured(first) != first


def test_demo_leaves_the_real_home_and_names_no_credential() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'export HOME="$WORK/home"' in text
    assert "unset GITHUB_TOKEN MODEL_API_KEY BASETEN_API_KEY KNACK_REGISTRY" in text


def test_demo_pins_knack_home_inside_its_sandbox_home() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'export KNACK_HOME="$HOME/.knack"' in text
