import json
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from knack.contracts.models import Root, Verdict
from knack.guard.check import check_file, fail_open, log_error_quietly
from knack.hooks.scope import event_cwd, home_error_log, scoped_quietly
from knack.receipts.chain import append_receipt, guard_receipt, receipts_path
from knack.roots.store import load_roots
from knack.walk.registry import Registry

JsonDict = dict[str, Any]
RuleAndRoot = tuple[Path, Root | None]
WRITE_TOOL = "write_file"
EDIT_TOOL = "edit_file"


@dataclass(frozen=True)
class Trail:
    # Where one proposal's verdicts go: the error log, and receipts when kept.
    log: Path
    receipts: Path | None
    repo: str
    file: str


def run_hook(stdin_text: str) -> JsonDict | None:
    # Silent unless the event cwd is a clone of the registry's repo.
    event = json.loads(stdin_text)
    scoped = scoped_quietly(event)
    if scoped is None:
        return None
    return decide(event, scoped[0], home_error_log(), receipts_path())


def decide(
    event: JsonDict, registry: Registry, log_path: Path, receipts: Path | None = None
) -> JsonDict | None:
    # Fail open: any surprise in the hook input is logged, never blocks the edit.
    try:
        return _decide_inner(event, registry, log_path, receipts)
    except Exception as error:
        log_error_quietly(log_path, error)
        return None


def _decide_inner(
    event: JsonDict, registry: Registry, log_path: Path, receipts: Path | None
) -> JsonDict | None:
    base = event_cwd(event)
    content = _proposed_content(event, base)
    if content is None:
        return None
    target = _target(event, base)
    trail = Trail(log_path, receipts, registry.repo, target)
    proposal = (content, _current_content(Path(target)))
    return _scan_proposal(*proposal, _rules_with_roots(registry), trail)


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
    # ast-grep scans real files; the temp copies never touch the tree.
    temp = _write_temp(content)
    baseline = None if current is None else _write_temp(current)
    try:
        return _first_deny(temp, baseline, rules, trail)
    finally:
        for path in (temp, baseline or temp):
            path.unlink(missing_ok=True)


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
        _receipt_quietly(trail, rule_path, root, verdict)
        if not verdict.allowed:
            return _deny(verdict.reason)
    return None


def _check_rule(
    temp: Path, baseline: Path | None, rule_path: Path, root: Root | None, log: Path
) -> Verdict:
    # Only matches the current file lacks can deny; a broken rule fails open alone.
    try:
        return check_file(temp, rule_path, _rule_id(rule_path), root, log, baseline)
    except Exception as error:
        return fail_open(error, log, time.perf_counter())


def _receipt_quietly(
    trail: Trail, rule_path: Path, root: Root | None, verdict: Verdict
) -> None:
    # A receipt is best effort: its failure is logged and the verdict stands.
    try:
        _append_receipt(trail, rule_path, root, verdict)
    except Exception as error:
        log_error_quietly(trail.log, error)


def _append_receipt(
    trail: Trail, rule_path: Path, root: Root | None, verdict: Verdict
) -> None:
    if trail.receipts is None:
        return
    now = datetime.now(timezone.utc).isoformat()
    fields = guard_receipt(
        trail.repo, trail.file, _rule_name(rule_path), root, verdict, now
    )
    append_receipt(trail.receipts, fields)


def _rule_name(rule_path: Path) -> str:
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


def _deny(reason: str) -> JsonDict:
    # Muse Code only honors this exact deny envelope, exit 0.
    inner = {"hookEventName": "PreToolUse", "permissionDecision": "deny"}
    inner["permissionDecisionReason"] = reason
    return {"hookSpecificOutput": inner}
