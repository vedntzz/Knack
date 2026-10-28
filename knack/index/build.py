from collections import defaultdict
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from knack.index.calls import extract_calls, IndexedCall
from knack.index.functions import extract_functions, IndexedFunction
from knack.index.walker import find_python_files, IndexerError

Resolution = Literal["same_file", "unique_name", "unresolved"]
FileIndex = tuple[list[IndexedFunction], list[IndexedCall]]


class IndexedEdge(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    caller_file: Path
    caller: str
    callee_text: str
    target_file: Path | None = None
    target_qualname: str | None = None
    resolution: Resolution


class Index(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    repo_root: Path
    functions: list[IndexedFunction]
    edges: list[IndexedEdge]
    skipped: list[Path]


def build_index(repo_root: Path) -> Index:
    files = find_python_files(repo_root)
    extracted = {file: _extract_file(repo_root / file, file) for file in files}
    parsed = [pair for pair in extracted.values() if pair is not None]
    functions = [function for found, _ in parsed for function in found]
    edges = _resolve_all([call for _, calls in parsed for call in calls], functions)
    skipped = [file for file, pair in extracted.items() if pair is None]
    return Index(repo_root=repo_root, functions=functions, edges=edges, skipped=skipped)


def write_index(index: Index, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(index.model_dump_json(indent=2))


def load_index(path: Path) -> Index:
    return Index.model_validate_json(path.read_text())


def _extract_file(path: Path, file: Path) -> FileIndex | None:
    # Unparseable or non-UTF-8 files are skipped, never fatal.
    try:
        source = path.read_text(encoding="utf-8")
        return extract_functions(source, file), extract_calls(source, file)
    except (IndexerError, UnicodeDecodeError):
        return None


def _resolve_all(
    calls: list[IndexedCall], functions: list[IndexedFunction]
) -> list[IndexedEdge]:
    by_qualname = _group_by_qualname(functions)
    return [_resolve(call, by_qualname) for call in calls]


def _group_by_qualname(
    functions: list[IndexedFunction],
) -> dict[str, list[IndexedFunction]]:
    groups: defaultdict[str, list[IndexedFunction]] = defaultdict(list)
    for function in functions:
        groups[function.qualname].append(function)
    return groups


def _resolve(
    call: IndexedCall, by_qualname: dict[str, list[IndexedFunction]]
) -> IndexedEdge:
    # Same file wins; a cross-file guess is taken only for a bare, unique name.
    candidates = by_qualname.get(_target_qualname(call), [])
    same_file = [function for function in candidates if function.file == call.file]
    if same_file:
        return _resolved(call, same_file[0], "same_file")
    if len(candidates) == 1 and "." not in call.callee:
        return _resolved(call, candidates[0], "unique_name")
    return _unresolved(call)


def _target_qualname(call: IndexedCall) -> str:
    # self.m() inside Class.method targets Class.m; other dotted callees get "".
    receiver, _, attribute = call.callee.partition(".")
    if not attribute:
        return call.callee
    scope = call.caller.rpartition(".")[0]
    is_self_method = receiver == "self" and scope and "." not in attribute
    return f"{scope}.{attribute}" if is_self_method else ""


def _resolved(
    call: IndexedCall, target: IndexedFunction, resolution: Resolution
) -> IndexedEdge:
    target_fields = {"target_file": target.file, "target_qualname": target.qualname}
    return _unresolved(call).model_copy(
        update={**target_fields, "resolution": resolution}
    )


def _unresolved(call: IndexedCall) -> IndexedEdge:
    return IndexedEdge(
        caller_file=call.file,
        caller=call.caller,
        callee_text=call.callee,
        resolution="unresolved",
    )
