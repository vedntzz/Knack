import json
import re
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from knack.console.links import verdict_url
from knack.contracts.models import Root, Verdict
from knack.git import current_branch
from knack.guard.check import check_file, fail_open, log_error_quietly
from knack.hooks.scope import event_cwd, home_error_log, scoped_quietly
from knack.receipts.chain import (
    append_receipt,
    guard_receipt,
    human_allow,
    load_receipts,
    Receipt,
    receipts_path,
    Resolution,
)
from knack.receipts.edits import edits_dir, EditSnapshot, load_edit, save_edit
from knack.roots.store import load_roots
from knack.walk.registry import Registry

JsonDict = dict[str, Any]
RuleAndRoot = tuple[Path, Root | None]
Scan = Callable[[Path, Path | None], Any]
WRITE_TOOL = "write_file"
EDIT_TOOL = "edit_file"
DISPUTE_LINE = 'To dispute: knack argue "<your reason>"'
# The console link only loads while knack console serves it.
OPEN_CONSOLE = "(open with: knack console)"
# Muse Code's PreToolUse payload names the agent's model here (tests/hooks/fixtures).
AGENT_KEY = "model"
# Commands that settle or change what blocks; an agent must never run them on itself.
PERSON_ONLY = re.compile(
    r"\bknack(?:\.cli)?\s+(?:resolve|confirm|false-block|retire)\b"
)
FOR_A_PERSON = (
    "knack resolve, knack confirm, knack false-block and knack retire are for a person,"
    " not an agent: ask a person to run it in their own terminal."
    " The console's held page shows them the command."
)


@dataclass(frozen=True)
class Trail:
    # Where one proposal's verdicts go: the error log, and receipts when kept.
    log: Path
    receipts: Path | None
    repo: str
    file: str
    branch: str | None = None
    session_id: str | None = None
    # The saved snapshot of this proposal, when receipts are kept.
    edit_sha256: str | None = None
    # The coding agent the payload names, when it names one.
    agent: str | None = None


def run_hook(stdin_text: str) -> JsonDict | None:
    # A person-only command is denied anywhere; else silent outside the registry's clones.
    event = json.loads(stdin_text)
    if runs_person_only(event):
        return _envelope(FOR_A_PERSON)
    scoped = scoped_quietly(event)
    if scoped is None:
        return None
    return decide(event, scoped[0], home_error_log(), receipts_path(), scoped[1])


def runs_person_only(event: JsonDict) -> bool:
    # Any tool whose input carries shell text: Muse Code's bash or an equivalent.
    tool_input = event.get("tool_input")
    inputs = cast(JsonDict, tool_input) if isinstance(tool_input, dict) else {}
    command = inputs.get("command")
    return isinstance(command, str) and PERSON_ONLY.search(command) is not None


def decide(
    event: JsonDict,
    registry: Registry,
    log_path: Path,
    receipts: Path | None = None,
    root: Path | None = None,
) -> JsonDict | None:
    # Fail open: any surprise in the hook input is logged, never blocks the edit.
    try:
        return _decide_inner(event, registry, log_path, receipts, root)
    except Exception as error:
        log_error_quietly(log_path, error)
        return None


def _decide_inner(
    event: JsonDict,
    registry: Registry,
    log_path: Path,
    receipts: Path | None,
    root: Path | None,
) -> JsonDict | None:
    base = event_cwd(event)
    content = _proposed_content(event, base) if _in_root(event, base, root) else None
    if content is None:
        return None
    trail = _trail(event, base, registry.repo, log_path, receipts)
    content, current, trail = _snapshotted(content, trail)
    return _scan_proposal(content, current, _rules_with_roots(registry), trail)


def _with_snapshot(trail: Trail, after: str, before: str | None) -> Trail:
    # Best effort: a failed snapshot is logged and the receipt simply has none.
    try:
        return _snapshot_trail(trail, after, before)
    except Exception as error:
        log_error_quietly(trail.log, error)
        return trail


def _trail(
    event: JsonDict, base: Path, repo: str, log: Path, receipts: Path | None
) -> Trail:
    # Branch and session are only worth a git call when a receipt will hold them.
    target = _target(event, base)
    if receipts is None:
        return Trail(log, receipts, repo, target)
    session, agent = _named(event, "session_id"), _named(event, AGENT_KEY)
    branch = current_branch(base)
    return Trail(log, receipts, repo, target, branch, session, agent=agent)


def _named(event: JsonDict, key: str) -> str | None:
    return str(event[key]) if event.get(key) else None


