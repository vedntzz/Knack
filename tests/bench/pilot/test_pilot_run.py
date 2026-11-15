import json
from pathlib import Path

import pytest
from bench.pilot.arm import ArmUsage
from bench.pilot.candidates import file_sha256, PilotCandidate
from bench.pilot.run import PilotSetup, registered_hash, run_one, unregistered
from tests_pilot_support import BASE, REJECTED, TARGET, write_tree

USAGE = ArmUsage(cost_usd=0.5, turns=3, is_error=False)


class FakeJudge:
    model = "fake-judge"

    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.prompts: list[str] = []

    def ask(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.answer


class FakeBase:
    def file_at(self, repo: str, sha: str, path: str) -> str | None:
        return BASE if path == TARGET else None


def candidate(rule: Path) -> PilotCandidate:
    return PilotCandidate(
        id="demo-1",
        repo="acme/demo",
        pr=1,
        base_sha="a" * 40,
        head_sha="b" * 40,
        files=[TARGET],
        rejected_path="Block the loop with time.sleep",
        why_naive="first commit",
        evidence_url="u",
        evidence_quote="q",
        accepted_fix="await asyncio.sleep",
        ticket="The poller never pauses.",
        rule=rule.name,
        accepted_rule=rule.name,
        leak_terms=["sleep"],
    )


def agent_writing(text: str):  # noqa: ANN201
    def agent(sandbox: Path, ticket: str, model: str) -> ArmUsage:
        (sandbox / TARGET).write_text(text)
        return USAGE

    return agent


def setup(tmp_path: Path, rule: Path, text: str, answer: str) -> PilotSetup:
    return PilotSetup(
        work=tmp_path / "work",
        artifacts=tmp_path / "artifacts",
        rules=rule.parent,
        model="claude-opus-5-5",
        base=FakeBase(),
        cache=tmp_path / "cache",
        judge=FakeJudge(answer),
        agent=agent_writing(text),
    )


def test_run_one_scores_a_rule_hit_the_judge_confirms_as_a_repeat(
    tmp_path: Path, sleep_rule: Path
) -> None:
    ready = setup(tmp_path, sleep_rule, REJECTED, "took the rejected path: yes")
    record = run_one(candidate(sleep_rule), 0, ready)
    assert record.rule_hits == ["time.sleep(1)"] and record.blind == "yes"
    assert record.repeat and record.usage == USAGE and record.model == "claude-opus-5-5"


def test_run_one_judge_never_sees_the_rule_verdict(
    tmp_path: Path, sleep_rule: Path
) -> None:
    ready = setup(tmp_path, sleep_rule, REJECTED, "took the rejected path: no")
    record = run_one(candidate(sleep_rule), 0, ready)
    assert not record.repeat and record.rule_hits
    prompt = ready.judge.prompts[0]  # type: ignore[attr-defined]
    assert "time.sleep" in prompt and "pilot-sleep" not in prompt


def test_run_one_keeps_the_final_diff_as_an_artifact(
    tmp_path: Path, sleep_rule: Path
) -> None:
    ready = setup(tmp_path, sleep_rule, REJECTED, "took the rejected path: yes")
    record = run_one(candidate(sleep_rule), 2, ready)
    assert record.diff_path and "time.sleep(1)" in Path(record.diff_path).read_text()
    assert record.run == 2 and record.id == "demo-1"


def test_run_one_records_an_internal_error_instead_of_crashing(
    tmp_path: Path, sleep_rule: Path
) -> None:
    ready = setup(tmp_path, sleep_rule, REJECTED, "x")
    broken = candidate(sleep_rule).model_copy(update={"files": ["missing.py"]})
    record = run_one(broken, 0, ready)
    assert record.error and not record.repeat


def test_registered_hash_reads_the_candidates_hash_from_the_prereg(
    tmp_path: Path,
) -> None:
    prereg = tmp_path / "PREREG.md"
    prereg.write_text("x\n- `bench/pilot/candidates.jsonl` sha256 `" + "c" * 64 + "`\n")
    assert registered_hash(prereg) == "c" * 64


@pytest.mark.parametrize("matches", [True, False])
def test_unregistered_refuses_a_candidates_file_changed_after_prereg(
    tmp_path: Path, matches: bool
) -> None:
    candidates = tmp_path / "candidates.jsonl"
    candidates.write_text(json.dumps({"id": "x"}) + "\n")
    digest = file_sha256(candidates) if matches else "0" * 64
    prereg = tmp_path / "PREREG.md"
    prereg.write_text(f"- `bench/pilot/candidates.jsonl` sha256 `{digest}`\n")
    assert unregistered(candidates, prereg) is not matches


def test_fixture_base_serves_the_proven_base_tree(tmp_path: Path) -> None:
    from bench.pilot.run import FixtureBase

    write_tree(tmp_path / "demo-1" / "base", {TARGET: BASE})
    ready = FixtureBase(tmp_path, {"a" * 40: "demo-1"})
    assert ready.file_at("acme/demo", "a" * 40, TARGET) == BASE
    assert ready.file_at("acme/demo", "a" * 40, "nope.py") is None
    assert ready.file_at("acme/demo", "f" * 40, TARGET) is None


class DownJudge:
    model = "down-judge"

    def ask(self, prompt: str) -> str:
        raise RuntimeError("Model version is deactivated")


def test_judge_ready_is_true_when_the_judge_answers() -> None:
    from bench.pilot.run import judge_ready

    assert judge_ready(FakeJudge("ok")) is True


def test_judge_ready_is_false_when_the_judge_errors() -> None:
    from bench.pilot.run import judge_ready

    assert judge_ready(DownJudge()) is False
