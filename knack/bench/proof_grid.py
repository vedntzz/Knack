import re
from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from knack.bench.heldout_pr import HeldOutPr
from knack.contracts.models import RuleProof
from knack.pipeline.prove import MIN_FLAGGED, MUST_FLAG
from knack.roots.pin import pin_holds, rule_sha
from knack.roots.store import load_roots
from knack.walk.registry import load_registry, Registry, RegistryEntry

Mark = Literal["PASS", "FAIL", "NOT RUN"]
Tier = Literal["block", "warn"]
# (held-out repo dir, PR) -> its same- and cross-model scores.
HeldOut = dict[tuple[str, str], HeldOutPr]
GATES = (
    "base",
    "head",
    "0 FP tree",
    "0 FP release",
    "rename",
    "variants",
    "compliant",
    "held-out",
)
# Each side gate and the proof sides that must all hold for it.
SIDE_GATES = {
    "base": ("base",),
    "head": ("head",),
    "rename": ("rename-base", "rename-head"),
    "variants": ("variant-violation",),
    "compliant": ("variant-compliant",),
}
HEADING = re.compile(r"^=== (.*) ===$", re.M)
ATTEMPT = re.compile(r"#(\d+) ATTEMPT (\d+)")
# "<side> must flag ... | <file>: <matches, no matches or an error>"
SIDE_ROW = re.compile(r"^(\S+) must flag [^|]*\| (.*)$")
# "<tree> must flag 0 outside this PR's files | N false positives" (or ERROR: ...)
FP_ROW = re.compile(r"^(.+) must flag 0 outside this PR's files \| (.*)$")
FP_COUNT = re.compile(r"(\d+) false positives")
INTRO = [
    "# Proof grid",
    "",
    "Every installed rule against each gate a rule must pass before it guards.",
    "PASS and FAIL come from the committed record of this exact rule text: the proof stored",
    "in its registry entry (`knack reprove` or install), or a compile-log attempt whose rule",
    "is byte-identical to the installed file. Held-out is scored again from data/heldout.",
    "NOT RUN means the input the gate needs does not exist; each is listed below with why.",
    "Tier is what the guard does on a new match today: block (a Confirmed root,",
    "pinned to this rule or confirmed before pins existed) or warn (anything else).",
    "",
]
HEADER = "| Decision | Roots | Tier | " + " | ".join(GATES) + " | Evidence |"
SEPARATOR = "|" + "---|" * (len(GATES) + 4)
UNRULED = "Decisions with no installed rule (never block or warn): {ids}"
NOT_RUN_HEADING = "NOT RUN, and the input that does not exist:"
NO_RECORD = "no committed record shows this gate on this rule text"
NO_HELDOUT = "no held-out set is committed for this PR"


