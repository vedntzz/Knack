from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any

from knack.contracts.models import Root
from knack.pipeline.compile import Attempt, compile_prompt, compile_rule, with_rule_id
from knack.pipeline.corroborate import corroborated_roots
from knack.pipeline.extract import extract_all
from knack.pipeline.heldout import (
    HeldOut,
    HELDOUT_DIR,
    install_failure,
    not_run,
    score_heldout,
)
from knack.pipeline.models import Compiled, Decision, Extraction, PullRequest, Selection
from knack.pipeline.ports import GitHub, Spark
from knack.pipeline.progress import (
    adversary_line,
    compile_line,
    extract_header,
    extract_totals_line,
    extracted_line,
    heldout_line,
    install_line,
    old_release_line,
    outcome_line,
    roots_line,
    second_line,
    select_line,
)
from knack.pipeline.prove import failed_checks, ProofCase, Sides, verifier_sides
from knack.pipeline.readings import save_readings, save_trace
from knack.pipeline.record import rule_proof, with_heldout, with_merged_at
from knack.pipeline.releases import last_release_before
from knack.pipeline.roots import install_roots, reviewed_roots, root_prefix, roots_for
from knack.pipeline.sources import fetch_side, joined_source
from knack.pipeline.variants import variant_files, variant_prompt
from knack.roots.corrections import corrections_path, few_shot_block, recent_corrections
from knack.walk.registry import Registry, RegistryEntry

Log = Callable[[str], None]


@dataclass(frozen=True)
class Run:
    github: GitHub
    spark: Spark
    repo: str
    out: Path
    log: Log
    # Proof scans this tree; None clones the default branch under out/work/tree.
    tree: Path | None = None
    # The release every proof must also stay clean on; None picks one per PR.
    old_ref: str | None = None
    # The partner extractor that corroborates every root; None reads once.
    second: Spark | None = None
    # The model that writes variants; None means the compiler, with a warning.
    adversary: Spark | None = None


@dataclass(frozen=True)
class SecondReading:
    model: str
    by_number: dict[int, Extraction]


@dataclass(frozen=True)
class Trees:
    tree: Path
    # Release tag dates, read once; empty when old_ref names the release.
    tags: dict[str, str]


@dataclass(frozen=True)
class Target:
    pr: PullRequest
    decision: Decision
    root_ids: list[str]


def verbatim_decision(extraction: Extraction) -> Decision | None:
    # The first decision with a verbatim rejected alternative; it is the one compiled.
    for decision in extraction.decisions:
        if any(a.verbatim for a in decision.rejected_alternatives):
            return decision
    return None


def finish(run: Run, selection: Selection, keep: list[RegistryEntry]) -> Path:
    # extract -> roots -> compile+prove -> install, after either kind of select.
    run.log(select_line(selection))
    extractions, second = read_and_save(run, selection.prs)
    roots = _roots_stage(run, extractions, second, selection.prs)
    compiled = _compile_stage(run, selection.prs, extractions, roots)
    return _install_stage(run, compiled, keep)


def read_and_save(
    run: Run, prs: list[PullRequest]
) -> tuple[list[Extraction], SecondReading | None]:
    # Both models read every PR; both readings, and any kept trace, go to out/work.
    extractions = _extract_stage(run, prs)
    second = _second_stage(run, prs)
    _save_stage(run, extractions, second)
    return extractions, second


def _extract_stage(run: Run, prs: list[PullRequest]) -> list[Extraction]:
    run.log(extract_header(len(prs)))
    # The last few human corrections teach this run's extract prompt.
    report = partial(_log_extracted, run.log)
    stage = extract_all(run.github, run.spark, run.repo, prs, report, _lessons())
    run.log(extract_totals_line(stage))
    return stage.extractions


def _second_stage(run: Run, prs: list[PullRequest]) -> SecondReading | None:
    # The partner reads the same PRs; a PR it fails on keeps its roots Inferred.
    if run.second is None:
        return None
    keep = partial(_keep_trace, run.out / "work", run.second)
    stage = extract_all(run.github, run.second, run.repo, prs, keep, _lessons())
    run.log(second_line(run.second.model, stage))
    return SecondReading(run.second.model, {e.number: e for e in stage.extractions})


def _save_stage(
    run: Run, extractions: list[Extraction], second: SecondReading | None
) -> None:
    # Both readings stay on disk; a PR a model failed on has no entry for it.
    by_model = {run.spark.model: extractions}
    if second is not None:
        by_model[second.model] = list(second.by_number.values())
    save_readings(run.out / "work", by_model)


def _keep_trace(
    work: Path, second: Spark, number: int, extraction: Extraction | None
) -> None:
    # Runs right after each PR's read, so last_trace is that PR's; None when the flag is off.
    trace: str | None = getattr(second, "last_trace", None)
    if extraction is not None and trace:
        save_trace(work, number, second.model, trace)


