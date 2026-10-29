import re

from pydantic import BaseModel, ConfigDict

from knack.pipeline.extract import strip_fences
from knack.pipeline.models import Decision
from knack.pipeline.ports import Spark
from knack.pipeline.prove import feedback, passed, Proof, ProofCase, prove

MAX_ATTEMPTS = 5
TOP_LEVEL_ID = re.compile(r"^id:.*$", re.MULTILINE)
PROMPT = """You compile an engineering decision into an ast-grep rule (YAML) that flags code violating it.
The rule must flag code that goes against the decision, including its rejected alternative,
and must NOT flag code that follows the decision or unrelated code.
ast-grep notes: top-level keys are id, language (python), severity (error), message, rule.
Rule operators: pattern, kind, regex, inside, has, all, any, not.
Relational operators (inside, has) only check the direct parent/child by default (stopBy: neighbor);
use stopBy: end to search all ancestors/descendants.
Do not match identifiers introduced by this PR; match the structure of the violation.
Use id: compiled-rule. Return ONLY the YAML. No prose, no code fences.

DECISION:
{decision}

CODE BEFORE THE DECISION (violates it):
{before}

CODE AFTER THE DECISION (follows it):
{after}
"""


class Attempt(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rule: str
    number: int
    proof: Proof

    @property
    def proven(self) -> bool:
        return passed(self.proof)


def compile_prompt(decision: Decision, before: str, after: str) -> str:
    shown = decision.model_dump_json(indent=2)
    return PROMPT.format(decision=shown, before=before, after=after)


def compile_rule(
    spark: Spark, case: ProofCase, prompt: str, number: int = 1
) -> Attempt:
    # Each failed rule and its verifier results go back to Spark, up to MAX_ATTEMPTS.
    rule = rule_text(spark.ask(prompt))
    attempt = Attempt(rule=rule, number=number, proof=prove(rule, case))
    if attempt.proven or number == MAX_ATTEMPTS:
        return attempt
    return compile_rule(spark, case, retry_prompt(prompt, attempt, case), number + 1)


def retry_prompt(prompt: str, attempt: Attempt, case: ProofCase) -> str:
    results = feedback(attempt.proof, case)
    return f"{prompt}\n\nYOUR PREVIOUS RULE:\n{attempt.rule}\n\nVERIFIER RESULTS:\n{results}\nFix the rule."


def rule_text(answer: str) -> str:
    return strip_fences(answer, "yaml")


def with_rule_id(rule_yaml: str, rule_id: str) -> str:
    # The guard reports the rule by this id, so each installed rule gets its own.
    return TOP_LEVEL_ID.sub(f"id: {rule_id}", rule_yaml, count=1)
