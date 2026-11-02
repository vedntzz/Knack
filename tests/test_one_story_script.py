import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from knack.receipts.chain import human_allow, load_receipts, Receipt, verify_chain

REPO_ROOT = Path(__file__).parents[1]
SCRIPT = REPO_ROOT / "scripts" / "one_story.sh"
RULE_ID = "airflow-75025"
HOLD_OBJECTION = (
    "Let me alias state and start_date onto DagRun.state and DagRun.start_date"
    " so the advertised names keep working."
)
ESCALATE_OBJECTION = (
    "A customer dashboard pins order_by=state in a contract that runs until March;"
    " removing it breaks them."
)
UPHOLD_REASON = (
    "The decision stands; the customer can sort by last_run_state"
    " and last_run_start_date."
)
STEPS = ["block", "argue_hold", "argue_escalate", "resolve", "corrected", "verify"]
ALIAS_LINES = [
    '                    "state": DagRun.state,',
    '                    "start_date": DagRun.start_date,',
]
# Measured each run: hashes chain a timestamp, times and latencies are this run's.
MEASURED = [
    re.compile(r"[0-9a-f]{64}"),
    re.compile(r"[0-9a-f]{12}(?=:)"),
    re.compile(r"\d+(\.\d+)? ms"),
]

Json = dict[str, Any]


def run_story(home: Path, **env: str) -> subprocess.CompletedProcess[str]:
    # CI's shape: an empty HOME, a bare PATH, no credential of any kind.
    base = {"HOME": str(home), "PATH": "/usr/bin:/bin", "PYTHON": sys.executable}
    base |= {"KNACK_STORY_MODELS": "fake", "KNACK_STORY_BY": "story test"}
    home.mkdir(parents=True, exist_ok=True)
    command = ["bash", str(SCRIPT), str(home / "out")]
    return subprocess.run(
        command, capture_output=True, text=True, timeout=300, env=base | env
    )


@pytest.fixture(scope="module")
def story(tmp_path_factory: pytest.TempPathFactory) -> Path:
    home = tmp_path_factory.mktemp("story")
    done = run_story(home)
    assert done.returncode == 0, done.stdout + done.stderr
    (home / "stdout.txt").write_text(done.stdout)
    return home


def out(home: Path) -> Path:
    return home / "out"


def manifest(home: Path) -> Json:
    found: Json = json.loads((out(home) / "story.json").read_text())
    return found


def chain(home: Path) -> list[Receipt]:
    return load_receipts(out(home) / "receipts.jsonl")


def rulings(home: Path) -> list[Json]:
    lines = (out(home) / "rulings.jsonl").read_text().splitlines()
    return [json.loads(line) for line in lines]


def latency(home: Path) -> Json:
    found: Json = json.loads((out(home) / "latency.json").read_text())
    return found


def deny(home: Path) -> Receipt:
    # The agent's block; the person's uphold also records a deny, but blocks nothing new.
    denies = [r for r in chain(home) if r.decision == "deny" and r.resolution is None]
    assert len(denies) == 1
    return denies[0]


def guarded(home: Path) -> list[Receipt]:
    # The #75025 rule's receipts, in chain order.
    return [r for r in chain(home) if r.rule_id == RULE_ID]


def unmeasured(text: str) -> str:
    for pattern in MEASURED:
        text = pattern.sub("<measured>", text)
    return text


def test_story_runs_every_step_in_order(story: Path) -> None:
    steps = manifest(story)["steps"]
    assert [step["name"] for step in steps] == STEPS
    assert all(step["exit"] == 0 for step in steps)


def test_every_step_answers_the_same_block_receipt(story: Path) -> None:
    block = deny(story).hash
    assert [r["receipt_hash"] for r in rulings(story)] == [block, block]
    resolved = [r for r in chain(story) if r.resolution]
    assert [r.resolution.of for r in resolved if r.resolution] == [block]
    assert manifest(story)["block_receipt"] == block


def test_argue_holds_then_escalates_on_the_two_objections(story: Path) -> None:
    found = [(r["objection"], r["decision"]) for r in rulings(story)]
    assert found == [(HOLD_OBJECTION, "hold"), (ESCALATE_OBJECTION, "escalate")]


def test_resolve_upholds_the_block_in_a_receipt_chained_after_it(story: Path) -> None:
    receipts = guarded(story)
    block = deny(story)
    upheld = next(r for r in receipts if r.resolution)
    assert receipts.index(upheld) > receipts.index(block)
    assert upheld.resolution and upheld.resolution.of == block.hash
    assert (upheld.decision, upheld.resolution.action) == ("deny", "uphold")
    assert (upheld.resolution.reason, upheld.resolution.by) == (
        UPHOLD_REASON,
        "story test",
    )


