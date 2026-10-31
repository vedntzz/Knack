import difflib
import tempfile
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Protocol

from knack.contracts.models import Root
from knack.guard.check import log_error_quietly, only_new
from knack.guard.runner import GuardRunnerError, scan_file_with_rule
from knack.hooks.pretool_guard import rule_name
from knack.hooks.scope import home_error_log
from knack.miss.cases import EditCase
from knack.miss.loop import default_loop, Log, Loop, record_and_recompile
from knack.miss.selfcheck import (
    answer_json,
    ask_judge,
    Asked,
    self_checks_path,
    settle,
    Settle,
)
from knack.pipeline.ports import GitHub, Spark
from knack.roots.store import load_roots
from knack.walk.registry import Registry

QUESTION = "the change takes the rejected path"
SKIPPED = (
    "self-check skipped: no second model (set BASETEN_API_KEY, unless --no-corroborate)"
)
AUTO_NOTE = (
    "auto: two models, asked blind, both said this change takes the rejected path"
)
# Blind: no word of the guard, the rule, its silence or the other model's answer.
PROMPT = """A team recorded this decision about their code.
Decision: {decision}
They rejected: {rejected}
In the words of {decided_by}: "{quote}"

Below is one file's change from a merged pull request. Does the code this change adds
take the rejected path? Judge only what the change adds, not code that was already there.
Reply with JSON only: {{"takes_rejected_path": true or false, "why": "one sentence"}}

{diff}
"""


class MergedFiles(Protocol):
    # The part of GitHub a self-check reads: what each merged PR changed.
    def changed_files(self, repo: str, number: int) -> list[str]: ...

    def shas(self, repo: str, number: int) -> tuple[str, str]: ...

    def file_at(self, repo: str, sha: str, path: str) -> str | None: ...


@dataclass(frozen=True)
class Watched:
    github: MergedFiles
    # Asked the same prompt, each without the other's answer.
    judges: tuple[Spark, Spark]
    settle: Settle


@dataclass(frozen=True)
class Checked:
    # A rule the guard blocks with: one of its roots is Confirmed and names a rejection.
    rule_id: str
    rule: Path
    root: Root


@dataclass(frozen=True)
class FileEdit:
    number: int
    file: str
    # None when the PR adds the file.
    before: str | None
    after: str


def self_check_quietly(
    registry_path: Path,
    registry: Registry,
    numbers: list[int],
    models: tuple[GitHub, Spark, Spark | None],
    log: Log,
) -> None:
    # Never raises, so a self-check can never keep a merge pending.
    try:
        _self_check(registry_path, registry, numbers, models, log)
    except Exception as error:
        log(f"self-check error: {type(error).__name__}: {error}")
        log_error_quietly(home_error_log(), error)


def check_merged(watched: Watched, registry: Registry, numbers: list[int]) -> None:
    # Every silent Confirmed rule, against every Python file each merged PR changed.
    edits = [e for n in numbers for e in merged_edits(watched.github, registry.repo, n)]
    for checked in confirmed_rules(registry):
        for edit in edits:
            if is_silent(checked.rule, edit):
                _judged(watched, checked, edit)


def confirmed_rules(registry: Registry) -> list[Checked]:
    roots = load_roots(registry.roots_dir)
    by_id = {
        r.id: r for r in roots if r.status == "Confirmed" and r.rejected_alternative
    }
    found = [(e, [by_id[i] for i in e.root_ids if i in by_id]) for e in registry.rules]
    return [Checked(rule_name(e.rule), e.rule, held[0]) for e, held in found if held]


def merged_edits(github: MergedFiles, repo: str, number: int) -> list[FileEdit]:
    # Removed files add no code, so only files the PR leaves behind are judged.
    base, head = github.shas(repo, number)
    files = [f for f in github.changed_files(repo, number) if f.endswith(".py")]
    sides = [
        (f, github.file_at(repo, base, f), github.file_at(repo, head, f)) for f in files
    ]
    return [FileEdit(number, f, b, a) for f, b, a in sides if a is not None and a != b]


def is_silent(rule: Path, edit: FileEdit) -> bool:
    # The guard's own test; an edit the rule cannot scan is not judged.
    with tempfile.TemporaryDirectory() as folder:
        return not _adds_a_match(rule, *_written(Path(folder), edit))


def _adds_a_match(rule: Path, before: Path, after: Path) -> bool:
    # Unscannable counts as a match, so the edit is never judged silent.
    try:
        fresh = only_new(
            scan_file_with_rule(after, rule), scan_file_with_rule(before, rule)
        )
    except GuardRunnerError:
        return True
    return bool(fresh)


def judge_prompt(root: Root, edit: FileEdit) -> str:
    fields = {"decision": root.decision, "rejected": root.rejected_alternative}
    fields |= {"decided_by": root.decided_by, "quote": root.quote}
    return PROMPT.format(**fields, diff=_diff(edit))


def takes_rejected_path(text: str) -> bool:
    return answer_json(text).get("takes_rejected_path") is True


def _self_check(
    registry_path: Path,
    registry: Registry,
    numbers: list[int],
    models: tuple[GitHub, Spark, Spark | None],
    log: Log,
) -> None:
    github, spark, partner = models
    if partner is None:
        log(SKIPPED)
        return
    loop = default_loop(github, spark, partner, registry_path, log)
    ports = _watch_settle(registry_path, loop, log)
    check_merged(Watched(github, (spark, partner), ports), registry, numbers)


def _watch_settle(registry_path: Path, loop: Loop, log: Log) -> Settle:
    run_loop = partial(record_and_recompile, loop)
    return Settle(registry_path, self_checks_path(registry_path), run_loop, log)


def _judged(watched: Watched, checked: Checked, edit: FileEdit) -> None:
    prompt = judge_prompt(checked.root, edit)
    answers = [
        ask_judge(judge, prompt, takes_rejected_path) for judge in watched.judges
    ]
    asked = Asked(trigger="watch", question=QUESTION, answers=answers)
    settle(watched.settle, _case(checked, edit), asked)


def _case(checked: Checked, edit: FileEdit) -> EditCase:
    fields = {"kind": "must-fail", "rule_id": checked.rule_id, "file": edit.file}
    fields |= {"before": edit.before, "after": edit.after, "note": AUTO_NOTE}
    return EditCase.model_validate(
        fields | {"source": f"watch PR #{edit.number} (auto)"}
    )


def _written(folder: Path, edit: FileEdit) -> tuple[Path, Path]:
    # A new file's before is empty, so all its matches are new.
    before, after = folder / "before" / edit.file, folder / "after" / edit.file
    for path, text in ((before, edit.before or ""), (after, edit.after)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return before, after


def _diff(edit: FileEdit) -> str:
    old, new = (edit.before or "").splitlines(True), edit.after.splitlines(True)
    lines = difflib.unified_diff(old, new, f"a/{edit.file}", f"b/{edit.file}")
    return "".join(lines)
