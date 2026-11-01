# Recompile #75025 with the real agent edit (tests/hooks/fixtures/edit_75025_alias.json) as a guard edit
# the rule must deny, on top of every existing check. Installs only if every check and gate passes.
import json
import os
import shutil
import sys
from pathlib import Path

from knack.pipeline.compile import Attempt, compile_prompt, compile_rule, retry_prompt, rule_text, with_rule_id
from knack.home import knack_home, user_home
from knack.pipeline.heldout import score_heldout
from knack.pipeline.prove import (
    _rule_file,
    _tree_false_positives,
    failed_checks,
    GuardEdit,
    ProofCase,
    prove,
    verifier_sides,
)
from knack.pipeline.sources import joined_source
from knack.pipeline.spark import SparkApi
from knack.pipeline.variants import KINDS

KNACK = Path(__file__).parent.parent
SRC = KNACK / "spikes/batch/apache-airflow/src/75025"
HOME_REG = knack_home() / "registries/apache-airflow"
MAIN, OLD = HOME_REG / "work/tree", HOME_REG / "work/release-3.3.2"
SANDBOX_DAGS = user_home() / "Documents/knack-sandbox/routes/public/dags.py"
DAGS = "airflow-core/src/airflow/api_fastapi/core_api/routes/public/dags.py"
FIXTURE = KNACK / "tests/hooks/fixtures/edit_75025_alias.json"
INSTALL = [KNACK / "data/rules/airflow/75025.yml", HOME_REG / "rules/75025.yml"]


class LoggedSpark(SparkApi):
    # The compiler's own client; each answer is kept so every attempt can be reported.
    answers: list[str] = []

    def ask(self, prompt: str) -> str:
        answer = super().ask(prompt)
        self.answers.append(answer)
        return answer


def decision():
    from spikes.heldout_cross import decision as first_with_rejected
    return first_with_rejected("apache-airflow", 75025)


def side(which):
    from spikes.heldout_cross import side as cached_side
    return cached_side("apache-airflow", 75025, which)


def cached(folder):
    # Read straight from disk: variant_files would regenerate a set with no authors.json.
    return {s: {p.name: p for p in sorted((SRC / folder).glob(f"{k}_*.py"))} for s, k in KINDS.items()}


def guard_edit(work):
    # The sandbox's base dags.py, then the agent's find -> replace applied once, as the hook does.
    fix = json.loads(FIXTURE.read_text())
    before_text = SANDBOX_DAGS.read_text()
    assert before_text == (SRC / "base" / DAGS).read_text() and before_text.count(fix["find"]) == 1
    paths = {k: work / "guard-edit" / k / DAGS for k in ("before", "after")}
    for key, text in (("before", before_text), ("after", before_text.replace(fix["find"], fix["replace"], 1))):
        paths[key].parent.mkdir(parents=True, exist_ok=True)
        paths[key].write_text(text)
    return {DAGS: GuardEdit(**paths)}


def build_case(work):
    base, head = side("base"), side("head")
    sides = verifier_sides(75025, base, head, work, cached("variants"))
    return ProofCase(sides=sides, changed=sorted(base), tree=MAIN, old_ref="3.3.2", old_tree=OLD,
                     guard_edits=guard_edit(work)), base, head


def gates(rule):
    # Never shown to the compiler: v2-10-stable must have no match at all, and both held-out sets must pass.
    with _rule_file(rule) as path:
        v210, error = _tree_false_positives(path, Path(sys.argv[1]), [])
    same = score_heldout(rule, cached("variants-heldout"), "muse-spark-1.3")
    cross = score_heldout(rule, cached("variants-heldout-cross"), "meta-models/muse-spark-open-1026")
    return {"v2-10-stable": (not v210 and not error, error or v210),
            "held-out same-model": (same.passed, f"{same.caught}/{same.violations} caught, {same.allowed}/{same.compliant} allowed"),
            "held-out cross-model": (cross.passed, f"{cross.caught}/{cross.violations} caught, {cross.allowed}/{cross.compliant} allowed")}


def install(rule, backup):
    backup.mkdir(parents=True, exist_ok=True)
    for i, target in enumerate(INSTALL):
        shutil.copy2(target, backup / f"{i}-{target.parent.name}-75025.yml")
        target.write_text(with_rule_id(rule, "airflow-75025").rstrip("\n") + "\n")


def resumed_prompt(case, first_prompt, prior):
    # The prompt compile_rule would have sent next: each saved attempt re-proved and appended in order.
    prompt = first_prompt
    for n in range(1, 6):
        rule = (prior / f"attempt-{n}.yml").read_text().rstrip("\n")
        attempt = Attempt(rule=rule, number=n, proof=prove(rule, case))
        print(f"REPLAYED ATTEMPT {n}:", failed_checks(attempt.proof) or "all checks pass", flush=True)
        prompt = retry_prompt(prompt, attempt, case)
    return prompt


def main():
    # argv: v2-10-stable tree, work dir, and optionally a prior work dir whose 5 attempts to continue from.
    work = Path(sys.argv[2])
    case, base, head = build_case(work)
    first = compile_prompt(decision(), joined_source(base), joined_source(head))
    resume = len(sys.argv) > 3
    if not resume:
        print("BASELINE installed rule:", failed_checks(prove(INSTALL[0].read_text(), case)) or "all checks pass", flush=True)
    prompt = resumed_prompt(case, first, Path(sys.argv[3])) if resume else first
    offset = 5 if resume else 0
    spark = LoggedSpark(os.environ["MODEL_API_KEY"])
    final = compile_rule(spark, case, prompt)
    for n, answer in enumerate(spark.answers, offset + 1):
        rule = rule_text(answer)
        (work / f"attempt-{n}.yml").write_text(rule + "\n")
        print(f"ATTEMPT {n}:", failed_checks(prove(rule, case)) or "all checks pass", flush=True)
    finish(final, work, offset + final.number)


def finish(final, work, number):
    if not final.proven:
        print(f"RESULT: not proven through attempt {number}; nothing installed")
        return
    results = gates(final.rule)
    for name, (ok, detail) in results.items():
        print(f"GATE {name}: {'pass' if ok else 'FAIL'} | {detail}")
    if all(ok for ok, _ in results.values()):
        install(final.rule, work / "backup")
        print(f"RESULT: proven on attempt {number}, all gates pass; installed to {', '.join(map(str, INSTALL))}")
    else:
        print(f"RESULT: proven on attempt {number} but a gate failed; nothing installed")


if __name__ == "__main__":
    main()
