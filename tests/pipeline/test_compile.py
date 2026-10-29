from pathlib import Path

from conftest import GATHER_DECISION, MEMORIZED, STRUCTURAL
from knack.pipeline.compile import (
    compile_prompt,
    compile_rule,
    MAX_ATTEMPTS,
    rule_text,
    with_rule_id,
)
from knack.pipeline.models import Decision
from test_prove import case


class QueueSpark:
    # Serves rules in order, repeating the last; records prompts.
    model = "queue"

    def __init__(self, *rules: str) -> None:
        self.rules, self.prompts = list(rules), list[str]()

    def ask(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.rules[min(len(self.prompts), len(self.rules)) - 1]


def prompt() -> str:
    return compile_prompt(Decision.model_validate(GATHER_DECISION), "OLD", "NEW")


def test_prompt_carries_decision_code_and_generality_rule() -> None:
    text = prompt()
    assert text.startswith("You compile") and "OLD" in text and "NEW" in text
    assert "Read blobs one at a time in a loop" in text and "stopBy: end" in text
    assert "Do not match identifiers introduced by this PR" in text


def test_rule_text_strips_yaml_fences() -> None:
    assert rule_text("```yaml\nid: x\n```") == "id: x"


def test_with_rule_id_replaces_only_the_top_level_id() -> None:
    rule = with_rule_id(STRUCTURAL, "widgets-9")
    assert rule.startswith("id: widgets-9\n") and rule.count("id:") == 1


def test_proven_on_first_attempt_asks_once(tmp_path: Path) -> None:
    spark = QueueSpark(STRUCTURAL)
    attempt = compile_rule(spark, case(tmp_path), prompt())
    assert attempt.number == 1 and attempt.rule == STRUCTURAL.strip()
    assert len(spark.prompts) == 1


def test_failed_rule_and_verifier_results_feed_the_next_attempt(tmp_path: Path) -> None:
    spark = QueueSpark(MEMORIZED, STRUCTURAL)
    attempt = compile_rule(spark, case(tmp_path), prompt())
    assert attempt.number == 2
    assert (
        MEMORIZED.strip() in spark.prompts[1]
        and "rename-head must flag 0" in spark.prompts[1]
    )
    assert spark.prompts[1].endswith("Fix the rule.")


def test_gives_up_after_max_attempts(tmp_path: Path) -> None:
    spark = QueueSpark(MEMORIZED)
    attempt = compile_rule(spark, case(tmp_path), prompt())
    assert attempt.number == MAX_ATTEMPTS == len(spark.prompts) == 5
    assert attempt.proof.rows and not attempt.proven
