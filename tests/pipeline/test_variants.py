import json
from pathlib import Path

import pytest
from conftest import COMPLIANT, GATHER_DECISION, VIOLATIONS
from knack.pipeline.models import Decision
from knack.pipeline.variants import (
    generate_variants,
    parse_variants,
    variant_files,
    variant_prompt,
)

GOOD = {"violations": ["x = 1\n", "y = 2\n", "z = 3\n"], "compliant": COMPLIANT}


class ScriptedSpark:
    # Replies with each answer in turn and records the prompts it got.
    model = "scripted"

    def __init__(self, *answers: str) -> None:
        self.answers, self.prompts = list(answers), list[str]()

    def ask(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.answers[len(self.prompts) - 1]


def test_three_of_each_kind_that_parse_are_accepted() -> None:
    variants = parse_variants("```json\n" + json.dumps(GOOD) + "\n```")
    assert variants.violations == GOOD["violations"]
    assert variants.compliant == COMPLIANT


@pytest.mark.parametrize(
    "bad",
    [
        {**GOOD, "violations": GOOD["violations"][:2]},
        {**GOOD, "compliant": ["def broken(:\n", "b = 2\n", "c = 3\n"]},
        {"violations": GOOD["violations"]},
    ],
)
def test_wrong_count_unparseable_or_missing_kind_is_rejected(
    bad: dict[str, list[str]],
) -> None:
    with pytest.raises(ValueError):
        parse_variants(json.dumps(bad))


def test_invalid_answer_is_retried() -> None:
    spark = ScriptedSpark("not json", json.dumps(GOOD))
    assert generate_variants(spark, "p").compliant == COMPLIANT
    assert len(spark.prompts) == 2


def test_gives_up_after_three_invalid_answers() -> None:
    with pytest.raises(RuntimeError):
        generate_variants(ScriptedSpark("no", "no", "no"), "p")


def test_variants_are_written_once_and_reused(tmp_path: Path) -> None:
    spark = ScriptedSpark(json.dumps(GOOD))
    first = variant_files(tmp_path, "prompt", spark)
    assert variant_files(tmp_path, "prompt", spark) == first
    assert len(spark.prompts) == 1
    assert first["variant-violation"]["violation_2.py"].read_text() == "y = 2\n"
    assert sorted(first["variant-compliant"]) == [
        "compliant_1.py",
        "compliant_2.py",
        "compliant_3.py",
    ]


def test_prompt_asks_for_fresh_names_real_api_and_no_copying() -> None:
    decision = Decision.model_validate(GATHER_DECISION)
    prompt = variant_prompt(decision, "BEFORE CODE", "AFTER CODE")
    assert prompt.startswith("You write test cases")
    assert "BEFORE CODE" in prompt and "AFTER CODE" in prompt
    assert "Read blobs one at a time in a loop" in prompt
    assert "new identifiers" in prompt and "different structure" in prompt
    assert "never define stand-in" in prompt.lower() and "do not copy" in prompt.lower()


def test_violation_fixtures_parse() -> None:
    assert (
        len(parse_variants(json.dumps({**GOOD, "violations": VIOLATIONS})).violations)
        == 3
    )
