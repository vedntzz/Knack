import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from knack.contracts.models import Root
from knack.hooks.pretool_guard import rule_name
from knack.miss.cases import cases_dir, EditCase, load_cases, save_case
from knack.pipeline.compile import (
    Attempt,
    compile_prompt,
    compile_rule,
    retry_prompt,
    with_rule_id,
)
from knack.pipeline.heldout import HeldOut, holds_install_bar, score_heldout
from knack.pipeline.models import Alternative, Decision, PullRequest
from knack.pipeline.ports import GitHub, Spark
from knack.pipeline.prove import (
    edit_checks,
    failed_checks,
    GuardEdit,
    Proof,
    ProofCase,
    prove,
    Sides,
    verifier_sides,
)
from knack.pipeline.releases import last_release_before
from knack.pipeline.select import pull_request
from knack.pipeline.sources import fetch_side, joined_source
from knack.pipeline.variants import saved_variants, variant_files, variant_prompt
from knack.roots.store import load_roots
from knack.walk.registry import load_registry, Registry, RegistryEntry, repo_data

Log = Callable[[str], None]
PR_NUMBER = re.compile(r"/pull/(\d+)")
HELDOUT_SETS = ("same", "cross")
FRESH = "fresh cross-model"
# Case field on ProofCase -> the kind of case it holds.
EDIT_FIELDS = {"guard_edits": "must-fail", "guard_allows": "must-pass"}
CASES_HOLD = "every must-fail edit denied, every must-pass edit allowed"
ALREADY = "the current rule already denies every must-fail edit and allows every must-pass edit"


class UnknownRule(Exception):
    pass


@dataclass(frozen=True)
class Loop:
    github: GitHub
    compiler: Spark
    # The other model: it writes the training variants and the fresh cross-model set.
    writer: Spark
    registry: Path
    # Committed held-out sets: <heldout>/<pr>/same and <heldout>/<pr>/cross.
    heldout: Path
    work: Path
    log: Log


@dataclass(frozen=True)
class Target:
    rule_id: str
    rule_path: Path
    repo: str
    pr: PullRequest
    decision: Decision


@dataclass(frozen=True)
class Rules:
    # The recompiled rule, and the installed one whose recall it must reach.
    new: str
    old: str


@dataclass(frozen=True)
class Built:
    case: ProofCase
    compile_prompt: str
    variant_prompt: str


class GateResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    passed: bool
    detail: str


