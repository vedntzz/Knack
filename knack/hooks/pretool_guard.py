import json
import tempfile
import time
from pathlib import Path
from typing import Any

from knack.contracts.models import Root, Verdict
from knack.guard.check import check_file, fail_open, log_error_quietly

JsonDict = dict[str, Any]
WRITE_TOOL = "write_file"
EDIT_TOOL = "edit_file"
GUARD_JSON = ".knack/guard.json"
ERROR_LOG = ".knack/guard_errors.log"


def decide(event: JsonDict, registry: list[JsonDict], root: Path) -> JsonDict | None:
    # Fail open: any surprise in the hook input is logged, never blocks the edit.
    try:
        return _decide_inner(event, registry, root)
    except Exception as error:
        log_error_quietly(root / ERROR_LOG, error)
        return None


def _decide_inner(
    event: JsonDict, registry: list[JsonDict], root: Path
) -> JsonDict | None:
    content = _proposed_content(event, event_cwd(event))
    if content is None:
        return None
    return _scan_proposal(content, registry, root)


def event_cwd(event: JsonDict) -> Path:
    # tool_input.path is relative to the payload cwd, not the process cwd.
    return Path(str(event.get("cwd") or Path.cwd())).resolve()


def find_repo_root(start: Path) -> Path:
    # The nearest ancestor holding .knack/guard.json is the repo root.
    for candidate in (start, *start.parents):
        if (candidate / GUARD_JSON).is_file():
            return candidate
    raise FileNotFoundError(f"no {GUARD_JSON} at or above {start}")


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
    content: str, registry: list[JsonDict], base: Path
) -> JsonDict | None:
    # ast-grep scans a real file; the temp copy never touches the tree.
    temp = _write_temp(content)
    try:
        return _first_deny(temp, registry, base)
    finally:
        temp.unlink(missing_ok=True)


def _write_temp(content: str) -> Path:
    # ast-grep needs a real .py file; the hook never touches the tree.
    handle = tempfile.NamedTemporaryFile(suffix=".py", delete=False)
    handle.write(content.encode("utf-8"))
    handle.close()
    return Path(handle.name)


def _first_deny(temp: Path, registry: list[JsonDict], base: Path) -> JsonDict | None:
    # Entries run in order; the first deny wins.
    for entry in registry:
        verdict = _check_entry(temp, entry, base)
        if not verdict.allowed:
            return _deny(verdict.reason)
    return None


def _check_entry(temp: Path, entry: JsonDict, base: Path) -> Verdict:
    # A broken entry is logged and fails open without blinding the rest.
    try:
        rule_path = _resolve(base, str(entry["rule"]))
        root = _load_root(_resolve(base, str(entry["root"])))
        return check_file(temp, rule_path, _rule_id(rule_path), root, base / ERROR_LOG)
    except Exception as error:
        return fail_open(error, base / ERROR_LOG, time.perf_counter())


def _load_root(path: Path) -> Root:
    # Roots are frozen contract models; bad JSON fails open upstream.
    return Root.model_validate(json.loads(path.read_text(encoding="utf-8")))


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


def _load_registry(root: Path) -> list[JsonDict]:
    # Registry paths are relative to the repo root that holds guard.json.
    return json.loads((root / GUARD_JSON).read_text(encoding="utf-8"))


def run_hook(stdin_text: str) -> JsonDict | None:
    event = json.loads(stdin_text)
    root = find_repo_root(event_cwd(event))
    return decide(event, _load_registry(root), root)
