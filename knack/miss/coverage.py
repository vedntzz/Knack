import json
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, cast

import yaml
from pydantic import BaseModel, ConfigDict

from knack.guard.check import only_new
from knack.guard.runner import GuardRunnerError, scan_file_with_rule
from knack.pipeline.prove import GuardEdit, ProofCase
from knack.pipeline.variants import saved_variants

HELDOUT_SETS = ("same", "cross")
# Input sides v1 had to flag in its own proof.
MUST_FLAG_SIDES = ("base", "variant-violation")
BRANCH_SHOWN = 200


class CoverageInputs(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    # Files denied when the rule matches anything in them, by name.
    files: dict[str, Path] = {}
    # Edits denied when the rule matches something the file lacked before, by name.
    edits: dict[str, GuardEdit] = {}


def coverage_inputs(case: ProofCase, heldout: Path) -> CoverageInputs:
    # Proof base and variant violations, held-out violations, recorded must-fail edits.
    proof = {f"{s} {n}": p for s in MUST_FLAG_SIDES for n, p in _side(case, s)}
    held = {f"held-out {w} {n}": p for w in HELDOUT_SETS for n, p in _held(heldout, w)}
    edits = {f"guard edit {name}": e for name, e in case.guard_edits.items()}
    return CoverageInputs(files=proof | held, edits=edits)


def coverage_losses(old: str, new: str, inputs: CoverageInputs) -> list[str]:
    # Every input v1 denied stays denied; a v1 branch no input exercises stays verbatim.
    lost = sorted(denied(old, inputs) - denied(new, inputs))
    named = [f"no longer denies {name}" for name in lost]
    return named + [_dropped(b) for b in _unexercised_dropped(old, new, inputs)]


def denied(rule_yaml: str, inputs: CoverageInputs) -> set[str]:
    with _rule_file(rule_yaml) as rule:
        files = {name for name, path in inputs.files.items() if _flags(rule, path)}
        return files | {name for name, e in inputs.edits.items() if _adds(rule, e)}


def _side(case: ProofCase, side: str) -> list[tuple[str, Path]]:
    return sorted(case.sides.get(side, {}).items())


def _held(heldout: Path, which: str) -> list[tuple[str, Path]]:
    folder = heldout / which
    found = saved_variants(folder) if folder.is_dir() else {}
    return sorted(found.get("variant-violation", {}).items())


def _flags(rule: Path, path: Path) -> bool:
    # A rule ast-grep rejects denies nothing.
    try:
        return bool(scan_file_with_rule(path, rule))
    except GuardRunnerError:
        return False


def _adds(rule: Path, edit: GuardEdit) -> bool:
    # The guard's own test: a match the file lacked before.
    try:
        before = scan_file_with_rule(edit.before, rule)
        return bool(only_new(scan_file_with_rule(edit.after, rule), before))
    except GuardRunnerError:
        return False


def _unexercised_dropped(old: str, new: str, inputs: CoverageInputs) -> list[Any]:
    # No input can show a missing branch is covered, so only keeping it verbatim is safe.
    kept = _branches(new)
    dropped = [branch for branch in _branches(old) if branch not in kept]
    return [b for b in dropped if not denied(_branch_rule(old, b), inputs)]


def _branches(rule_yaml: str) -> list[Any]:
    # The top-level any's branches, or the whole rule as one; unreadable has none.
    try:
        rule: Any = yaml.safe_load(rule_yaml)["rule"]
    except (yaml.YAMLError, TypeError, KeyError):
        return []
    return list(rule["any"]) if _only_any(rule) else [rule]


def _only_any(rule: Any) -> bool:
    return isinstance(rule, dict) and list(cast(dict[str, Any], rule)) == ["any"]


def _branch_rule(rule_yaml: str, branch: Any) -> str:
    # JSON is YAML, so ast-grep reads the one-branch rule as written.
    return json.dumps(yaml.safe_load(rule_yaml) | {"rule": branch})


def _dropped(branch: Any) -> str:
    shown = json.dumps(branch)[:BRANCH_SHOWN]
    return f"dropped a v1 branch no input exercises: {shown}"


@contextmanager
def _rule_file(rule_yaml: str) -> Generator[Path]:
    # ast-grep reads rules from disk; the temp file never outlives the check.
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "rule.yml"
        path.write_text(rule_yaml, encoding="utf-8")
        yield path
