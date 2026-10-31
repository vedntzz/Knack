# KN-35b: compliant_3.py counts as compliant (decided 2026-10-30), so the first Spark Open set moves into
# training, a fresh Spark Open set becomes the held-out set, and #75025 compiling continues from attempt 6.
import json
import os
import shutil
import sys
from pathlib import Path

from knack.pipeline.compile import Attempt, compile_prompt, compile_rule, retry_prompt, rule_text
from knack.pipeline.heldout import score_heldout
from knack.pipeline.prove import failed_checks, prove
from knack.pipeline.sources import joined_source
from knack.pipeline.spark_open import SparkOpenApi
from knack.pipeline.variants import variant_files, variant_prompt
from spikes.recompile_75025 import (
    build_case,
    cached,
    decision,
    finish,
    gates,
    LoggedSpark,
    resumed_prompt,
    SRC,
)
import spikes.recompile_75025 as first_round

TRAIN = SRC / "variants-train-kn35"
FRESH = "variants-heldout-cross-2"
SPARK, OPEN = "muse-spark-1.3", "meta-models/muse-spark-open-1026"


def build_training():
    # Spark's training set as violation/compliant 1-3, the first Spark Open set as 4-6; originals stay put.
    TRAIN.mkdir(exist_ok=True)
    authors = {}
    for folder, shift, author in (("variants", 0, SPARK), ("variants-heldout-cross", 3, OPEN)):
        for path in sorted((SRC / folder).glob("*_*.py")):
            kind, n = path.stem.split("_")
            name = f"{kind}_{int(n) + shift}.py"
            shutil.copy2(path, TRAIN / name)
            authors[name] = author
    (TRAIN / "authors.json").write_text(json.dumps(authors, indent=2) + "\n")


def fresh_heldout(base, head):
    # Same prompt and writer as the first Spark Open set; the directory is never given to the compiler.
    prompt = variant_prompt(decision(), joined_source(base), joined_source(head))
    sides = variant_files(SRC / FRESH, prompt, SparkOpenApi(os.environ["BASETEN_API_KEY"]))
    seen = {p.read_text().strip() for d in ("variants", "variants-heldout", "variants-heldout-cross")
            for p in (SRC / d).glob("*_*.py")}
    overlap = sum(p.read_text().strip() in seen for p in (SRC / FRESH).glob("*_*.py"))
    print(f"FRESH HELD-OUT {FRESH}: {sum(map(len, sides.values()))} files, identical to an earlier set: {overlap}", flush=True)


def per_set(rule):
    # The verifier pools both training sets into one side; the old bar (>=2/3 caught, 3/3 allowed) holds per set.
    rows = {}
    for label, folder in (("training Spark", "variants"), ("training Spark Open (moved)", "variants-heldout-cross")):
        held = score_heldout(rule, cached(folder), label)
        rows[label] = (held.passed, f"{held.caught}/{held.violations} caught, {held.allowed}/{held.compliant} allowed")
    return rows


def all_gates(rule):
    # v2-10-stable and same-model held-out as before; cross-model held-out is now the fresh set.
    results = {k: v for k, v in gates(rule).items() if k != "held-out cross-model"}
    cross = score_heldout(rule, cached(FRESH), OPEN)
    results["held-out cross-model (fresh)"] = (cross.passed, f"{cross.caught}/{cross.violations} caught, {cross.allowed}/{cross.compliant} allowed")
    return {**per_set(rule), **results}


def main():
    # argv: v2-10-stable tree, work dir, first-round work dir (attempts 1-5), attempt-6 work dir.
    work, round1, round2 = Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
    build_training()
    old_case, base, head = build_case(work / "old")
    fresh_heldout(base, head)
    new_case = old_case.model_copy(update={"sides": {**old_case.sides, **cached("variants-train-kn35")}})
    prompt = resumed_prompt(old_case, compile_prompt(decision(), joined_source(base), joined_source(head)), round1)
    rule6 = (round2 / "attempt-6.yml").read_text().rstrip("\n")
    attempt6 = Attempt(rule=rule6, number=6, proof=prove(rule6, new_case))
    print("ATTEMPT 6 under the new training set:", failed_checks(attempt6.proof) or "all checks pass", flush=True)
    spark = LoggedSpark(os.environ["MODEL_API_KEY"])
    final = compile_rule(spark, new_case, retry_prompt(prompt, attempt6, new_case))
    for n, answer in enumerate(spark.answers, 7):
        rule = rule_text(answer)
        (work / f"attempt-{n}.yml").write_text(rule + "\n")
        print(f"ATTEMPT {n}:", failed_checks(prove(rule, new_case)) or "all checks pass", flush=True)
    first_round.gates = all_gates
    finish(final, work, 6 + final.number)


if __name__ == "__main__":
    main()