def _lessons() -> str:
    return few_shot_block(recent_corrections(corrections_path()))


def _log_extracted(log: Log, number: int, extraction: Extraction | None) -> None:
    log(extracted_line(number, extraction))


def _roots_stage(
    run: Run,
    extractions: list[Extraction],
    second: SecondReading | None,
    prs: list[PullRequest],
) -> list[Root]:
    # New roots carry machine labels and merge time; reviewed ones on disk stay.
    found = [r for e in extractions for r in _roots_of(run, e, second)]
    roots = with_merged_at(found, prs)
    reviewed = reviewed_roots(run.out / "roots")
    written = install_roots(roots, run.out / "roots")
    kept = [reviewed[r.id] for r in roots if r.id in reviewed]
    run.log(roots_line(written, kept, corroborating=second is not None))
    return [r for r in roots if reviewed.get(r.id, r).status != "Unknown"]


def _roots_of(
    run: Run, extraction: Extraction, second: SecondReading | None
) -> list[Root]:
    if second is None:
        return roots_for(run.repo, extraction, run.spark.model)
    other = second.by_number.get(extraction.number)
    models = (run.spark.model, second.model)
    return corroborated_roots(run.repo, extraction, other, models)


def _compile_stage(
    run: Run, prs: list[PullRequest], extractions: list[Extraction], roots: list[Root]
) -> list[Compiled]:
    # The default branch is cloned only when some PR has a rule to prove.
    targets = _targets(prs, extractions, roots)
    _log_compile_header(run, len(targets))
    if not targets:
        return []
    tags = {} if run.old_ref else run.github.tags(run.repo)
    trees = Trees(_prepare(run), tags)
    return [_compile_logged(run, target, trees) for target in targets]


def _log_compile_header(run: Run, targets: int) -> None:
    run.log(compile_line(targets))
    run.log(adversary_line(run.spark.model, _writer(run).model))


def _writer(run: Run) -> Spark:
    return run.adversary or run.spark


def _targets(
    prs: list[PullRequest], extractions: list[Extraction], roots: list[Root]
) -> list[Target]:
    by_number = {pr.number: pr for pr in prs}
    found = [(e.number, verbatim_decision(e)) for e in extractions]
    targets = [Target(by_number[n], d, _root_ids(roots, n, d)) for n, d in found if d]
    # A decision whose every root was rejected gets no rule, so none is compiled.
    return [target for target in targets if target.root_ids]


def _root_ids(roots: list[Root], number: int, decision: Decision) -> list[str]:
    # The roots behind the compiled decision, so the rule cites what it enforces.
    ours = [r for r in roots if str(r.source_url).endswith(f"/pull/{number}")]
    return [r.id for r in ours if r.decision == decision.decision]


def _prepare(run: Run) -> Path:
    (run.out / "rules").mkdir(parents=True, exist_ok=True)
    return run.tree or run.github.checkout(run.repo, run.out / "work" / "tree")


def _old_release(run: Run, pr: PullRequest, tags: dict[str, str]) -> dict[str, Any]:
    # --old-ref wins; otherwise the last release tagged before this PR merged.
    ref = run.old_ref or last_release_before(tags, pr.merged_at)
    run.log(old_release_line(pr.number, ref, pr.merged_at, bool(run.old_ref)))
    if ref is None:
        return {}
    dest = run.out / "work" / f"release-{ref}"
    return {"old_ref": ref, "old_tree": run.github.checkout_ref(run.repo, ref, dest)}


def _compile_logged(run: Run, target: Target, trees: Trees) -> Compiled:
    compiled = _compile_safely(run, target, trees)
    run.log(outcome_line(compiled))
    if compiled.heldout is not None:
        run.log(heldout_line(compiled.number, compiled.heldout))
    return compiled


def _compile_safely(run: Run, target: Target, trees: Trees) -> Compiled:
    # One PR's network or model failure is reported, never fatal to the run.
    try:
        prompt, attempt = _compile_pr(run, target, trees)
        compiled = _record(run, target, attempt)
        return _with_heldout(run, compiled, prompt, _rule_text(run, target, attempt))
    except Exception as error:
        return _failed(target, error)


def _compile_pr(run: Run, target: Target, trees: Trees) -> tuple[str, Attempt]:
    # Returns the variant prompt too, so the held-out set is asked the same way.
    work = _work(run, target.pr.number)
    base, head = _side(run, target, "base", work), _side(run, target, "head", work)
    code = joined_source(base), joined_source(head)
    prompt = variant_prompt(target.decision, *code)
    case = _case(run, target.pr, trees, _sides(run, target, prompt, (base, head)))
    return prompt, compile_rule(run.spark, case, compile_prompt(target.decision, *code))


