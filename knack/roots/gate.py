import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from knack.contracts.models import Root
from knack.pipeline.corroborate import same_alternative
from knack.pipeline.extract import extract_pr
from knack.pipeline.models import Alternative, Extraction, PullRequest
from knack.pipeline.ports import GitHub, Spark
from knack.roots.corrections import (
    Correction,
    few_shot_block,
    recent_corrections,
    remove_correction,
)
from knack.roots.store import find_root, load_roots, write_root
from knack.walk.registry import load_registry

PR_NUMBER = re.compile(r"/pull/(\d+)")
Apply = Callable[[Path], Correction]


def _quiet(line: str) -> None:
    pass


@dataclass(frozen=True)
class Gate:
    github: GitHub
    spark: Spark
    log: Callable[[str], None] = field(default=_quiet)


@dataclass(frozen=True)
class Outcome:
    correction: Correction
    # Confirmed roots the new few-shot block no longer extracts; empty means kept.
    lost: list[Root]

    @property
    def rolled_back(self) -> bool:
        return bool(self.lost)


def gated(registry_path: Path, apply: Apply, gate: Gate | None, log: Path) -> Outcome:
    # Apply the correction, re-read every Confirmed PR, and undo it if one regressed.
    saved = registry_path.read_text("utf-8") if registry_path.exists() else ""
    correction = apply(registry_path)
    lost = [] if gate is None else lost_roots(registry_path, gate, log)
    if lost:
        _roll_back(registry_path, correction, saved, log)
    return Outcome(correction, lost)


def lost_roots(registry_path: Path, gate: Gate, log: Path) -> list[Root]:
    registry = load_registry(registry_path)
    by_pr = _confirmed_by_pr(load_roots(registry.roots_dir))
    gate.log(f"gate: re-extracting {len(by_pr)} PR(s) with Confirmed roots")
    few_shot = few_shot_block(recent_corrections(log))
    lost = [_lost_in(gate, registry.repo, n, rs, few_shot) for n, rs in by_pr.items()]
    return [root for roots in lost for root in roots]


def still_extracted(root: Root, extraction: Extraction) -> bool:
    # Corroboration's test, judged against a verbatim quote in the new reading.
    found = [a for d in extraction.decisions for a in d.rejected_alternatives]
    confirmed = Alternative(
        alternative=root.rejected_alternative or "", quote=root.quote, verbatim=True
    )
    return any(a.verbatim and same_alternative(confirmed, a) for a in found)


def regressed_line(root: Root) -> str:
    alternative, quote = root.rejected_alternative, root.quote
    said = f"rejected alternative {alternative!r} quoting {quote!r}"
    return f"  {root.id} (#{pr_number(root)}) no longer extracted: {said}"


def pr_number(root: Root) -> int:
    match = PR_NUMBER.search(str(root.source_url))
    if match is None:
        raise ValueError(f"{root.id} source_url names no pull request")
    return int(match.group(1))


def _confirmed_by_pr(roots: list[Root]) -> dict[int, list[Root]]:
    # Only roots with a rejected alternative can be matched against an extraction.
    by_pr = dict[int, list[Root]]()
    for root in roots:
        if root.status == "Confirmed" and root.rejected_alternative:
            by_pr.setdefault(pr_number(root), []).append(root)
    return by_pr


def _lost_in(
    gate: Gate, repo: str, number: int, roots: list[Root], few_shot: str
) -> list[Root]:
    # A PR that can no longer be read loses every root it backed.
    extraction = _extracted(gate, repo, number, few_shot)
    if extraction is None:
        return roots
    return [root for root in roots if not still_extracted(root, extraction)]


def _extracted(gate: Gate, repo: str, number: int, few_shot: str) -> Extraction | None:
    try:
        pr = _pull(gate, repo, number)
        return extract_pr(gate.github, gate.spark, repo, pr, few_shot=few_shot)
    except Exception:
        return None


def _pull(gate: Gate, repo: str, number: int) -> PullRequest:
    # Only title, author and body feed the extract prompt; shas and files do not.
    summary = gate.github.summary(repo, number).model_dump()
    return PullRequest(**summary, base_sha="", head_sha="", python_files=[])


def _roll_back(
    registry_path: Path, correction: Correction, saved: str, log: Path
) -> None:
    # The log line, the registry rules a reject dropped, then the root as it was.
    remove_correction(correction, log)
    registry_path.write_text(saved, encoding="utf-8")
    found = find_root(load_registry(registry_path).roots_dir, correction.root_id)
    if found is not None:
        write_root(correction.before, found[0])
