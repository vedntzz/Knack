# Held-out variant score: a second variant set per PR, sampled apart from the training set and never shown to the compiler.
from batch_compile import (Batch, decision_with_rejection, evaluate, fetch_side, joined_source, pr_meta, repo_parser,
                           targets)
from batch_variants import KINDS, variant_files, variant_prompt
from compile_spike import ask_spark

# Spark has no seed parameter ("unknown parameter `seed`"); at temperature 1.0 a fresh call is an independent sample
HELDOUT_DIR = "variants-heldout"


def heldout_dir(batch, number):
    return batch.src / str(number) / HELDOUT_DIR


def variant_score(rule_yaml, variants):
    # (violations flagged, compliant allowed, any ast-grep error)
    rows = evaluate(rule_yaml, variants)
    caught = sum(1 for side, _, matches, _ in rows if side == "variant-violation" and matches)
    allowed = sum(1 for side, _, matches, _ in rows if side == "variant-compliant" and not matches)
    return caught, allowed, any(error for *_, error in rows)


def variant_pass(score):
    caught, allowed, error = score
    return caught >= 2 and allowed == 3 and not error


def identical_modules(train, heldout):
    # held-out modules that repeat a training module, ignoring surrounding whitespace
    seen = {path.read_text().strip() for side in train.values() for path in side.values()}
    return sum(1 for side in heldout.values() for path in side.values() if path.read_text().strip() in seen)


def saved_variants(out):
    return {side: {path.name: path for path in sorted(out.glob(f"{prefix}_*.py"))} for side, prefix in KINDS.values()}


def heldout_variants(batch, number):
    # same prompt as the training set, so only the sample differs
    meta = pr_meta(batch, number)
    base, head = fetch_side(batch, number, meta, "base"), fetch_side(batch, number, meta, "head")
    prompt = variant_prompt(decision_with_rejection(batch, number), joined_source(base), joined_source(head))
    return variant_files(heldout_dir(batch, number), prompt, ask_spark)


def score_line(batch, number):
    heldout, train = heldout_variants(batch, number), saved_variants(batch.src / str(number) / "variants")
    rule = batch.rules / f"{number}.yml"
    score = variant_score(rule.read_text(), heldout) if rule.exists() else None
    verdict = "no rule" if score is None else f"{score[0]}/3 caught, {score[1]}/3 allowed{' ERROR' if score[2] else ''}"
    return f"#{number}: {verdict}{' PASS' if score and variant_pass(score) else ''} | identical to training: {identical_modules(train, heldout)}/6"


def safe_score_line(batch, number):
    try:
        return score_line(batch, number)
    except Exception as error:  # one PR's network failure should not sink the batch; rerun picks up from the cache
        return f"#{number}: ERROR {error!r}"


if __name__ == "__main__":
    batch = Batch(repo_parser("score each PR's final rule on a held-out variant set").parse_args().repo)
    for number in targets(batch):
        print(safe_score_line(batch, number), flush=True)
