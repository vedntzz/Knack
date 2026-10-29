from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from knack.contracts.models import Root
from knack.pipeline.compile import Attempt, compile_prompt, compile_rule, with_rule_id
from knack.pipeline.extract import extract_all
from knack.pipeline.models import Compiled, Decision, Extraction, PullRequest
from knack.pipeline.ports import GitHub, Spark
from knack.pipeline.progress import (
    compile_line,
    extract_header,
    extract_totals_line,
    extracted_line,
    install_line,
    outcome_line,
    roots_line,
    select_line,
)
from knack.pipeline.prove import failed_checks, ProofCase, Sides, verifier_sides
from knack.pipeline.roots import install_roots, reviewed_roots, root_prefix, roots_for
from knack.pipeline.select import select_prs
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


@dataclass(frozen=True)
class Target:
    pr: PullRequest
    decision: Decision
    root_ids: list[str]


def run_init(
    repo: str, limit: int, out: Path, github: GitHub, spark: Spark, log: Log = print
) -> Path:
    # select -> extract -> roots -> compile+prove -> install; returns the registry path.
    run = Run(github, spark, repo, out, log)
    log(f"knack init {repo}")
    prs = _select_stage(run, limit)
    extractions = _extract_stage(run, prs)
    roots = _roots_stage(run, extractions)
    return _install_stage(run, _compile_stage(run, prs, extractions, roots))


def verbatim_decision(extraction: Extraction) -> Decision | None:
    # The first decision with a verbatim rejected alternative; it is the one compiled.
    for decision in extraction.decisions:
        if any(a.verbatim for a in decision.rejected_alternatives):
            return decision
    return None


def _select_stage(run: Run, limit: int) -> list[PullRequest]:
    selection = select_prs(run.github, run.repo, limit)
    run.log(select_line(selection))
    return selection.prs


def _extract_stage(run: Run, prs: list[PullRequest]) -> list[Extraction]:
    run.log(extract_header(len(prs)))
    # The last few human corrections teach this run's extract prompt.
    report = partial(_log_extracted, run.log)
    lessons = few_shot_block(recent_corrections(corrections_path()))
    stage = extract_all(run.github, run.spark, run.repo, prs, report, lessons)
    run.log(extract_totals_line(stage))
    return stage.extractions


def _log_extracted(log: Log, number: int, extraction: Extraction | None) -> None:
    log(extracted_line(number, extraction))


def _roots_stage(run: Run, extractions: list[Extraction]) -> list[Root]:
    # New roots are Inferred; reviewed ones on disk stay, and rejected ones back no rule.
    roots = [r for e in extractions for r in roots_for(run.repo, e, run.spark.model)]
    reviewed = reviewed_roots(run.out / "roots")
    written = install_roots(roots, run.out / "roots")
    run.log(
        roots_line(len(written), [reviewed[r.id] for r in roots if r.id in reviewed])
    )
    return [r for r in roots if reviewed.get(r.id, r).status != "Unknown"]


def _compile_stage(
    run: Run, prs: list[PullRequest], extractions: list[Extraction], roots: list[Root]
) -> list[Compiled]:
    # The default branch is cloned only when some PR has a rule to prove.
    targets = _targets(prs, extractions, roots)
    run.log(compile_line(len(targets)))
    if not targets:
        return []
    tree = _prepare(run)
    return [_compile_logged(run, target, tree) for target in targets]


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
    return run.github.checkout(run.repo, run.out / "work" / "tree")


def _compile_logged(run: Run, target: Target, tree: Path) -> Compiled:
    compiled = _compile_safely(run, target, tree)
    run.log(outcome_line(compiled))
    return compiled


def _compile_safely(run: Run, target: Target, tree: Path) -> Compiled:
    # One PR's network or model failure is reported, never fatal to the run.
    try:
        return _record(run, target, _compile_pr(run, target, tree))
    except Exception as error:
        return _failed(target, error)


def _compile_pr(run: Run, target: Target, tree: Path) -> Attempt:
    work = run.out / "work" / str(target.pr.number)
    base, head = _side(run, target, "base", work), _side(run, target, "head", work)
    before, after = joined_source(base), joined_source(head)
    variants = _variants(run, target.decision, (before, after), work)
    sides = verifier_sides(target.pr.number, base, head, work, variants)
    case = ProofCase(sides=sides, changed=target.pr.python_files, tree=tree)
    return compile_rule(run.spark, case, compile_prompt(target.decision, before, after))


def _side(run: Run, target: Target, side: str, work: Path) -> dict[str, Path]:
    return fetch_side(run.github, run.repo, target.pr, side, work)


def _variants(run: Run, decision: Decision, code: tuple[str, str], work: Path) -> Sides:
    prompt = variant_prompt(decision, *code)
    return variant_files(work / "variants", prompt, run.spark)


def _record(run: Run, target: Target, attempt: Attempt) -> Compiled:
    rule = _install_rule(run, target, attempt)
    fields = {"number": target.pr.number, "rule": rule, "root_ids": target.root_ids}
    fields |= {
        "attempts": attempt.number,
        "failed_checks": failed_checks(attempt.proof),
    }
    return Compiled.model_validate(fields)


def _install_rule(run: Run, target: Target, attempt: Attempt) -> Path | None:
    # A proven rule is written under its own id; a discarded one leaves no file behind.
    path = run.out / "rules" / f"{target.pr.number}.yml"
    path.unlink(missing_ok=True)
    if not attempt.proven:
        return None
    rule_id = f"{root_prefix(run.repo)}-{target.pr.number}"
    path.write_text(with_rule_id(attempt.rule, rule_id) + "\n", encoding="utf-8")
    return path


def _failed(target: Target, error: Exception) -> Compiled:
    fields = {"number": target.pr.number, "rule": None, "root_ids": target.root_ids}
    failure = f"{type(error).__name__}: {error}"
    return Compiled.model_validate(
        {**fields, "attempts": 0, "failed_checks": [failure]}
    )


def _install_stage(run: Run, compiled: list[Compiled]) -> Path:
    # Paths in the registry are relative to it, so the folder can move.
    entries = [_entry(c.rule, c.root_ids) for c in compiled if c.rule]
    registry = Registry(repo=run.repo, roots_dir=Path("roots"), rules=entries)
    path = run.out / "registry.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(registry.model_dump_json(indent=2) + "\n", encoding="utf-8")
    run.log(install_line(len(entries), len(compiled) - len(entries), path))
    return path


def _entry(rule: Path, root_ids: list[str]) -> RegistryEntry:
    return RegistryEntry(rule=Path("rules") / rule.name, root_ids=root_ids)
