from pathlib import Path

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


def roots_line(written: int, kept: int) -> str:
    return f"[3/5] roots    {written} Inferred roots written ({kept} Confirmed kept)"


def compile_line(targets: int) -> str:
    return f"[4/5] compile  {targets} PRs with a verbatim rejected alternative"


def outcome_line(compiled: Compiled) -> str:
    # Indented under the compile stage, one line per PR as it finishes.
    if compiled.rule is not None:
        return f"  #{compiled.number} proven on attempt {compiled.attempts}"
    after = f" after {compiled.attempts} attempts" if compiled.attempts else ""
    return f"  #{compiled.number} discarded{after}: {', '.join(compiled.failed_checks)}"


def install_line(proven: int, discarded: int, path: Path) -> str:
    return f"[5/5] install  {proven} rules proven, {discarded} discarded -> {path}"


def _counted(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"
