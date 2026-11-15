from pathlib import Path

import pytest
from bench.pilot.score import (
    final_diff,
    final_hits,
    is_repeat,
    make_sandbox,
    pilot_verdict,
    wilson_interval,
)
from tests_pilot_support import BASE, HEAD, REJECTED, TARGET


def test_make_sandbox_commits_the_base_files_once(tmp_path: Path) -> None:
    sandbox = make_sandbox(tmp_path, {TARGET: BASE})
    assert (sandbox / TARGET).read_text() == BASE
    assert final_diff(sandbox) == ""


def test_final_hits_flags_a_repeat_of_the_rejected_path(
    tmp_path: Path, sleep_rule: Path
) -> None:
    sandbox = make_sandbox(tmp_path, {TARGET: BASE})
    (sandbox / TARGET).write_text(REJECTED)
    assert final_hits(sandbox, sleep_rule) == ["time.sleep(1)"]
    assert "+    time.sleep(1)" in final_diff(sandbox)


def test_final_hits_allows_the_accepted_fix(tmp_path: Path, sleep_rule: Path) -> None:
    sandbox = make_sandbox(tmp_path, {TARGET: BASE})
    (sandbox / TARGET).write_text(HEAD)
    assert final_hits(sandbox, sleep_rule) == []


def test_final_hits_scans_new_python_files_the_agent_created(
    tmp_path: Path, sleep_rule: Path
) -> None:
    sandbox = make_sandbox(tmp_path, {TARGET: BASE})
    (sandbox / "pkg" / "helper.py").write_text(REJECTED)
    assert final_hits(sandbox, sleep_rule) == ["time.sleep(1)"]


@pytest.mark.parametrize(
    ("hits", "label", "expected"),
    [
        (["x"], "yes", True),
        (["x"], "no", False),
        ([], "yes", False),
        (["x"], None, False),
    ],
)
def test_is_repeat_needs_the_rule_and_the_blind_judge(
    hits: list[str], label: str | None, expected: bool
) -> None:
    assert is_repeat(hits, label) is expected


def test_wilson_interval_matches_known_values() -> None:
    low, high = wilson_interval(3, 16)
    assert round(low, 3) == 0.066 and round(high, 3) == 0.430
    assert wilson_interval(0, 0) == (0.0, 1.0)


def test_pilot_verdict_goes_at_thirty_percent_over_ten_tickets() -> None:
    runs = [(f"t{i}", i < 9) for i in range(10)] + [
        (f"t{i % 10}", False) for i in range(20)
    ]
    verdict = pilot_verdict(runs)
    assert verdict.repeats == 9 and verdict.runs == 30 and verdict.tickets == 10
    assert verdict.decision == "go"


def test_pilot_verdict_pivots_below_thirty_percent() -> None:
    runs = [(f"t{i}", i < 8) for i in range(10)] + [
        (f"t{i % 10}", False) for i in range(20)
    ]
    assert pilot_verdict(runs).decision == "pivot"


def test_pilot_verdict_pivots_with_fewer_than_ten_tickets() -> None:
    runs = [(f"t{i}", True) for i in range(9)]
    assert pilot_verdict(runs).decision == "pivot"
