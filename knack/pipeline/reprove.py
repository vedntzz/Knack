from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from knack.contracts.models import RuleProof
from knack.hooks.pretool_guard import rule_name
from knack.pipeline.heldout import HeldOut, score_heldout
from knack.pipeline.models import PullRequest
from knack.pipeline.ports import GitHub
from knack.pipeline.prove import (
    failed_checks,
    MUST_FLAG,
    Proof,
    ProofCase,
    prove,
    Sides,
    verifier_sides,
)
from knack.pipeline.record import rule_proof
from knack.pipeline.releases import last_release_before
from knack.pipeline.select import pull_request
from knack.pipeline.sources import fetch_side
from knack.pipeline.variants import saved_variants, variant_authors
from knack.roots.pin import rule_sha
from knack.walk.registry import load_registry, Registry, RegistryEntry

Log = Callable[[str], None]
HELDOUT_SETS = ("same", "cross")
NO_RELEASE = "no X.Y.Z release was tagged before the PR merged ({merged})"
NO_VARIANTS = "no committed training variants at {folder}"
NO_HELDOUT = "no {which} held-out set at {folder}"
NO_FILES = "none of the PR's Python files exist at {side} {sha}"
# Proof-grid gate and a proof side it needs; an empty side leaves the gate not run.
NEEDS = (
    ("base", "base"),
    ("head", "head"),
    ("rename", "base"),
    ("rename", "head"),
    ("variants", "variant-violation"),
    ("compliant", "variant-compliant"),
)


@dataclass(frozen=True)
class Reprove:
    github: GitHub
    registry: Path
    # Committed training variants: <variants>/<pr>/{violation,compliant}_*.py.
    variants: Path
    # Committed held-out sets: <heldout>/<pr>/same and <heldout>/<pr>/cross.
    heldout: Path
    # The default-branch and release checkouts, reused across runs.
    work: Path
    log: Log
    stamp: str


@dataclass(frozen=True)
class Place:
    repo: str
    tree: Path
    tags: dict[str, str]


@dataclass(frozen=True)
class Inputs:
    case: ProofCase
    not_run: dict[str, str]


@dataclass(frozen=True)
class Reproved:
    proof: RuleProof
    failed: list[str]


def default_variants(registry: Path) -> Path:
    # data/registry/fastapi.json -> data/variants/fastapi.
    return registry.parent.parent / "variants" / registry.stem


def reprove_registry(run: Reprove) -> list[str]:
    # Every entry's proof replaced in place; returns the rules that could not be reproved.
    registry = load_registry(run.registry)
    place = _place(run, registry.repo)
    results = [_reproved_safely(run, place, entry) for entry in registry.rules]
    _write_proofs(run.registry, [proof for _, proof in results])
    run.log(f"wrote {run.registry}")
    return [name for name, proof in results if proof is None]


def reproved_line(name: str, reproved: Reproved) -> str:
    failed = "; ".join(reproved.failed) or "every gate run holds"
    skipped = ", ".join(reproved.proof.not_run)
    return f"{name}: {failed}" + (f"; not run: {skipped}" if skipped else "")


def _place(run: Reprove, repo: str) -> Place:
    tree = run.github.checkout(repo, run.work / "tree")
    return Place(repo, tree, run.github.tags(repo))


def _reproved_safely(
    run: Reprove, place: Place, entry: RegistryEntry
) -> tuple[str, RuleProof | None]:
    # One PR's failure is reported and keeps its old proof; the others still run.
    name = rule_name(entry.rule)
    try:
        reproved = _reproved(run, place, entry)
    except Exception as error:
        return name, _not_reproved(run, name, error)
    run.log(reproved_line(name, reproved))
    return name, reproved.proof


def _not_reproved(run: Reprove, name: str, error: Exception) -> None:
    run.log(f"{name} not reproved: {type(error).__name__}: {error}")


def _reproved(run: Reprove, place: Place, entry: RegistryEntry) -> Reproved:
    pr = pull_request(run.github, place.repo, _rule_number(entry.rule))
    inputs = _inputs(run, place, pr)
    rule = entry.rule.read_text(encoding="utf-8")
    proof = prove(rule, inputs.case)
    held, missing = _heldout(run, pr.number, rule)
    stored = _stored(run, entry, (proof, pr), held, inputs.not_run | missing)
    return Reproved(stored, _failures(proof, held))


def _rule_number(rule: Path) -> int:
    # Installed rules are named <pr>.yml.
    return int(rule.stem.split(".")[0])


def _inputs(run: Reprove, place: Place, pr: PullRequest) -> Inputs:
    sides = _sides(run, place, pr)
    release, no_release = _release(run, place, pr)
    missing = _missing(run, pr, sides) | no_release
    return Inputs(_case(place, pr, sides, release), missing)


