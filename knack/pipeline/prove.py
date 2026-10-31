import difflib
import json
import random
import subprocess
import tempfile
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from knack.guard.check import only_new
from knack.guard.runner import (
    AST_GREP,
    GuardRunnerError,
    scan_file_with_rule,
    SUCCESS_EXIT_CODES,
)
from knack.pipeline.rename import (
    fresh_names,
    introduced_identifiers,
    rename_locals,
    rename_names,
)

Sides = dict[str, dict[str, Path]]
TREE_TIMEOUT = 600
FP_SHOWN = 5
# Whether each side must be flagged (True) or never flagged (False).
MUST_FLAG = {
    "base": True,
    "head": False,
    "rename-base": True,
    "rename-head": False,
    "variant-violation": True,
    "variant-compliant": False,
}
# Real agent edits the guard must deny: each needs a match its file lacked before.
EDIT_SIDE = "guard-edit"
# Real agent edits the guard must allow: none may add a match its file lacked.
ALLOW_SIDE = "guard-allow"
# Files a must-flag side needs flagged; 1 unless listed.
MIN_FLAGGED = {"variant-violation": 2}
SIDE_NOTES = {
    "rename-base": " (base with its local variables renamed)",
    "rename-head": " (head with every identifier this PR introduced renamed to _r... names)",
    "variant-violation": " (fresh violation written apart from the PR; >=2 of 3 must be flagged)",
    "variant-compliant": " (fresh compliant code written apart from the PR)",
    EDIT_SIDE: " (a real agent edit the guard must deny; only matches the file lacked before count)",
    ALLOW_SIDE: " (a real agent edit the guard must allow; only matches the file lacked before count)",
}
EDIT_MISS = "(the guard must deny it; your rule matches only code the file already had)"
ALLOW_MISS = "(the guard must allow it; your rule flags code this edit adds)"
VARIANT_MISSES = {
    "variant-violation": "MISSED VIOLATION (the rule must flag this)",
    "variant-compliant": "FLAGGED COMPLIANT CODE (the rule must allow this)",
}


class SideRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    side: str
    name: str
    matches: list[str]
    error: str | None = None


