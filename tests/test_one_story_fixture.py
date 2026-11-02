import json
import re
from pathlib import Path
from typing import Any

from knack.receipts.chain import load_receipts, verify_chain

REPO_ROOT = Path(__file__).parents[1]
FROZEN = REPO_ROOT / "mockups" / "fixtures" / "one_story"
SPIKE = REPO_ROOT / "spikes" / "one_story_live.md"
CAPTURED_EVENT = REPO_ROOT / "tests" / "hooks" / "fixtures" / "edit_event.json"
STEPS = ["block", "argue_hold", "argue_escalate", "resolve", "corrected", "verify"]
SPARK_OPEN = ("meta-models/muse-spark-open-1026", "inference.baseten.co")

Json = dict[str, Any]


def frozen_json(name: str) -> Json:
    found: Json = json.loads((FROZEN / name).read_text())
    return found


def rulings() -> list[Json]:
    lines = (FROZEN / "rulings.jsonl").read_text().splitlines()
    return [json.loads(line) for line in lines]


def spike_line(label: str) -> str:
    # The spike's "- <label>: <value>." lines are the single source for these numbers.
    found = re.search(rf"^- {label}: (.+)\.$", SPIKE.read_text(), re.M)
    assert found, label
    return found.group(1)


def test_frozen_story_is_live_and_ran_every_step_cleanly() -> None:
    story = frozen_json("story.json")
    assert story["models"] == "live"
    assert [(s["name"], s["exit"]) for s in story["steps"]] == [(n, 0) for n in STEPS]


def test_frozen_rulings_hold_then_escalate_with_spark_open_asked() -> None:
    assert [r["decision"] for r in rulings()] == ["hold", "escalate"]
    asked = [(m["model"], m["host"]) for m in rulings()[1]["models"]]
    assert SPARK_OPEN in asked and all(m["trace_id"] for m in rulings()[1]["models"])


def test_frozen_rulings_name_the_agent_from_the_captured_payload() -> None:
    agent = json.loads(CAPTURED_EVENT.read_text())["model"]
    assert [r["agent"] for r in rulings()] == [agent, agent]


def test_frozen_receipts_verify_intact_and_hold_the_uphold() -> None:
    path = FROZEN / "receipts.jsonl"
    assert verify_chain(path).broken_line is None
    upheld = [r.resolution for r in load_receipts(path) if r.resolution]
    assert [(u.action, u.of) for u in upheld] == [
        ("uphold", rulings()[0]["receipt_hash"])
    ]


def test_frozen_story_keeps_traces_and_edit_snapshots() -> None:
    assert (FROZEN / "traces" / "self_checks.jsonl").is_file()
    assert len(list((FROZEN / "traces" / "steps").iterdir())) == len(STEPS)
    assert len(list((FROZEN / "edits").glob("*.json"))) == 2


def test_spike_states_this_runs_latency_from_the_frozen_story() -> None:
    measured = frozen_json("latency.json")
    verdicts = [measured[k]["guard_ms"] for k in ("block", "corrected")]
    trips = [measured["wall_ms"][k] for k in ("block", "corrected")]
    expected = "{} ms (block), {} ms (corrected edit)"
    assert spike_line("Guard verdict, this run") == expected.format(
        *(f"{v:.1f}" for v in verdicts)
    )
    assert spike_line("Hook round trip, this run") == expected.format(
        *(f"{t:.0f}" for t in trips)
    )