def _sides(run: Reprove, place: Place, pr: PullRequest) -> Sides:
    # The PR's base and head, their renamed copies, and the committed variants.
    work = run.work / str(pr.number)
    base = fetch_side(run.github, place.repo, pr, "base", work)
    head = fetch_side(run.github, place.repo, pr, "head", work)
    found = _variant_folder(run, pr.number)
    variants = saved_variants(found) if found else {}
    return verifier_sides(pr.number, base, head, work, variants)


def _case(
    place: Place, pr: PullRequest, sides: Sides, release: dict[str, Any]
) -> ProofCase:
    fields = {"sides": sides, "changed": pr.python_files, "tree": place.tree}
    return ProofCase.model_validate(fields | release)


def _variant_folder(run: Reprove, number: int) -> Path | None:
    # The committed set, else the one install wrote beside a home registry.
    install = run.registry.parent / "work" / str(number) / "variants"
    found = [run.variants / str(number), install]
    return next((f for f in found if any(f.glob("violation_*.py"))), None)


def _missing(run: Reprove, pr: PullRequest, sides: Sides) -> dict[str, str]:
    # Why each empty side is empty: the PR's files or the variants do not exist.
    variants = NO_VARIANTS.format(folder=run.variants / str(pr.number))
    why = {"variant-violation": variants, "variant-compliant": variants}
    why |= {"base": NO_FILES.format(side="base", sha=pr.base_sha)}
    why |= {"head": NO_FILES.format(side="head", sha=pr.head_sha)}
    return {gate: why[side] for gate, side in NEEDS if not sides.get(side)}


def _release(
    run: Reprove, place: Place, pr: PullRequest
) -> tuple[dict[str, Any], dict[str, str]]:
    # The last release tagged before the merge, as install picks it.
    ref = last_release_before(place.tags, pr.merged_at)
    if ref is None:
        return {}, {"0 FP release": NO_RELEASE.format(merged=pr.merged_at)}
    old = run.github.checkout_ref(place.repo, ref, run.work / f"release-{ref}")
    return {"old_ref": ref, "old_tree": old}, {}


def _heldout(
    run: Reprove, number: int, rule: str
) -> tuple[dict[str, HeldOut], dict[str, str]]:
    folders = {which: run.heldout / str(number) / which for which in HELDOUT_SETS}
    found = {which: f for which, f in folders.items() if f.is_dir()}
    scores = {which: _score(rule, f, which) for which, f in found.items()}
    return scores, _missing_heldout(folders, found)


def _missing_heldout(
    folders: dict[str, Path], found: dict[str, Path]
) -> dict[str, str]:
    gone = [NO_HELDOUT.format(which=w, folder=f) for w, f in folders.items()]
    named = [why for which, why in zip(folders, gone) if which not in found]
    return {"held-out": "; ".join(named)} if named else {}


def _score(rule: str, folder: Path, which: str) -> HeldOut:
    # Scored by the model that wrote the set, if recorded, else by the set's name.
    author = next(iter(variant_authors(folder).values()), which)
    return score_heldout(rule, saved_variants(folder), author)


def _stored(
    run: Reprove,
    entry: RegistryEntry,
    proven: tuple[Proof, PullRequest],
    held: dict[str, HeldOut],
    not_run: dict[str, str],
) -> RuleProof:
    # Install's attempt count stays; a rule never installed by knack has none recorded.
    attempts = entry.proof.attempts if entry.proof else 0
    sets = {which: score.model_dump() for which, score in held.items()}
    pinned = {"rule_sha": rule_sha(entry.rule), "reproved_at": run.stamp}
    found = {"heldout_sets": sets, "not_run": not_run} | pinned
    return RuleProof.model_validate(rule_proof(*proven, attempts).model_dump() | found)


def _failures(proof: Proof, held: dict[str, HeldOut]) -> list[str]:
    # A side with no files was not run, so it is reported as not run, not failed.
    ran = {row.side for row in proof.rows}
    checks = [c for c in failed_checks(proof) if c not in MUST_FLAG or c in ran]
    return checks + [_heldout_failure(w, s) for w, s in held.items() if not s.passed]


def _heldout_failure(which: str, score: HeldOut) -> str:
    counts = f"{score.caught}/{score.violations} caught, {score.allowed}/{score.compliant} allowed"
    return f"held-out {which}: {score.error or counts}"


def _write_proofs(path: Path, proofs: list[RuleProof | None]) -> None:
    # Paths stay as written, relative to the registry; an unreproved entry is untouched.
    raw = Registry.model_validate_json(path.read_text(encoding="utf-8"))
    pairs = zip(raw.rules, proofs)
    rules = [e if p is None else e.model_copy(update={"proof": p}) for e, p in pairs]
    text = raw.model_copy(update={"rules": rules}).model_dump_json(indent=2)
    path.write_text(text + "\n", encoding="utf-8")