class LoopOutcome(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str
    recompiled: bool
    installed: bool
    attempts: int = 0
    gates: list[GateResult] = []
    # The recompiled rule, installed or not.
    rule: str | None = None
    rule_path: Path | None = None
    # Where the recompiled rule was saved for review, installed or not.
    candidate_path: Path | None = None

    @property
    def reasons(self) -> list[str]:
        return [f"{gate.name}: {gate.detail}" for gate in self.gates if not gate.passed]


def default_loop(
    github: GitHub, compiler: Spark, writer: Spark, registry: Path, log: Log
) -> Loop:
    # The held-out sets and work folder knack miss uses when none are given.
    places = (default_heldout(registry), default_work(registry))
    return Loop(github, compiler, writer, registry, *places, log)


def default_heldout(registry: Path) -> Path:
    # data/registry/fastapi.json or a home registry for fastapi/fastapi -> data/heldout/fastapi.
    return repo_data(registry, "heldout")


def default_work(registry: Path) -> Path:
    name = f"{registry.resolve().parent.name}-{registry.stem}"
    return Path.home() / ".knack" / "cache" / "miss" / name


def record_and_recompile(loop: Loop, cases: list[EditCase]) -> LoopOutcome:
    # Each new case is kept for good, then its rule is recompiled against all of them.
    for case in cases:
        path = save_case(cases_dir(loop.registry), case)
        loop.log(f"recorded {case.kind} case {case.name} for {case.rule_id} -> {path}")
    return recompile(loop, cases[0].rule_id)


def recompile(loop: Loop, rule_id: str) -> LoopOutcome:
    # The old rule is proven on every case first; only a failing one is recompiled.
    target = find_target(loop, rule_id)
    built = _built(loop, target, load_cases(cases_dir(loop.registry), rule_id))
    old = _old_attempt(target, built.case)
    if edit_checks(old.proof.rows):
        return _recompiled(loop, target, built, old)
    return _nothing_to_do(rule_id)


def find_target(loop: Loop, rule_id: str) -> Target:
    registry = load_registry(loop.registry)
    entry = _entry(registry, rule_id, loop.registry)
    root = _speaking_root(registry, entry)
    pr = pull_request(loop.github, registry.repo, _pr_number(root))
    return Target(rule_id, entry.rule, registry.repo, pr, decision_of(root))


def decision_of(root: Root) -> Decision:
    # The root's verbatim rejected alternative is what the rule enforces.
    rejected = root.rejected_alternative or ""
    alternative = Alternative(alternative=rejected, quote=root.quote, verbatim=True)
    fields = {"decision": root.decision, "why": root.why, "decided_by": root.decided_by}
    return Decision(rejected_alternatives=[alternative], **fields)


def outcome_lines(outcome: LoopOutcome) -> list[str]:
    # One line per gate, the saved candidate, then what happened to the rule.
    gates = [
        f"{'PASS' if g.passed else 'FAIL'} {g.name}: {g.detail}" for g in outcome.gates
    ]
    saved = (
        [f"candidate rule: {outcome.candidate_path}"] if outcome.candidate_path else []
    )
    return gates + saved + [_verdict_line(outcome)]


def _verdict_line(outcome: LoopOutcome) -> str:
    if not outcome.recompiled:
        return f"kept {outcome.rule_id}: nothing to recompile"
    if outcome.installed:
        return f"installed {outcome.rule_id} -> {outcome.rule_path} ({outcome.attempts} attempt(s))"
    return f"kept the old {outcome.rule_id}: {len(outcome.reasons)} gate(s) failed"


def _already() -> GateResult:
    return GateResult(name="cases", passed=True, detail=ALREADY)


def _entry(registry: Registry, rule_id: str, path: Path) -> RegistryEntry:
    found = [entry for entry in registry.rules if rule_name(entry.rule) == rule_id]
    if not found:
        raise UnknownRule(f"no rule {rule_id} in {path}")
    return found[0]


def _speaking_root(registry: Registry, entry: RegistryEntry) -> Root:
    roots = [r for r in load_roots(registry.roots_dir) if r.id in entry.root_ids]
    if not roots:
        raise UnknownRule(f"rule {entry.rule} has no root on record")
    return roots[0]


def _pr_number(root: Root) -> int:
    found = PR_NUMBER.search(str(root.source_url))
    if found is None:
        raise UnknownRule(f"root {root.id} cites no pull request: {root.source_url}")
    return int(found.group(1))


def _built(loop: Loop, target: Target, cases: list[EditCase]) -> Built:
    # The same sides init proves against, plus every recorded case for this rule.
    base, head = _side(loop, target, "base"), _side(loop, target, "head")
    code = joined_source(base), joined_source(head)
    prompt = variant_prompt(target.decision, *code)
    sides = _sides(loop, target, (base, head), prompt)
    case = _case(loop, target, sides, cases)
    return Built(case, compile_prompt(target.decision, *code), prompt)


def _trees(loop: Loop, target: Target) -> dict[str, Any]:
    # The default branch, and the last release tagged before the PR merged.
    tree = loop.github.checkout(target.repo, loop.work / "tree")
    ref = last_release_before(loop.github.tags(target.repo), target.pr.merged_at)
    if ref is None:
        return {"tree": tree}
    old = loop.github.checkout_ref(target.repo, ref, loop.work / f"release-{ref}")
    return {"tree": tree, "old_ref": ref, "old_tree": old}


def _edit_sides(folder: Path, cases: list[EditCase]) -> dict[str, dict[str, GuardEdit]]:
    edits = {
        case.name: (case.kind, _edit_files(folder / case.key, case)) for case in cases
    }
    return {
        field: {name: edit for name, (k, edit) in edits.items() if k == kind}
        for field, kind in EDIT_FIELDS.items()
    }


def _edit_files(folder: Path, case: EditCase) -> GuardEdit:
    # A new file's before is empty, so all its matches are new.
    before, after = folder / "before" / case.file, folder / "after" / case.file
    for path, text in ((before, case.before or ""), (after, case.after)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return GuardEdit(before=before, after=after)


def _recompiled(loop: Loop, target: Target, built: Built, old: Attempt) -> LoopOutcome:
    # The old rule and its failures are the first feedback, so the fix starts from it.
    loop.log(_recompiling_line(target.rule_id, old.proof, loop.compiler.model))
    prompt = retry_prompt(built.compile_prompt, old, built.case)
    attempt = compile_rule(loop.compiler, built.case, prompt)
    rules = Rules(new=attempt.rule, old=old.rule)
    gates = _gates(loop, target, attempt, rules, built.variant_prompt)
    return _settled(target, attempt, gates, _saved_candidate(loop, target, attempt))


def _gates(
    loop: Loop, target: Target, attempt: Attempt, rules: Rules, prompt: str
) -> list[GateResult]:
    # Every gate runs, so a kept rule reports each reason, not only the first.
    folder = loop.heldout / str(target.pr.number)
    held = [_heldout_gate(folder / which, rules, which) for which in HELDOUT_SETS]
    fresh = _fresh_gate(loop, target.pr.number, rules, prompt)
    proof = attempt.proof
    return [_cases_gate(proof), _proof_gate(proof), *held, fresh]


def _proof_gate(proof: Proof) -> GateResult:
    # Absolute: sides, renames, variants, 0 FP on the default branch and old release.
    cases = edit_checks(proof.rows)
    failed = [check for check in failed_checks(proof) if check not in cases]
    detail = "; ".join(failed) or _proof_summary(proof)
    return GateResult(name="proof", passed=not failed, detail=detail)


def _proof_summary(proof: Proof) -> str:
    old = proof.old_release
    release = f" and release {old.ref}" if old else " (no release tagged before the PR)"
    sides = sorted({row.side for row in proof.rows})
    return f"{', '.join(sides)} hold; 0 FP on the default branch{release}"


def _heldout_gate(folder: Path, rules: Rules, which: str) -> GateResult:
    name = f"held-out {which}"
    if not folder.is_dir():
        return GateResult(name=name, passed=False, detail=f"missing {folder}")
    return _compared(name, _scores(rules, saved_variants(folder), which))


def _fresh_gate(loop: Loop, number: int, rules: Rules, prompt: str) -> GateResult:
    # A new folder each run, so the set is written again and no compile saw it.
    folder = loop.work / str(number) / f"fresh-{_stamp()}"
    try:
        sides = variant_files(folder, prompt, loop.writer)
    except Exception as error:
        return _not_run(FRESH, error)
    return _compared(FRESH, _scores(rules, sides, loop.writer.model), f" ({folder})")


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:6]


def _settled(
    target: Target, attempt: Attempt, gates: list[GateResult], candidate: Path
) -> LoopOutcome:
    # Installed only if every gate passed; otherwise the old rule file is untouched.
    installed = all(gate.passed for gate in gates)
    if installed:
        _install(target, attempt.rule)
    fields: dict[str, Any] = {"rule_id": target.rule_id, "installed": installed}
    fields |= {"attempts": attempt.number, "gates": gates, "rule": attempt.rule}
    return LoopOutcome.model_validate(fields | _recompiled_at(target, candidate))


def _old_attempt(target: Target, case: ProofCase) -> Attempt:
    rule = target.rule_path.read_text(encoding="utf-8")
    return Attempt(rule=rule, number=0, proof=prove(rule, case))


def _nothing_to_do(rule_id: str) -> LoopOutcome:
    fields = {"rule_id": rule_id, "recompiled": False, "installed": False}
    return LoopOutcome.model_validate(fields | {"gates": [_already()]})


def _work(loop: Loop, target: Target) -> Path:
    return loop.work / str(target.pr.number)


def _side(loop: Loop, target: Target, side: str) -> dict[str, Path]:
    return fetch_side(loop.github, target.repo, target.pr, side, _work(loop, target))


def _sides(
    loop: Loop,
    target: Target,
    code: tuple[dict[str, Path], dict[str, Path]],
    prompt: str,
) -> Sides:
    # Training variants come from the writer, cached per PR like init's.
    work = _work(loop, target)
    variants = variant_files(work / "variants", prompt, loop.writer)
    return verifier_sides(target.pr.number, *code, work, variants)


def _case(loop: Loop, target: Target, sides: Sides, cases: list[EditCase]) -> ProofCase:
    fields = {"sides": sides, "changed": target.pr.python_files, **_trees(loop, target)}
    edits = _edit_sides(_work(loop, target) / "cases", cases)
    return ProofCase.model_validate(fields | edits)


def _recompiling_line(rule_id: str, proof: Proof, model: str) -> str:
    failing = "; ".join(edit_checks(proof.rows))
    return f"{rule_id} fails: {failing}; recompiling with {model}"


def _not_run(name: str, error: Exception) -> GateResult:
    detail = f"not run: {type(error).__name__}: {error}"
    return GateResult(name=name, passed=False, detail=detail)


def _install(target: Target, rule: str) -> None:
    text = with_rule_id(rule, target.rule_id) + "\n"
    target.rule_path.write_text(text, encoding="utf-8")


def _recompiled_at(target: Target, candidate: Path) -> dict[str, Any]:
    paths = {"rule_path": target.rule_path, "candidate_path": candidate}
    return {"recompiled": True, **paths}


def _saved_candidate(loop: Loop, target: Target, attempt: Attempt) -> Path:
    path = _work(loop, target) / f"candidate-{_stamp()}.yml"
    path.write_text(attempt.rule + "\n", encoding="utf-8")
    return path


def _cases_gate(proof: Proof) -> GateResult:
    # Absolute: every recorded must-fail edit denied, every must-pass edit allowed.
    failed = edit_checks(proof.rows)
    detail = "; ".join(failed) or CASES_HOLD
    return GateResult(name="cases", passed=not failed, detail=detail)


def _scores(rules: Rules, sides: Sides, author: str) -> tuple[HeldOut, HeldOut]:
    # The same files scored by the recompiled rule and the installed one.
    new = score_heldout(rules.new, sides, author)
    return new, score_heldout(rules.old, sides, author)


def _compared(
    name: str, scores: tuple[HeldOut, HeldOut], where: str = ""
) -> GateResult:
    # Precision is absolute; recall must reach the old rule's, which counts 0 if broken.
    new, old = scores
    if new.error:
        return GateResult(name=name, passed=False, detail=new.error + where)
    floor = 0 if old.error else old.caught
    detail = _counts(new, floor) + where
    return GateResult(name=name, passed=_holds(new, floor), detail=detail)


def _holds(new: HeldOut, floor: int) -> bool:
    # An empty set proves nothing, so it never passes; init and watch share this bar.
    return holds_install_bar(new, floor)


def _counts(new: HeldOut, floor: int) -> str:
    caught = f"{new.caught}/{new.violations} violations caught (old rule {floor})"
    return f"{caught}, {new.allowed}/{new.compliant} compliant allowed"