def _in_root(event: JsonDict, base: Path, root: Path | None) -> bool:
    # Only files under the clone's git root are guarded; a write elsewhere (e.g.
    # /tmp) is not the repo's, so it is neither checked nor receipted. None is
    # for callers that scoped already. Other tools may carry no path at all.
    if root is None or event["tool_name"] not in (WRITE_TOOL, EDIT_TOOL):
        return True
    target = _resolve(base, str(event["tool_input"]["path"])).resolve()
    return target.is_relative_to(root.resolve())


def _current_content(target: Path) -> str | None:
    # The file before this call; a new file has none, so all its matches are new.
    return target.read_text(encoding="utf-8") if target.is_file() else None


def _target(event: JsonDict, base: Path) -> str:
    return str(_resolve(base, str(event["tool_input"]["path"])))


def _rules_with_roots(registry: Registry) -> list[RuleAndRoot]:
    # Root ids resolve through the roots store the registry names.
    by_id = {root.id: root for root in load_roots(registry.roots_dir)}
    return [(e.rule, _speaking_root(e.root_ids, by_id)) for e in registry.rules]


def _speaking_root(root_ids: list[str], by_id: dict[str, Root]) -> Root | None:
    # A Confirmed root speaks for the rule; weaker ones only advise, never block.
    known = [by_id[root_id] for root_id in root_ids if root_id in by_id]
    confirmed = [root for root in known if root.status == "Confirmed"]
    return next(iter(confirmed + known), None)


def _proposed_content(event: JsonDict, base: Path) -> str | None:
    tool_input = event["tool_input"]
    if event["tool_name"] == WRITE_TOOL:
        return _write_content(tool_input)
    if event["tool_name"] == EDIT_TOOL:
        return _edit_content(tool_input, base)
    return None


def _write_content(tool_input: JsonDict) -> str | None:
    # New files are checked too; only the suffix decides.
    if not str(tool_input["path"]).endswith(".py"):
        return None
    return str(tool_input["content"])


def _edit_content(tool_input: JsonDict, base: Path) -> str | None:
    # Applies find -> replace once in memory; the target file is only read.
    if not str(tool_input["path"]).endswith(".py"):
        return None
    current = _resolve(base, str(tool_input["path"])).read_text(encoding="utf-8")
    return current.replace(str(tool_input["find"]), str(tool_input["replace"]), 1)


def _resolve(base: Path, value: str) -> Path:
    # Absolute paths pass through; relative ones join the given base.
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    return base / candidate


def _scan_proposal(
    content: str, current: str | None, rules: list[RuleAndRoot], trail: Trail
) -> JsonDict | None:
    return _on_temps(content, current, lambda t, b: _first_deny(t, b, rules, trail))


def _on_temps(content: str, current: str | None, scan: Scan) -> Any:
    # ast-grep scans real files; the temp copies never touch the tree.
    temp = _write_temp(content)
    baseline = None if current is None else _write_temp(current)
    try:
        return scan(temp, baseline)
    finally:
        for path in (temp, baseline or temp):
            path.unlink(missing_ok=True)


def rerun_deny(
    receipts: Path, receipt_hash: str, registry: Registry, log: Path
) -> JsonDict | None:
    # Today's deny for a kept receipt: its saved edit rescanned, its own hash linked.
    receipt = _kept_receipt(receipts, receipt_hash)
    edit = _kept_edit(receipts, receipt)
    rule = _rule_for(registry, receipt.rule_id) if receipt else None
    if receipt is None or edit is None or rule is None:
        return None
    verdict = _rescan(edit, rule, log)
    return None if verdict.allowed else _deny(verdict.reason, receipt)


def _kept_receipt(receipts: Path, receipt_hash: str) -> Receipt | None:
    # A hash prefix names a receipt, as knack resolve accepts one.
    found = (r for r in load_receipts(receipts) if r.hash.startswith(receipt_hash))
    return next(found, None)


def _kept_edit(receipts: Path, receipt: Receipt | None) -> EditSnapshot | None:
    if receipt is None or receipt.edit_sha256 is None:
        return None
    return load_edit(edits_dir(receipts), receipt.edit_sha256)


def _rule_for(registry: Registry, rule_id: str) -> RuleAndRoot | None:
    pairs = _rules_with_roots(registry)
    return next((pair for pair in pairs if rule_name(pair[0]) == rule_id), None)


def _rescan(edit: EditSnapshot, rule: RuleAndRoot, log: Path) -> Verdict:
    scan: Scan = lambda t, b: _check_rule(t, b, rule[0], rule[1], log)
    verdict: Verdict = _on_temps(edit.after, edit.before, scan)
    return verdict