def _work(run: Run, number: int) -> Path:
    return run.out / "work" / str(number)


def _sides(
    run: Run, target: Target, prompt: str, code: tuple[dict[str, Path], dict[str, Path]]
) -> Sides:
    work = _work(run, target.pr.number)
    variants = variant_files(work / "variants", prompt, _writer(run))
    return verifier_sides(target.pr.number, *code, work, variants)


def _with_heldout(run: Run, compiled: Compiled, prompt: str, text: str) -> Compiled:
    # Scored after the last attempt, so the compiler never sees the held-out set.
    if compiled.rule is None:
        return compiled
    heldout = _heldout_safely(run, compiled.number, text, prompt)
    failure = install_failure(heldout)
    if failure is not None:
        return _discarded_by_heldout(compiled, heldout, failure)
    return _written(compiled, compiled.rule, heldout, text)


def _written(compiled: Compiled, rule: Path, heldout: HeldOut, text: str) -> Compiled:
    # Only a rule that cleared the held-out bar reaches disk.
    rule.write_text(text, encoding="utf-8")
    proof = with_heldout(compiled.proof, heldout)
    return compiled.model_copy(update={"heldout": heldout, "proof": proof})


def _discarded_by_heldout(
    compiled: Compiled, heldout: HeldOut, failure: str
) -> Compiled:
    # The score stays for the log; nothing is written, so a kept rule file is untouched.
    update = {"rule": None, "proof": None, "heldout": heldout}
    return compiled.model_copy(update=update | {"failed_checks": [failure]})


def _heldout_safely(run: Run, number: int, text: str, prompt: str) -> HeldOut:
    # A writer or scan failure is "not run", which the install bar then discards.
    writer = _writer(run)
    try:
        sides = variant_files(_work(run, number) / HELDOUT_DIR, prompt, writer)
        return score_heldout(text, sides, writer.model)
    except Exception as error:
        return not_run(writer.model, error)


def _case(run: Run, pr: PullRequest, trees: Trees, sides: Sides) -> ProofCase:
    fields = {"sides": sides, "changed": pr.python_files, "tree": trees.tree}
    return ProofCase.model_validate({**fields, **_old_release(run, pr, trees.tags)})


def _side(run: Run, target: Target, side: str, work: Path) -> dict[str, Path]:
    return fetch_side(run.github, run.repo, target.pr, side, work)


def _record(run: Run, target: Target, attempt: Attempt) -> Compiled:
    rule = _rule_path(run, target, attempt)
    fields = {"number": target.pr.number, "rule": rule, "root_ids": target.root_ids}
    checks = {"attempts": attempt.number, "failed_checks": failed_checks(attempt.proof)}
    proof = rule_proof(attempt.proof, target.pr, attempt.number) if rule else None
    return Compiled.model_validate(fields | checks | {"proof": proof})


def _rule_path(run: Run, target: Target, attempt: Attempt) -> Path | None:
    # Where a proven rule goes; it is written only once held-out clears the bar.
    if not attempt.proven:
        return None
    return run.out / "rules" / f"{target.pr.number}.yml"


def _rule_text(run: Run, target: Target, attempt: Attempt) -> str:
    rule_id = f"{root_prefix(run.repo)}-{target.pr.number}"
    return with_rule_id(attempt.rule, rule_id) + "\n"


def _failed(target: Target, error: Exception) -> Compiled:
    fields = {"number": target.pr.number, "rule": None, "root_ids": target.root_ids}
    failure = f"{type(error).__name__}: {error}"
    return Compiled.model_validate(
        {**fields, "attempts": 0, "failed_checks": [failure]}
    )


def _install_stage(
    run: Run, compiled: list[Compiled], keep: list[RegistryEntry]
) -> Path:
    # New rules join the kept entries; a rule file proven again replaces its entry.
    entries = [_entry(c) for c in compiled if c.rule]
    rules = [e for e in keep if e.rule not in {n.rule for n in entries}] + entries
    path = _write_registry(run, rules)
    discarded = len(compiled) - len(entries)
    run.log(install_line(len(entries), discarded, len(rules), path))
    return path


def _write_registry(run: Run, rules: list[RegistryEntry]) -> Path:
    # Paths in the registry are relative to it, so the folder can move.
    registry = Registry(repo=run.repo, roots_dir=Path("roots"), rules=rules)
    path = run.out / "registry.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(registry.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def _entry(compiled: Compiled) -> RegistryEntry:
    rule = Path("rules") / Path(str(compiled.rule)).name
    return RegistryEntry(rule=rule, root_ids=compiled.root_ids, proof=compiled.proof)