class SideCount(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    files: int
    flagged: int
    errors: int = 0


class LogAttempt(BaseModel):
    # One "=== #<pr> ATTEMPT <n> ===" block: the rule it compiled and its proof rows.
    model_config = ConfigDict(frozen=True, extra="forbid")

    log: str
    pr: str
    attempt: int
    rule: str
    proof: str


class Evidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str
    sides: dict[str, SideCount]
    tree: Mark
    release: Mark
    # Gate -> why its input does not exist, as the proof recorded it.
    not_run: dict[str, str] = {}


class GridRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    repo: str
    pr: str
    root_ids: list[str]
    tier: Tier
    marks: dict[str, Mark]
    source: str
    # Each NOT RUN gate and why.
    not_run: dict[str, str]


def grid_lines(registries: list[Path], heldout: HeldOut, logs: list[Path]) -> list[str]:
    rows = grid_rows(registries, heldout, log_attempts(logs))
    table = [HEADER, SEPARATOR, *map(_row_line, rows)]
    totals = [*_totals(rows), "", *_not_run_lines(rows)]
    return [*INTRO, *table, "", *totals, "", _unruled_line(registries)]


def grid_rows(
    registries: list[Path], heldout: HeldOut, attempts: list[LogAttempt]
) -> list[GridRow]:
    # One row per installed rule, in registry order; the held-out key is the file stem.
    loaded = [(load_registry(path), path.stem) for path in registries]
    return [
        _row(registry, stem, entry, heldout, attempts)
        for registry, stem in loaded
        for entry in registry.rules
    ]


def log_attempts(logs: list[Path]) -> list[LogAttempt]:
    return [attempt for log in logs for attempt in _attempts_in(log)]


def rule_body(text: str) -> str:
    # The rule without its id line: install renames the id, nothing else.
    kept = [line for line in text.strip().splitlines() if not line.startswith("id:")]
    return "\n".join(kept).strip()


def _attempts_in(log: Path) -> list[LogAttempt]:
    # Every "=== ... ===" heading ends the block before it; only attempts are kept.
    text = log.read_text(encoding="utf-8")
    heads = list(HEADING.finditer(text))
    ends = [head.start() for head in heads[1:]] + [len(text)]
    blocks = [
        (ATTEMPT.fullmatch(h.group(1)), text[h.end() : e]) for h, e in zip(heads, ends)
    ]
    return [_attempt(log.name, found, chunk) for found, chunk in blocks if found]


def _attempt(name: str, found: re.Match[str], chunk: str) -> LogAttempt:
    # The rule YAML runs to the first blank line; the proof rows follow it.
    rule, _, proof = chunk.strip("\n").partition("\n\n")
    number, attempt = found.group(1), int(found.group(2))
    body = rule_body(rule)
    return LogAttempt(log=name, pr=number, attempt=attempt, rule=body, proof=proof)


def _row(
    registry: Registry,
    stem: str,
    entry: RegistryEntry,
    heldout: HeldOut,
    attempts: list[LogAttempt],
) -> GridRow:
    pr = entry.rule.stem.split(".")[0]
    evidence = _evidence(entry, pr, attempts)
    marks = _marks(evidence) | {"held-out": _heldout_mark(heldout.get((stem, pr)))}
    found = {"source": evidence.source if evidence else "none", "marks": marks}
    found |= {"not_run": _reasons(marks, evidence)}
    cited = {"repo": registry.repo, "pr": pr, "root_ids": entry.root_ids}
    return GridRow.model_validate(cited | found | {"tier": _tier(entry, registry)})


def _reasons(marks: dict[str, Mark], evidence: Evidence | None) -> dict[str, str]:
    # The proof's own reason, else none on record (or no held-out set committed).
    recorded = evidence.not_run if evidence else {}
    default = {gate: NO_RECORD for gate in GATES} | {"held-out": NO_HELDOUT}
    reasons = default | recorded
    return {gate: reasons[gate] for gate in GATES if marks[gate] == "NOT RUN"}


def _evidence(
    entry: RegistryEntry, pr: str, attempts: list[LogAttempt]
) -> Evidence | None:
    # The stored proof of this rule text, else the latest log attempt of this exact text.
    if entry.proof is not None and _proves_this_text(entry.proof, entry.rule):
        return _proof_evidence(entry.proof)
    body = rule_body(entry.rule.read_text(encoding="utf-8"))
    found = [a for a in attempts if a.pr == pr and a.rule == body]
    return _log_evidence(found[-1]) if found else None


def _proves_this_text(proof: RuleProof, rule: Path) -> bool:
    # An install proof predates pins and was written with the rule; a pin must match.
    return proof.rule_sha is None or proof.rule_sha == rule_sha(rule)


def _proof_evidence(proof: RuleProof) -> Evidence:
    sides = {s.side: s.model_dump(exclude={"side"}) for s in proof.sides}
    old = proof.old_release
    release = "NOT RUN" if old is None else _clean(old.false_positives, old.error)
    tree = _clean(proof.false_positives, proof.tree_error)
    found = {"sides": sides, "tree": tree, "release": release, "not_run": proof.not_run}
    return Evidence.model_validate(found | {"source": _proof_source(proof)})


def _proof_source(proof: RuleProof) -> str:
    stamp = proof.reproved_at
    return f"knack reprove {stamp[:10]}" if stamp else "install proof"


def _clean(false_positives: int, error: str | None) -> Mark:
    # An error means the scan never finished, so it cannot pass.
    return "FAIL" if error else _zero(false_positives)


def _log_evidence(attempt: LogAttempt) -> Evidence:
    rows = attempt.proof.splitlines()
    fps = [found for found in map(FP_ROW.match, rows) if found]
    tree = [f.group(2) for f in fps if not f.group(1).startswith("release ")]
    release = [f.group(2) for f in fps if f.group(1).startswith("release ")]
    source = f"{attempt.log} #{attempt.pr} attempt {attempt.attempt}"
    sides = _side_counts(rows)
    return Evidence(
        source=source, sides=sides, tree=_fp_mark(tree), release=_fp_mark(release)
    )


def _fp_mark(results: list[str]) -> Mark:
    # No row means the check never ran; an ERROR row has no count and fails.
    if not results:
        return "NOT RUN"
    counts = [FP_COUNT.fullmatch(result) for result in results]
    return "PASS" if all(c and c.group(1) == "0" for c in counts) else "FAIL"


def _zero(false_positives: int) -> Mark:
    return "PASS" if false_positives == 0 else "FAIL"


def _side_counts(rows: list[str]) -> dict[str, SideCount]:
    results: dict[str, Counter[str]] = {}
    for found in filter(None, map(SIDE_ROW.match, rows)):
        if found.group(1) in MUST_FLAG:
            results.setdefault(found.group(1), Counter())[_result(found.group(2))] += 1
    return {side: _count(counted) for side, counted in results.items()}


def _count(counted: Counter[str]) -> SideCount:
    flagged, errors = counted["flagged"], counted["error"]
    return SideCount(files=counted.total(), flagged=flagged, errors=errors)


def _result(named: str) -> str:
    # "file: 'match' (line n)" is flagged, "file: no matches" is clean, else an error.
    result = named.partition(": ")[2]
    if result == "no matches":
        return "clean"
    return "flagged" if result[:1] in ("'", '"') else "error"


def _marks(evidence: Evidence | None) -> dict[str, Mark]:
    # Held-out is added by the caller; no evidence leaves every gate not run.
    marks: dict[str, Mark] = {gate: "NOT RUN" for gate in GATES}
    if evidence is None:
        return marks
    marks |= {gate: _sides_mark(evidence.sides, n) for gate, n in SIDE_GATES.items()}
    marks |= {"0 FP tree": evidence.tree, "0 FP release": evidence.release}
    return marks


def _sides_mark(sides: dict[str, SideCount], names: tuple[str, ...]) -> Mark:
    # A side the record lacks was not run; an ast-grep error on any file fails it.
    found = [sides[name] for name in names if name in sides and sides[name].files]
    if len(found) < len(names):
        return "NOT RUN"
    held = [_holds(name, count) for name, count in zip(names, found)]
    return "PASS" if all(held) and not any(c.errors for c in found) else "FAIL"


def _holds(side: str, count: SideCount) -> bool:
    if MUST_FLAG[side]:
        return count.flagged >= MIN_FLAGGED.get(side, 1)
    return count.flagged == 0


def _heldout_mark(scored: HeldOutPr | None) -> Mark:
    # Both sets must pass the held-out bar; a set never scored is not run.
    if scored is None or (scored.same is None and scored.cross is None):
        return "NOT RUN"
    return "PASS" if scored.passed("same") and scored.passed("cross") else "FAIL"


def _tier(entry: RegistryEntry, registry: Registry) -> Tier:
    # The guard's own test: a Confirmed root whose pin holds for this rule blocks.
    roots = load_roots(registry.roots_dir)
    cited = [root for root in roots if root.id in entry.root_ids]
    blocks = any(r.status == "Confirmed" and pin_holds(r, entry.rule) for r in cited)
    return "block" if blocks else "warn"


def _row_line(row: GridRow) -> str:
    marks = " | ".join(row.marks[gate] for gate in GATES)
    named = f"{row.repo} #{row.pr} | {', '.join(row.root_ids)} | {row.tier}"
    return f"| {named} | {marks} | {row.source} |"


def _totals(rows: list[GridRow]) -> list[str]:
    counts = {gate: Counter(row.marks[gate] for row in rows) for gate in GATES}
    return [_total_line(gate, counted) for gate, counted in counts.items()]


def _total_line(gate: str, counted: Counter[str]) -> str:
    return f"{gate}: {counted['PASS']} PASS, {counted['FAIL']} FAIL, {counted['NOT RUN']} NOT RUN"


def _not_run_lines(rows: list[GridRow]) -> list[str]:
    found = [(row, gate, why) for row in rows for gate, why in row.not_run.items()]
    lines = [f"- {row.repo} #{row.pr} {gate}: {why}" for row, gate, why in found]
    return [NOT_RUN_HEADING, *(lines or ["- none"])]


def _unruled_line(registries: list[Path]) -> str:
    # Roots no installed rule cites: no gate applies, and the guard never consults them.
    loaded = [load_registry(path) for path in registries]
    cited = {i for reg in loaded for entry in reg.rules for i in entry.root_ids}
    roots = [root for reg in loaded for root in load_roots(reg.roots_dir)]
    ids = sorted(root.id for root in roots if root.id not in cited)
    return UNRULED.format(ids=", ".join(ids) or "none")
