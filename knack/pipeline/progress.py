from pathlib import Path

from knack.contracts.models import Root
from knack.pipeline.heldout import HeldOut
from knack.pipeline.models import Compiled, Extraction, ExtractStage, Selection


def select_line(selection: Selection) -> str:
    return f"[1/5] select   {selection.read} PRs read, {len(selection.prs)} kept"


def extract_header(prs: int) -> str:
    return f"[2/5] extract  reading {prs} PRs"


def extracted_line(number: int, extraction: Extraction | None) -> str:
    # Indented under the extract stage, one line per PR as it finishes.
    if extraction is None:
        return f"  #{number}: failed"
    decisions = _counted(len(extraction.decisions), "decision")
    total = sum(len(d.rejected_alternatives) for d in extraction.decisions)
    return f"  #{number}: {decisions}, {_counted(total, 'rejected alternative')}"


def extract_totals_line(stage: ExtractStage) -> str:
    decisions = [d for e in stage.extractions for d in e.decisions]
    alternatives = [a for d in decisions for a in d.rejected_alternatives]
    verbatim = sum(1 for a in alternatives if a.verbatim)
    found = f"{len(decisions)} decisions found"
    rejected = f"{len(alternatives)} rejected alternatives ({verbatim} verbatim)"
    return f"  {found}, {rejected}, {failed_text(stage.failed)}"


def failed_text(failed: list[int]) -> str:
    listed = ", ".join(f"#{number}" for number in failed)
    return f"{len(failed)} failed: {listed}" if failed else "0 failed"


def second_line(model: str, stage: ExtractStage) -> str:
    # The corroborating extractor's totals, under the primary's.
    return f"  second reading by {model}: {extract_totals_line(stage).strip()}"


def roots_line(
    written: list[Root], kept: list[Root], corroborating: bool = False
) -> str:
    # kept are the human-reviewed roots init left alone.
    confirmed = sum(root.status == "Confirmed" for root in kept)
    counts = f"{confirmed} Confirmed, {len(kept) - confirmed} Unknown kept"
    return f"[3/5] roots    {_written_text(written, corroborating)} ({counts})"


def compile_line(targets: int) -> str:
    return f"[4/5] compile  {targets} PRs with a verbatim rejected alternative"


def old_release_line(number: int, ref: str | None, merged_at: str, given: bool) -> str:
    # Which release this PR's rule must stay clean on, and why that one.
    head, merged = f"  #{number} old release:", merged_at[:10]
    if given:
        return f"{head} {ref} (--old-ref)"
    if ref is None:
        return f"{head} none before merge {merged}, check skipped"
    return f"{head} {ref} (last release before merge {merged})"


def outcome_line(compiled: Compiled) -> str:
    # Indented under the compile stage, one line per PR as it finishes.
    if compiled.rule is not None:
        return f"  #{compiled.number} proven on attempt {compiled.attempts}"
    after = f" after {compiled.attempts} attempts" if compiled.attempts else ""
    return f"  #{compiled.number} discarded{after}: {', '.join(compiled.failed_checks)}"


def install_line(proven: int, discarded: int, total: int, path: Path) -> str:
    counts = f"{proven} rules proven, {discarded} discarded, {total} in registry"
    return f"[5/5] install  {counts} -> {path}"


def _written_text(written: list[Root], corroborating: bool) -> str:
    inferred = sum(root.status == "Inferred" for root in written)
    if not corroborating:
        return f"{inferred} Inferred roots written"
    corroborated = sum(root.status == "Corroborated" for root in written)
    uncorroborated = sum(root.status == "Uncorroborated" for root in written)
    labels = f"{corroborated} corroborated, {uncorroborated} uncorroborated, {inferred} Inferred"
    return f"{len(written)} roots written: {labels}"


def _counted(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def adversary_line(compiler: str, adversary: str) -> str:
    # Variants from the compiler's own model only test it against its own ideas.
    if adversary == compiler:
        own = f"variants written by {compiler}, the compiler itself"
        return f"  warning: {own}; no cross-model adversary"
    return f"  adversary: {adversary} writes variants, {compiler} compiles"


def heldout_line(number: int, heldout: HeldOut) -> str:
    # Indented under the rule's outcome line; a set that could not run says so.
    if heldout.error is not None:
        return f"  #{number} held-out: not run ({heldout.error})"
    caught = f"{heldout.caught}/{heldout.violations} violations caught"
    allowed = f"{heldout.allowed}/{heldout.compliant} compliant allowed"
    verdict = "pass" if heldout.passed else "fail"
    return f"  #{number} held-out by {heldout.author}: {caught}, {allowed} ({verdict})"
