# #74150: the v3 rule with its whole-module branch (FallbackModel + MaskingCapability, no await) dropped,
# re-run through every check and both held-out sets. Installs only if every check and gate passes.
import shutil
import sys
from pathlib import Path

import yaml

from knack.home import knack_home
from knack.pipeline.compile import with_rule_id
from knack.pipeline.heldout import score_heldout
from knack.pipeline.prove import failed_checks, ProofCase, prove, verifier_sides
from knack.pipeline.variants import KINDS
from spikes.heldout_cross import side

KNACK = Path(__file__).parent.parent
SRC = KNACK / "spikes/batch/apache-airflow/src/74150"
V3 = KNACK / "spikes/batch/apache-airflow/rules/74150.v3.yml"
HOME_REG = knack_home() / "registries/apache-airflow"
MAIN, OLD = HOME_REG / "work/tree", HOME_REG / "work/release-3.3.2"
INSTALL = [KNACK / "data/rules/airflow/74150.yml", HOME_REG / "rules/74150.yml"]


def without_module_branch(v3_text):
    # Branch 1 is the whole-module text check; branch 2, the executor call, becomes the whole rule.
    rule = yaml.safe_load(v3_text)
    module, executor = rule["rule"]["any"]
    assert module["all"][0] == {"kind": "module"} and "kind" not in str(executor)
    return yaml.safe_dump({**rule, "rule": executor}, sort_keys=False, width=200)


def cached(folder):
    return {s: {p.name: p for p in sorted((SRC / folder).glob(f"{k}_*.py"))} for s, k in KINDS.items()}


def build_case(work):
    base, head = side("apache-airflow", 74150, "base"), side("apache-airflow", 74150, "head")
    sides = verifier_sides(74150, base, head, work, cached("variants"))
    return ProofCase(sides=sides, changed=sorted(base), tree=MAIN, old_ref="3.3.2", old_tree=OLD)


def report(rule, case):
    # Per-side flag counts, so each check's result is visible, not just the failures.
    proof = prove(rule, case)
    for name in dict.fromkeys(r.side for r in proof.rows):
        rows = [r for r in proof.rows if r.side == name]
        print(f"  {name}: {sum(bool(r.matches) for r in rows)}/{len(rows)} files flagged")
    print(f"  main FPs: {len(proof.false_positives)} | 3.3.2 FPs: {len(proof.old_release.false_positives)}")
    return failed_checks(proof)


def gates(rule):
    same = score_heldout(rule, cached("variants-heldout"), "muse-spark-1.3")
    cross = score_heldout(rule, cached("variants-heldout-cross"), "meta-models/muse-spark-open-1026")
    return {name: (h.passed and not h.error, f"{h.caught}/{h.violations} caught, {h.allowed}/{h.compliant} allowed")
            for name, h in (("held-out same-model", same), ("held-out cross-model", cross))}


def install(rule, backup):
    backup.mkdir(parents=True, exist_ok=True)
    for i, target in enumerate(INSTALL):
        shutil.copy2(target, backup / f"{i}-{target.parent.name}-74150.yml")
        target.write_text(with_rule_id(rule, "airflow-74150").rstrip("\n") + "\n")


def run(label, rule, case):
    print(f"{label}:")
    failed = report(rule, case)
    results = gates(rule)
    for name, (ok, detail) in results.items():
        print(f"  GATE {name}: {'pass' if ok else 'FAIL'} | {detail}")
    print(f"  CHECKS: {failed or 'all pass'}", flush=True)
    return not failed and all(ok for ok, _ in results.values())


def main():
    # argv: work dir (renamed copies and the install backup go here).
    work = Path(sys.argv[1])
    case, v3 = build_case(work), V3.read_text()
    run("BASELINE v3 (both branches)", v3, case)
    trimmed = without_module_branch(v3)
    (work / "74150.v3-trimmed.yml").write_text(trimmed)
    if not run("TRIMMED v3 (executor branch only)", trimmed, case):
        print("RESULT: a check failed; nothing installed")
        return
    install(trimmed, work / "backup")
    print(f"RESULT: every check passes; installed to {', '.join(map(str, INSTALL))}")


if __name__ == "__main__":
    main()