def _write_temp(content: str) -> Path:
    # ast-grep needs a real .py file; the hook never touches the tree.
    handle = tempfile.NamedTemporaryFile(suffix=".py", delete=False)
    handle.write(content.encode("utf-8"))
    handle.close()
    return Path(handle.name)


def _first_deny(
    temp: Path, baseline: Path | None, rules: list[RuleAndRoot], trail: Trail
) -> JsonDict | None:
    # Rules run in registry order; every verdict is receipted; the first deny wins.
    for rule_path, root in rules:
        verdict = _check_rule(temp, baseline, rule_path, root, trail.log)
        verdict = _unless_human_allowed(verdict, rule_path, trail)
        receipt = _receipt_quietly(trail, rule_path, root, verdict)
        if not verdict.allowed:
            return _deny(verdict.reason, receipt)
    return None


def _check_rule(
    temp: Path, baseline: Path | None, rule_path: Path, root: Root | None, log: Path
) -> Verdict:
    # Only matches the current file lacks can deny; a broken rule fails open alone.
    try:
        return check_file(temp, rule_path, _rule_id(rule_path), root, log, baseline)
    except Exception as error:
        return fail_open(error, log, time.perf_counter())


def _unless_human_allowed(verdict: Verdict, rule_path: Path, trail: Trail) -> Verdict:
    # A deny a person resolved as allowed, for this exact edit, passes on retry.
    if verdict.allowed or trail.receipts is None or trail.edit_sha256 is None:
        return verdict
    resolution = _human_allow_quietly(trail, rule_name(rule_path))
    if resolution is None:
        return verdict
    reason = f"resolved: allowed by {resolution.by}: {resolution.reason}"
    return verdict.model_copy(update={"allowed": True, "reason": reason})


def _human_allow_quietly(trail: Trail, rule_id: str) -> Resolution | None:
    # An unreadable chain keeps the deny: only a recorded human allow lets it through.
    try:
        return human_allow(trail.receipts or Path(), rule_id, trail.edit_sha256 or "")
    except Exception as error:
        log_error_quietly(trail.log, error)
        return None


def _receipt_quietly(
    trail: Trail, rule_path: Path, root: Root | None, verdict: Verdict
) -> Receipt | None:
    # A receipt is best effort: its failure is logged and the verdict stands.
    try:
        return _append_receipt(trail, rule_path, root, verdict)
    except Exception as error:
        log_error_quietly(trail.log, error)
        return None


def _append_receipt(
    trail: Trail, rule_path: Path, root: Root | None, verdict: Verdict
) -> Receipt | None:
    if trail.receipts is None:
        return None
    now = datetime.now(timezone.utc).isoformat()
    named = (trail.repo, trail.file, rule_name(rule_path), root, verdict, now)
    later = (trail.branch, trail.session_id, trail.edit_sha256, trail.agent)
    fields = guard_receipt(*named, *later)
    return append_receipt(trail.receipts, fields)


def rule_name(rule_path: Path) -> str:
    # A rule with no readable id is still receipted, by its file name.
    try:
        return _rule_id(rule_path)
    except Exception:
        return rule_path.name


def _rule_id(rule_path: Path) -> str:
    # ast-grep reports the id from the rule file, not the file name.
    for line in rule_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("id:"):
            return line.split(":", 1)[1].strip()
    raise ValueError(f"rule file has no id: {rule_path}")


def _deny(reason: str, receipt: Receipt | None) -> JsonDict:
    link = f"Console: {verdict_url(receipt.hash)} {OPEN_CONSOLE}\n" if receipt else ""
    return _envelope(f"{reason}\n{link}{DISPUTE_LINE}")


def _envelope(reason: str) -> JsonDict:
    # Muse Code only honors this exact deny envelope, exit 0.
    inner = {"hookEventName": "PreToolUse", "permissionDecision": "deny"}
    inner["permissionDecisionReason"] = reason
    return {"hookSpecificOutput": inner}


def _snapshotted(content: str, trail: Trail) -> tuple[str, str | None, Trail]:
    # The file before this call, and the trail pointing at the saved edit.
    current = _current_content(Path(trail.file))
    return content, current, _with_snapshot(trail, content, current)


def _snapshot_trail(trail: Trail, after: str, before: str | None) -> Trail:
    # No receipts, no snapshot: nothing would point at it.
    if trail.receipts is None:
        return trail
    edit = EditSnapshot(file=trail.file, before=before, after=after)
    return replace(trail, edit_sha256=save_edit(edits_dir(trail.receipts), edit))
