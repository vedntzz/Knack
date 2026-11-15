import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from knack.atomic import write_atomically

JsonDict = dict[str, Any]
# Tools that never write a file: allowed in silence, never logged as unknown.
NOT_EDITS = frozenset({"bash", "Bash", "Read", "Glob", "Grep", "LS"})
COUNTS_FILE = "hook_counts.json"
MALFORMED_KEY = "malformed_payload"


class UnknownTool(Exception):
    pass


class MalformedPayload(ValueError):
    pass


@dataclass(frozen=True)
class ProposedEdit:
    # One edit as every agent proposes it: the file and its whole text afterwards.
    path: Path
    new_content: str


Content = Callable[[JsonDict, Path], str]


@dataclass(frozen=True)
class Adapter:
    # One agent tool: where its input names the file, and how it builds the new text.
    path_key: str
    content: Content


def edit_target(event: JsonDict, base: Path) -> Path | None:
    # The file a tool would write; None for tools that write none.
    name = event.get("tool_name")
    if name in NOT_EDITS:
        return None
    adapter = _adapter(name)
    return _resolve(base, _text(_tool_input(event), adapter.path_key))


def proposed_edit(event: JsonDict, target: Path) -> ProposedEdit:
    # The target is read, never written: the edit is applied in memory only.
    adapter = _adapter(event.get("tool_name"))
    return ProposedEdit(target, adapter.content(_tool_input(event), target))


def _adapter(name: object) -> Adapter:
    if not isinstance(name, str) or name not in ADAPTERS:
        raise UnknownTool(str(name))
    return ADAPTERS[name]


def _tool_input(event: JsonDict) -> JsonDict:
    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        raise MalformedPayload(f"{event.get('tool_name')}: tool_input is not an object")
    return cast(JsonDict, tool_input)


def _text(inputs: JsonDict, key: str) -> str:
    # A missing or non-text field is a malformed payload, never a KeyError.
    value = inputs.get(key)
    if not isinstance(value, str):
        raise MalformedPayload(f"tool_input.{key} is missing or not text")
    return value


def _resolve(base: Path, value: str) -> Path:
    # Absolute paths pass through; relative ones join the payload cwd.
    candidate = Path(value)
    return candidate if candidate.is_absolute() else base / candidate


def _written(inputs: JsonDict, target: Path) -> str:
    return _text(inputs, "content")


def _muse_edit(inputs: JsonDict, target: Path) -> str:
    # Muse Code's edit_file: the first find becomes replace.
    find, replace = _text(inputs, "find"), _text(inputs, "replace")
    return target.read_text(encoding="utf-8").replace(find, replace, 1)


def _claude_edit(inputs: JsonDict, target: Path) -> str:
    return _replaced(_current_or_empty(target), inputs)


def _claude_multi_edit(inputs: JsonDict, target: Path) -> str:
    # Claude Code applies each edit to the result of the one before.
    content = _current_or_empty(target)
    for change in _edits(inputs):
        content = _replaced(content, change)
    return content


def _replaced(content: str, change: JsonDict) -> str:
    # replace_all only when it is exactly true; otherwise the first match.
    old, new = _text(change, "old_string"), _text(change, "new_string")
    count = -1 if change.get("replace_all") is True else 1
    return content.replace(old, new, count)


def _edits(inputs: JsonDict) -> list[JsonDict]:
    edits = inputs.get("edits")
    items = cast(list[object], edits) if isinstance(edits, list) else [None]
    if not all(isinstance(item, dict) for item in items):
        raise MalformedPayload("tool_input.edits is not a list of objects")
    return cast(list[JsonDict], items)


def _current_or_empty(target: Path) -> str:
    # Claude Code's Edit with an empty old_string creates a missing file.
    return target.read_text(encoding="utf-8") if target.is_file() else ""


ADAPTERS = {
    "write_file": Adapter("path", _written),
    "edit_file": Adapter("path", _muse_edit),
    "Write": Adapter("file_path", _written),
    "Edit": Adapter("file_path", _claude_edit),
    "MultiEdit": Adapter("file_path", _claude_multi_edit),
}


def count_malformed_quietly(directory: Path) -> None:
    # Best effort: a failed count never changes the verdict.
    try:
        counts = _counts(directory)
        counts[MALFORMED_KEY] = counts.get(MALFORMED_KEY, 0) + 1
        write_atomically(directory / COUNTS_FILE, json.dumps(counts) + "\n")
    except Exception:
        pass


def malformed_count(directory: Path) -> int:
    return int(_counts(directory).get(MALFORMED_KEY, 0))


def _counts(directory: Path) -> dict[str, int]:
    path = directory / COUNTS_FILE
    if not path.is_file():
        return {}
    return cast(dict[str, int], json.loads(path.read_text(encoding="utf-8")))
