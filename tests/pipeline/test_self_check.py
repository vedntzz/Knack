import json
from pathlib import Path

import pytest
from knack.miss.cases import cases_dir, EditCase, load_cases, ModelAnswer, save_case
from knack.miss.loop import LoopOutcome
from knack.miss.selfcheck import (
    ask_judge,
    Asked,
    load_checks,
    prompt_sha256,
    self_checks_path,
    settle,
    Settle,
)

YES = '{"takes_rejected_path": true, "why": "it gathers every read"}'
NO = '{"takes_rejected_path": false, "why": "it reads one at a time"}'


class FakeJudge:
    # One fixed answer, or an error; records every prompt it was asked.
    def __init__(self, model: str, answer: str | Exception) -> None:
        self.model, self.answer, self.prompts = model, answer, list[str]()

    def ask(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


class FakeLoop:
    # Stands in for record_and_recompile: saves the cases, then reports kept.
    def __init__(self, registry: Path, error: Exception | None = None) -> None:
        self.registry, self.error, self.runs = registry, error, list[list[EditCase]]()

    def __call__(self, cases: list[EditCase]) -> LoopOutcome:
        self.runs.append(cases)
        for case in cases:
            save_case(cases_dir(self.registry), case)
        if self.error:
            raise self.error
        return LoopOutcome(rule_id=cases[0].rule_id, recompiled=False, installed=False)


def takes(text: str) -> bool:
    return json.loads(text)["takes_rejected_path"] is True


def case() -> EditCase:
    return EditCase(
        kind="must-fail",
        rule_id="widgets-9",
        file="pkg/loader.py",
        before="x = 1\n",
        after="x = 2\n",
        source="watch PR #9 (auto)",
    )


def asked(*answers: tuple[str, str]) -> Asked:
    judged = [ask_judge(FakeJudge(m, a), "the prompt", takes) for m, a in answers]
    return Asked(trigger="watch", question="takes the rejected path", answers=judged)


def settled(tmp_path: Path, ask: Asked, loop: FakeLoop | None = None) -> FakeLoop:
    registry = tmp_path / "registry.json"
    runner = loop or FakeLoop(registry)
    lines = list[str]()
    settle(
        Settle(registry, self_checks_path(registry), runner, lines.append), case(), ask
    )
    return runner


def test_a_judge_answer_keeps_the_verbatim_text_model_and_prompt_hash() -> None:
    answer = ask_judge(FakeJudge("spark", YES), "the prompt", takes)
    assert answer == ModelAnswer(
        model="spark", yes=True, answer=YES, prompt_sha256=prompt_sha256("the prompt")
    )


def test_a_judge_error_is_a_no_with_the_error_kept() -> None:
    answer = ask_judge(FakeJudge("spark", TimeoutError("slow")), "p", takes)
    assert not answer.yes and answer.answer == "error: TimeoutError: slow"


def test_an_unreadable_answer_is_a_no() -> None:
    assert not ask_judge(FakeJudge("spark", "I think so!"), "p", takes).yes


def test_both_yes_records_the_case_with_both_answers_and_runs_the_loop(
    tmp_path: Path,
) -> None:
    loop = settled(tmp_path, asked(("spark", YES), ("spark-open", YES)))
    [[ran]] = loop.runs
    assert [a.model for a in ran.answers] == ["spark", "spark-open"]
    [saved] = load_cases(cases_dir(tmp_path / "registry.json"), "widgets-9")
    assert saved.answers == ran.answers and saved.key == case().key


def test_both_yes_is_logged_with_the_recorded_case_key(tmp_path: Path) -> None:
    settled(tmp_path, asked(("spark", YES), ("spark-open", YES)))
    [check] = load_checks(self_checks_path(tmp_path / "registry.json"))
    assert (check.trigger, check.rule_id, check.file) == (
        "watch",
        "widgets-9",
        "pkg/loader.py",
    )
    assert check.case_key == case().key and len(check.answers) == 2


def test_disagreement_is_logged_only(tmp_path: Path) -> None:
    loop = settled(tmp_path, asked(("spark", YES), ("spark-open", NO)))
    assert loop.runs == []
    assert load_cases(cases_dir(tmp_path / "registry.json"), "widgets-9") == []
    [check] = load_checks(self_checks_path(tmp_path / "registry.json"))
    assert check.case_key is None
    assert [a.answer for a in check.answers] == [YES, NO]


def test_two_yeses_from_one_model_are_not_agreement(tmp_path: Path) -> None:
    loop = settled(tmp_path, asked(("spark", YES), ("spark", YES)))
    assert loop.runs == []


def test_a_case_already_recorded_is_not_run_again(tmp_path: Path) -> None:
    loop = FakeLoop(tmp_path / "registry.json")
    both = asked(("spark", YES), ("spark-open", YES))
    settled(tmp_path, both, loop)
    settled(tmp_path, both, loop)
    assert len(loop.runs) == 1
    assert len(load_checks(self_checks_path(tmp_path / "registry.json"))) == 2


def test_a_loop_error_is_logged_and_the_case_stays_recorded(tmp_path: Path) -> None:
    registry = tmp_path / "registry.json"
    loop = FakeLoop(registry, RuntimeError("compiler down"))
    settled(tmp_path, asked(("spark", YES), ("spark-open", YES)), loop)
    assert len(load_cases(cases_dir(registry), "widgets-9")) == 1


def test_a_torn_check_line_is_skipped(tmp_path: Path) -> None:
    path = self_checks_path(tmp_path / "registry.json")
    settled(tmp_path, asked(("spark", NO), ("spark-open", NO)))
    with path.open("a") as handle:
        handle.write('{"torn"\n')
    assert len(load_checks(path)) == 1


@pytest.mark.parametrize("module", ["knack.hooks.pretool_guard", "knack.guard.check"])
def test_the_guard_verdict_path_never_loads_a_model_or_self_check(module: str) -> None:
    import subprocess
    import sys

    probe = f"import sys, {module}; print(sorted(m for m in sys.modules if m.startswith('knack.')))"
    done = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True)
    loaded = done.stdout
    banned = ["selfcheck", "second", "spark", "dispute", "knack.miss"]
    assert done.returncode == 0 and not [b for b in banned if b in loaded]
