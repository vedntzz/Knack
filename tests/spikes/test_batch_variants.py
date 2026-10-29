import json
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

import pytest
from conftest import SpikeLoader

GOOD = {"violations": ["x = 1\n", "y = 2\n", "z = 3\n"], "compliant": ["a = 1\n", "b = 2\n", "c = 3\n"]}


@pytest.fixture
def spike(load_spike: SpikeLoader) -> ModuleType:
    return load_spike("batch_variants")


def spark_reply(answer: object) -> dict[str, Any]:
    text = answer if isinstance(answer, str) else json.dumps(answer)
    return {"output": [{"type": "message", "content": [{"text": text}]}]}


def scripted(*answers: object) -> tuple[Callable[[str], dict[str, Any]], list[str]]:
    # a fake Spark that replies with each answer in turn and records the prompts it got
    replies, prompts = [spark_reply(a) for a in answers], list[str]()

    def ask(prompt: str) -> dict[str, Any]:
        prompts.append(prompt)
        return replies[len(prompts) - 1]

    return ask, prompts


def test_three_of_each_kind_that_parse_are_accepted(spike: ModuleType) -> None:
    assert spike.checked_variants(GOOD) == GOOD


@pytest.mark.parametrize("bad", [
    {**GOOD, "violations": GOOD["violations"][:2]},
    {**GOOD, "compliant": ["def broken(:\n", "b = 2\n", "c = 3\n"]},
    {"violations": GOOD["violations"]},
])
def test_wrong_count_unparseable_or_missing_kind_is_rejected(
    spike: ModuleType, bad: dict[str, list[str]]
) -> None:
    with pytest.raises((ValueError, KeyError, SyntaxError)):
        spike.checked_variants(bad)


def test_invalid_answer_is_retried(spike: ModuleType) -> None:
    ask, prompts = scripted("not json", GOOD)
    assert spike.generate_variants("p", ask) == GOOD and len(prompts) == 2


def test_gives_up_after_three_invalid_answers(spike: ModuleType) -> None:
    ask, _ = scripted("no", "no", "no")
    with pytest.raises(RuntimeError):
        spike.generate_variants("p", ask)


def test_variants_are_written_once_and_reused(spike: ModuleType, tmp_path: Path) -> None:
    ask, prompts = scripted(GOOD)
    first = spike.variant_files(tmp_path, "prompt", ask)
    second = spike.variant_files(tmp_path, "prompt", ask)
    assert first == second and len(prompts) == 1
    assert first["variant-violation"]["violation_2.py"].read_text() == "y = 2\n"
    assert sorted(first["variant-compliant"]) == ["compliant_1.py", "compliant_2.py", "compliant_3.py"]


def test_prompt_asks_for_fresh_names_and_structure(spike: ModuleType) -> None:
    prompt = spike.variant_prompt({"d": 1}, "BEFORE CODE", "AFTER CODE")
    assert "BEFORE CODE" in prompt and "AFTER CODE" in prompt and '"d": 1' in prompt
    assert "new identifiers" in prompt and "different structure" in prompt and "do not copy" in prompt.lower()


def test_prompt_forbids_stand_ins_for_the_decisions_api(spike: ModuleType) -> None:
    # generality means new names around the real API, not a fake copy of the API
    prompt = spike.variant_prompt({}, "", "")
    assert "never define stand-in" in prompt.lower() and "reviewer" in prompt
