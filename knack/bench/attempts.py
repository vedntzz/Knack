import json
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, ConfigDict

from knack.bench.classify import base_text, rule_and_alternatives, run_event
from knack.guard.runner import scan_file_with_rule

JsonDict = dict[str, Any]
WRITE_TOOL = "write_file"
EDIT_TOOL = "edit_file"
# Muse's tool result text when a PreToolUse hook denied the call.
BLOCKED_PREFIX = "tool blocked by hook"


class Attempt(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    tool: str
    path: str
    # Rule match text the call proposed that the file did not already hold.
    matched: str


@dataclass(frozen=True)
class ToolWrite:
    tool: str
    path: str
    args: JsonDict
    blocked: bool

    def proposed(self, before: str) -> str:
        # The file as the guard saw it: whole content, or find -> replace once.
        if self.tool == WRITE_TOOL:
            return str(self.args["content"])
        return before.replace(str(self.args["find"]), str(self.args["replace"]), 1)


@dataclass
class Replay:
    # Files as the agent's write calls left them, starting from the sandbox base.
    sandbox: Path
    rule: Path
    files: dict[Path, str] = field(default_factory=dict[Path, str])

    def step(self, write: ToolWrite) -> list[Attempt]:
        target = _resolved(self.sandbox, write.path)
        before = self._current(target)
        proposed = write.proposed(before)
        if not write.blocked:
            self.files[target] = proposed
        found = new_matches(before, proposed, self.rule)
        return [
            Attempt(tool=write.tool, path=self._shown(target), matched=m) for m in found
        ]

    def _current(self, target: Path) -> str:
        # A blocked call never landed, so the file stays as the last allowed call left it.
        return self.files[target] if target in self.files else self._base(target)

    def _base(self, target: Path) -> str:
        if not target.is_relative_to(self.sandbox):
            return ""
        return base_text(self.sandbox, target.relative_to(self.sandbox).as_posix())

    def _shown(self, target: Path) -> str:
        inside = target.is_relative_to(self.sandbox)
        return target.relative_to(self.sandbox).as_posix() if inside else str(target)


def attempts_of_run(
    export_path: Path, sandbox: Path, registry: Path, rule_id: str
) -> list[Attempt] | None:
    # None when the export, sandbox or rule cannot be read: unknown, not "no attempt".
    try:
        rule, _ = rule_and_alternatives(registry, rule_id)
        export = json.loads(export_path.read_text(encoding="utf-8"))
        return replay_attempts(export, sandbox, rule)
    except Exception:
        return None


def replay_attempts(export: JsonDict, sandbox: Path, rule: Path) -> list[Attempt]:
    # Every .py write or edit call in order, blocked ones included, scored by the rule.
    replay = Replay(sandbox.resolve(), rule)
    return [attempt for write in tool_writes(export) for attempt in replay.step(write)]


def attempt_fields(found: list[Attempt] | None) -> JsonDict:
    return {
        "attempted": None if found is None else bool(found),
        "attempts": found or [],
    }


def tool_writes(export: JsonDict) -> list[ToolWrite]:
    events = [run_event(record) for record in _dicts(export.get("events"))]
    blocked = _blocked_call_ids(events)
    calls = [c for e in events for c in _committed_calls(e)]
    writes = [_tool_write(call, blocked) for call in calls]
    return [write for write in writes if write and write.path.endswith(".py")]


def new_matches(before: str, proposed: str, rule: Path) -> list[str]:
    # Matched text, not lines, so moving an existing match is not a new one.
    if proposed == before:
        return []
    added = Counter(match_texts(proposed, rule)) - Counter(match_texts(before, rule))
    return list(added.elements())


@lru_cache(maxsize=256)
def match_texts(content: str, rule: Path) -> tuple[str, ...]:
    # ast-grep scans a real file, so the content goes to a temp .py first.
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "proposal.py"
        path.write_text(content, encoding="utf-8")
        return tuple(m.matched_text for m in scan_file_with_rule(path, rule))


def _committed_calls(event: JsonDict) -> list[JsonDict]:
    if event.get("kind") != "assistant_tool_calls_committed":
        return []
    return _dicts(event.get("tool_calls"))


def _blocked_call_ids(events: list[JsonDict]) -> set[str]:
    batches = [e for e in events if e.get("kind") == "tool_result_batch_committed"]
    results = [r for e in batches for r in _dicts(e.get("results"))]
    blocked = [r for r in results if str(r.get("text", "")).startswith(BLOCKED_PREFIX)]
    return {str(r.get("tool_call_id")) for r in blocked}


def _tool_write(call: JsonDict, blocked: set[str]) -> ToolWrite | None:
    if call.get("name") not in (WRITE_TOOL, EDIT_TOOL):
        return None
    args = json.loads(str(call.get("args") or "{}"))
    denied = str(call.get("call_id")) in blocked
    return ToolWrite(str(call["name"]), str(args.get("path", "")), args, denied)


def _dicts(value: object) -> list[JsonDict]:
    # Export JSON is untyped; only the objects in a list are kept.
    items = cast(list[object], value) if isinstance(value, list) else []
    return [cast(JsonDict, item) for item in items if isinstance(item, dict)]


def _resolved(sandbox: Path, value: str) -> Path:
    # Relative paths join the sandbox; resolve() makes /var and /private/var one file.
    candidate = Path(value)
    return (candidate if candidate.is_absolute() else sandbox / candidate).resolve()