def test_uphold_grants_no_exception_for_the_blocked_edit(story: Path) -> None:
    block = deny(story)
    assert block.edit_sha256 is not None
    path = out(story) / "receipts.jsonl"
    assert human_allow(path, RULE_ID, block.edit_sha256) is None
    step = manifest(story)["steps"][STEPS.index("resolve")]
    assert "upheld by story test" in step["stdout"]
    assert "must-pass" not in step["stdout"]


def test_corrected_edit_passes_the_hook_on_its_own_merits(story: Path) -> None:
    passed = guarded(story)[-1]
    assert (passed.decision, passed.resolution) == ("allow", None)
    assert passed.edit_sha256 != deny(story).edit_sha256
    step = manifest(story)["steps"][STEPS.index("corrected")]
    assert step["stdout"] == ""


def test_corrected_edit_is_the_blocked_edit_with_lines_135_136_deleted(
    story: Path,
) -> None:
    blocked, corrected = (snapshot(story, r) for r in (deny(story), guarded(story)[-1]))
    lines = blocked["after"].splitlines(keepends=True)
    assert [line.rstrip("\n") for line in lines[134:136]] == ALIAS_LINES
    assert corrected["after"] == "".join(lines[:134] + lines[136:])


def snapshot(home: Path, receipt: Receipt) -> Json:
    found: Json = json.loads(
        (out(home) / "edits" / f"{receipt.edit_sha256}.json").read_text()
    )
    return found


def test_whole_chain_verifies_intact(story: Path) -> None:
    assert verify_chain(out(story) / "receipts.jsonl").broken_line is None
    step = manifest(story)["steps"][STEPS.index("verify")]
    assert step["stdout"].endswith("chain intact")


def test_rulings_name_every_model_asked_and_the_agent(story: Path) -> None:
    for ruling in rulings(story):
        assert ruling["models"], ruling
        assert "agent" in ruling
    escalated = [m["model"] for m in rulings(story)[1]["models"]]
    assert escalated == ["fake-spark", "fake-spark-open"]


def test_fake_models_never_claim_a_real_model_or_host(story: Path) -> None:
    models = [m for r in rulings(story) for m in r["models"]]
    assert all(m["model"].startswith("fake-") for m in models)
    assert all(m["host"] == "no network (scripts/one_story_fakes.py)" for m in models)
    assert manifest(story)["models"] == "fake"


def test_latency_comes_from_this_runs_receipts(story: Path) -> None:
    measured = latency(story)
    block, passed = deny(story), guarded(story)[-1]
    assert measured["block"]["receipt"] == block.hash
    assert measured["block"]["guard_ms"] == block.latency_ms
    assert measured["corrected"]["receipt"] == passed.hash
    assert measured["corrected"]["guard_ms"] == passed.latency_ms
    assert set(measured["wall_ms"]) == set(STEPS)


def test_a_second_run_measures_itself_and_prints_the_same_story(
    story: Path, tmp_path: Path
) -> None:
    again = run_story(tmp_path)
    assert again.returncode == 0, again.stdout + again.stderr
    assert latency(tmp_path)["block"]["receipt"] == deny(tmp_path).hash
    assert deny(tmp_path).hash != deny(story).hash
    first = (story / "stdout.txt").read_text().replace(str(story), "<home>")
    second = again.stdout.replace(str(tmp_path), "<home>")
    assert unmeasured(first) == unmeasured(second)


def test_output_keeps_traces_and_edit_snapshots(story: Path) -> None:
    folder = out(story)
    assert (folder / "traces" / "self_checks.jsonl").is_file()
    steps = sorted(p.name for p in (folder / "traces" / "steps").iterdir())
    assert steps == [f"{n}_{name}.txt" for n, name in enumerate(STEPS, 1)]
    for receipt in (deny(story), guarded(story)[-1]):
        assert snapshot(story, receipt)["file"].endswith("public/dags.py")


def test_story_never_writes_the_callers_home(story: Path) -> None:
    assert not (story / ".knack").exists()
    assert not (story / ".config").exists()


def test_live_run_without_a_model_key_stops_before_writing(tmp_path: Path) -> None:
    done = run_story(tmp_path, KNACK_STORY_MODELS="live")
    assert done.returncode != 0
    assert "MODEL_API_KEY" in done.stderr
    assert not (tmp_path / "out").exists()


def test_refuses_to_replace_a_folder_that_is_not_a_story(tmp_path: Path) -> None:
    (tmp_path / "out").mkdir(parents=True)
    (tmp_path / "out" / "keep.txt").write_text("mine")
    done = run_story(tmp_path)
    assert done.returncode != 0
    assert (tmp_path / "out" / "keep.txt").read_text() == "mine"


def test_script_sandboxes_home_and_names_no_credential() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'export HOME="$WORK/home"' in text
    assert 'export KNACK_HOME="$HOME/.knack"' in text