class GuardEdit(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    before: Path
    after: Path


class ProofCase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sides: Sides
    changed: list[str]
    tree: Path
    # The previous release checkout; None skips the old-release check.
    old_ref: str | None = None
    old_tree: Path | None = None
    # Real edits the guard must deny, by file name; empty skips the check.
    guard_edits: dict[str, GuardEdit] = {}
    # Real edits the guard must allow (false blocks), by name; empty skips the check.
    guard_allows: dict[str, GuardEdit] = {}


class OldRelease(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ref: str
    false_positives: list[str]
    error: str | None = None


class Proof(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rows: list[SideRow]
    false_positives: list[str]
    tree_error: str | None = None
    old_release: OldRelease | None = None


def verifier_sides(
    number: int,
    base: dict[str, Path],
    head: dict[str, Path],
    out: Path,
    variants: Sides,
) -> Sides:
    # Rename and variant sides catch rules that memorize spellings, not structure.
    renamed = _renamed_sides(base, head, random.Random(number), out)
    return {"base": base, "head": head, **renamed, **variants}


def prove(rule_yaml: str, case: ProofCase) -> Proof:
    with _rule_file(rule_yaml) as rule_path:
        rows = _rows(rule_path, case)
        found, tree_error = _tree_false_positives(rule_path, case.tree, case.changed)
        old = _old_release(rule_path, case)
    return Proof(
        rows=rows, false_positives=found, tree_error=tree_error, old_release=old
    )


def scan_sides(rule_yaml: str, sides: Sides) -> list[SideRow]:
    # The given files only, no tree: the held-out check scores variants alone.
    with _rule_file(rule_yaml) as rule_path:
        return [_scan_row(rule_path, side, path) for side, path in _files(sides)]


def passed(proof: Proof) -> bool:
    return not failed_checks(proof)


def side_ok(rows: list[SideRow]) -> dict[str, bool]:
    # A must-flag side needs enough flagged files; a must-not side fails on any flag.
    flagged = {
        side: sum(1 for r in rows if r.side == side and r.matches) for side in MUST_FLAG
    }
    return {side: _side_holds(side, flagged[side]) for side in MUST_FLAG}


def failed_checks(proof: Proof) -> list[str]:
    # Rule errors first, then failing sides, then default-branch and old-release FPs.
    old = proof.old_release
    errors = [proof.tree_error, old and old.error, *(r.error for r in proof.rows)]
    rejected = [f"ast-grep rejected the rule: {e.splitlines()[0]}" for e in errors if e]
    sides = [side for side, ok in side_ok(proof.rows).items() if not ok]
    branch = _false_positive_check(proof.false_positives, "the default branch")
    edits = edit_checks(proof.rows)
    return rejected[:1] + sides + edits + branch + _old_release_check(old)


def feedback(proof: Proof, case: ProofCase) -> str:
    # What the compiler sees on retry: every side, the tree, and wrong variants' source.
    rows = "\n".join(_row_report(row) for row in proof.rows)
    trees = _tree_report(proof) + _old_release_report(proof.old_release)
    variants = _variant_feedback(proof, case.sides)
    return f"{rows}\n{trees}{variants}{_edit_feedback(proof, case)}"


def _rows(rule_path: Path, case: ProofCase) -> list[SideRow]:
    sides = [_scan_row(rule_path, side, path) for side, path in _files(case.sides)]
    edits = [_edit_row(rule_path, EDIT_SIDE, n, e) for n, e in case.guard_edits.items()]
    allows = [
        _edit_row(rule_path, ALLOW_SIDE, n, e) for n, e in case.guard_allows.items()
    ]
    return sides + edits + allows


def _edit_row(rule_path: Path, side: str, name: str, edit: GuardEdit) -> SideRow:
    # The guard's own test: matches compared by text with the file before the edit.
    try:
        before = scan_file_with_rule(edit.before, rule_path)
        fresh = only_new(scan_file_with_rule(edit.after, rule_path), before)
    except GuardRunnerError as error:
        return SideRow(side=side, name=name, matches=[], error=str(error))
    shown = [f"{m.matched_text!r} (line {m.line})" for m in fresh]
    return SideRow(side=side, name=name, matches=shown)


def edit_checks(rows: list[SideRow]) -> list[str]:
    # Must-deny edits that add no new match, then must-allow edits that add one.
    misses = [f"guard edit {name} adds no new match" for name in _missed(rows)]
    return misses + [f"guard allow {name} adds a new match" for name in _blocked(rows)]


def _false_positive_check(false_positives: list[str], where: str) -> list[str]:
    if not false_positives:
        return []
    return [f"{len(false_positives)} false positives on {where}"]


def _old_release_check(old: OldRelease | None) -> list[str]:
    if old is None:
        return []
    return _false_positive_check(old.false_positives, f"release {old.ref}")


def _old_release(rule_path: Path, case: ProofCase) -> OldRelease | None:
    # Released code the PR never touched must not be flagged either.
    if case.old_ref is None or case.old_tree is None:
        return None
    found, error = _tree_false_positives(rule_path, case.old_tree, case.changed)
    return OldRelease(ref=case.old_ref, false_positives=found, error=error)


def _files(sides: Sides) -> list[tuple[str, tuple[str, Path]]]:
    return [(side, item) for side, named in sides.items() for item in named.items()]


def _side_holds(side: str, flagged: int) -> bool:
    return flagged >= MIN_FLAGGED.get(side, 1) if MUST_FLAG[side] else flagged == 0


def _renamed_sides(
    base: dict[str, Path], head: dict[str, Path], rng: random.Random, out: Path
) -> Sides:
    fresh = fresh_names(introduced_identifiers(_texts(base), _texts(head)), rng)
    by_locals = _rewritten(base, lambda s: rename_locals(s, rng), out / "rename-base")
    by_fresh = _rewritten(head, lambda s: rename_names(s, fresh), out / "rename-head")
    return {"rename-base": by_locals, "rename-head": by_fresh}


def _texts(files: dict[str, Path]) -> list[str]:
    return [path.read_text(encoding="utf-8") for path in files.values()]


def _rewritten(
    files: dict[str, Path], transform: Callable[[str], str], out: Path
) -> dict[str, Path]:
    # Same relative paths under out, so path-scoped rules see the same filenames.
    for name, path in files.items():
        (out / name).parent.mkdir(parents=True, exist_ok=True)
        (out / name).write_text(transform(path.read_text(encoding="utf-8")), "utf-8")
    return {name: out / name for name in files}


@contextmanager
def _rule_file(rule_yaml: str) -> Generator[Path]:
    # ast-grep reads rules from disk; the temp file never outlives the proof.
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "rule.yml"
        path.write_text(rule_yaml, encoding="utf-8")
        yield path


def _scan_row(rule_path: Path, side: str, file: tuple[str, Path]) -> SideRow:
    # An ast-grep failure is recorded on the row, so a broken rule cannot pass.
    name, path = file
    try:
        matches = scan_file_with_rule(path, rule_path)
    except GuardRunnerError as error:
        return SideRow(side=side, name=name, matches=[], error=str(error))
    shown = [f"{m.matched_text!r} (line {m.line})" for m in matches]
    return SideRow(side=side, name=name, matches=shown)


def _tree_false_positives(
    rule_path: Path, tree: Path, changed: list[str]
) -> tuple[list[str], str | None]:
    # Matches on a whole checkout outside the PR's own files.
    try:
        matches = _scan_tree(rule_path, tree)
    except (GuardRunnerError, OSError, subprocess.TimeoutExpired, ValueError) as error:
        return [], str(error)
    rows = [(str(Path(m["file"]).relative_to(tree)), m) for m in matches]
    return [_fp_line(path, m) for path, m in rows if path not in changed], None


def _scan_tree(rule_path: Path, tree: Path) -> list[dict[str, Any]]:
    # The guard runner's 2s timeout is for single files; a whole tree gets 10 minutes.
    args = [str(AST_GREP), "scan", "--rule", str(rule_path), "--json", str(tree)]
    done = subprocess.run(args, capture_output=True, text=True, timeout=TREE_TIMEOUT)
    if done.returncode not in SUCCESS_EXIT_CODES:
        raise GuardRunnerError(f"ast-grep exited {done.returncode}: {done.stderr}")
    matches = [m for m in json.loads(done.stdout or "[]") if m["file"].endswith(".py")]
    return sorted(matches, key=lambda m: (m["file"], m["range"]["start"]["line"]))


def _fp_line(path: str, match: dict[str, Any]) -> str:
    line = match["range"]["start"]["line"] + 1
    return f"{path}:{line}  {' '.join(str(match['lines']).split())[:160]}"


def _row_report(row: SideRow) -> str:
    must_not = MUST_FLAG.get(row.side) is False or row.side == ALLOW_SIDE
    expected = "must flag 0" if must_not else "must flag >=1"
    result = row.error or ", ".join(row.matches) or "no matches"
    return f"{row.side} {expected}{SIDE_NOTES.get(row.side, '')} | {row.name}: {result}"


def _tree_report(proof: Proof) -> str:
    return _fp_report("default branch", proof.false_positives, proof.tree_error)


def _old_release_report(old: OldRelease | None) -> str:
    if old is None:
        return ""
    return "\n" + _fp_report(f"release {old.ref}", old.false_positives, old.error)


def _fp_report(label: str, false_positives: list[str], error: str | None) -> str:
    if error:
        return f"{label} must flag 0 | ERROR: {error}"
    count = f"{len(false_positives)} false positives"
    shown = "".join(f"\n  {fp}" for fp in false_positives[:FP_SHOWN])
    return f"{label} must flag 0 outside this PR's files | {count}{shown}"


def _variant_feedback(proof: Proof, sides: Sides) -> str:
    # The wrong variants' source, so the compiler sees the shapes its rule got wrong.
    wrong = [r for r in proof.rows if r.side in VARIANT_MISSES and _wrong(r)]
    return "".join(_variant_block(r, sides[r.side][r.name]) for r in wrong)


def _wrong(row: SideRow) -> bool:
    return bool(row.matches) != MUST_FLAG[row.side]


def _variant_block(row: SideRow, path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    return f"\n\n{VARIANT_MISSES[row.side]} {row.name}:\n{source}"


def _edit_feedback(proof: Proof, case: ProofCase) -> str:
    # A missed or falsely blocked edit is shown as its diff, so the compiler sees it.
    missed = [_missed_block(n, case.guard_edits[n]) for n in _missed(proof.rows)]
    blocked = [_blocked_block(n, case.guard_allows[n]) for n in _blocked(proof.rows)]
    return "".join(missed + blocked)


def _edit_block(name: str, edit: GuardEdit, heading: str, why: str) -> str:
    before = edit.before.read_text(encoding="utf-8").splitlines(keepends=True)
    after = edit.after.read_text(encoding="utf-8").splitlines(keepends=True)
    diff = "".join(difflib.unified_diff(before, after, "before", "after"))
    return f"\n\n{heading} {name} {why}:\n{diff}"


def _missed(rows: list[SideRow]) -> list[str]:
    return [r.name for r in rows if r.side == EDIT_SIDE and not r.matches]


def _blocked(rows: list[SideRow]) -> list[str]:
    return [r.name for r in rows if r.side == ALLOW_SIDE and r.matches]


def _missed_block(name: str, edit: GuardEdit) -> str:
    return _edit_block(name, edit, "MISSED GUARD EDIT", EDIT_MISS)


def _blocked_block(name: str, edit: GuardEdit) -> str:
    return _edit_block(name, edit, "FALSE BLOCK", ALLOW_MISS)
