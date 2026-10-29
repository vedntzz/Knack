import re
import subprocess
from pathlib import Path
from typing import Any, cast, Literal

from pydantic import BaseModel, ConfigDict

from knack.bench.tickets import BenchTicket, rule_entry
from knack.guard.runner import RuleMatch, scan_file_with_rule
from knack.roots.store import load_roots
from knack.walk.registry import load_registry, Registry, RegistryEntry

JsonDict = dict[str, Any]
DiffLabel = Literal["rejected_path", "correct", "other"]
BlockSignal = Literal["exact", "inferred"]
PERMISSION_DENIED = "permission_denied"
GIT_TIMEOUT_SECONDS = 30
HUNK = re.compile(r"^@@ -\S+ \+(\d+)(?:,(\d+))? @@")
# Plain diffs whatever the user's git config says: a/ b/ prefixes, no colour or tools.
PLAIN = ("-c", "diff.noprefix=false", "-c", "diff.mnemonicPrefix=false", "--no-pager")
DIFF = ("diff", "--cached", "--no-ext-diff", "--no-color")


class RuleHit(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    file: str
    line: int
    end_line: int
    # True when the match overlaps a line the agent added.
    added: bool


class Outcome(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    diff: str
    diff_empty: bool
    hits: list[RuleHit]
    alternatives: list[str]
    diff_label: DiffLabel


def assess(ticket: BenchTicket, sandbox: Path, registry: Path) -> Outcome:
    # The final diff against the initial import, scored by the ticket's rule.
    rule, alternatives = rule_and_alternatives(registry, ticket.rule)
    diff, zero, changed = final_diff(sandbox)
    files = _scanned_files(sandbox, [*changed, *ticket.files])
    hits = rule_hits(sandbox, files, rule, added_lines(zero))
    return _outcome(diff, hits, alternatives)


def _outcome(diff: str, hits: list[RuleHit], alternatives: list[str]) -> Outcome:
    empty = not diff.strip()
    found = {"diff": diff, "hits": hits, "alternatives": alternatives}
    scored = {"diff_empty": empty, "diff_label": diff_label(empty, hits)}
    return Outcome.model_validate(found | scored)


def diff_label(diff_empty: bool, hits: list[RuleHit]) -> DiffLabel:
    # Rejected when an added line matches; correct only when the rule is silent.
    if any(hit.added for hit in hits):
        return "rejected_path"
    return "correct" if not hits and not diff_empty else "other"


def denies_in_export(export: JsonDict) -> list[JsonDict]:
    # Each PreToolUse hook result that blocked, tagged with the signal that showed it.
    records = cast(list[object], export.get("events") or [])
    terminals = [_hook_terminal(record) for record in records]
    vetoes = [t for t in terminals if t and t.get("event") == "PreToolUse"]
    return [t | {"signal": signal} for t in vetoes if (signal := deny_signal(t))]


def deny_signal(terminal: JsonDict) -> BlockSignal | None:
    # Muse's own markers first; unmarked output from Knack's hook is the fallback.
    effects = terminal.get("effects")
    marked = isinstance(effects, list) and PERMISSION_DENIED in effects
    if terminal.get("status") == "blocked" or marked:
        return "exact"
    return "inferred" if _acted(terminal) else None


def added_lines(diff: str) -> dict[str, set[int]]:
    # The line numbers each file gained, read from a -U0 diff.
    found, path = dict[str, set[int]](), ""
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            path = line.removeprefix("+++ b/")
        elif hunk := HUNK.match(line):
            found.setdefault(path, set()).update(_span(hunk))
    return found


def final_diff(sandbox: Path) -> tuple[str, str, list[str]]:
    # Full diff, -U0 diff and changed files, all against the first commit.
    base = _git(sandbox, "rev-list", "--max-parents=0", "HEAD").split()[0]
    _git(sandbox, "add", "-A")
    changed = _git(sandbox, *DIFF, "--name-only", "--diff-filter=d", base).split()
    return _git(sandbox, *DIFF, base), _git(sandbox, *DIFF, "-U0", base), changed


def rule_hits(
    sandbox: Path, files: list[str], rule: Path, added: dict[str, set[int]]
) -> list[RuleHit]:
    return [h for f in files for h in _file_hits(sandbox, f, rule, added.get(f, set()))]


def rule_and_alternatives(registry_path: Path, rule_id: str) -> tuple[Path, list[str]]:
    # The rule file and the rejected alternatives of the roots it enforces.
    registry = load_registry(registry_path)
    entry = rule_entry(registry, rule_id)
    if entry is None:
        raise ValueError(f"rule {rule_id} is not in {registry_path}")
    return entry.rule, _alternatives(registry, entry)


def _alternatives(registry: Registry, entry: RegistryEntry) -> list[str]:
    roots = {root.id: root for root in load_roots(registry.roots_dir)}
    found = [roots[root_id].rejected_alternative for root_id in entry.root_ids]
    return [alternative for alternative in found if alternative]


def _scanned_files(sandbox: Path, paths: list[str]) -> list[str]:
    # Python files the agent changed plus the ticket's own, as they stand now.
    return sorted({p for p in paths if p.endswith(".py") and (sandbox / p).is_file()})


def _file_hits(sandbox: Path, path: str, rule: Path, added: set[int]) -> list[RuleHit]:
    return [
        _hit(path, match, added) for match in scan_file_with_rule(sandbox / path, rule)
    ]


def _hit(path: str, match: RuleMatch, added: set[int]) -> RuleHit:
    end = match.line + match.matched_text.count("\n")
    overlaps = bool(added & set(range(match.line, end + 1)))
    return RuleHit(file=path, line=match.line, end_line=end, added=overlaps)


def _span(hunk: re.Match[str]) -> range:
    # "+start,count"; a missing count means one line, a zero count none.
    start, count = int(hunk.group(1)), int(hunk.group(2) or 1)
    return range(start, start + count)


def _hook_terminal(record: object) -> JsonDict | None:
    payload = _as_dict(_as_dict(_as_dict(record).get("envelope")).get("payload"))
    event = _as_dict(payload.get("event"))
    return event if event.get("kind") == "hook_run_terminal" else None


def _as_dict(value: object) -> JsonDict:
    # Export records are untyped JSON; anything but an object reads as empty.
    return cast(JsonDict, value) if isinstance(value, dict) else {}


def _acted(terminal: JsonDict) -> bool:
    # Arm homes hold only Knack hooks, and Knack's PreToolUse hook is silent unless it denies.
    return bool(terminal.get("effects") or str(terminal.get("stdout") or "").strip())


def _git(sandbox: Path, *args: str) -> str:
    command = ["git", *PLAIN, "-C", str(sandbox), *args]
    done = subprocess.run(
        command, capture_output=True, text=True, check=True, timeout=GIT_TIMEOUT_SECONDS
    )
    return done.stdout
