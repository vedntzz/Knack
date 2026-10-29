import re
from pathlib import Path
from typing import Any, Literal

from knack.contracts.models import Leaf, RISK_RANK, Root, WalkResponse
from knack.guard.runner import scan_file_with_rule
from knack.index.build import Index, IndexedEdge
from knack.index.functions import IndexedFunction
from knack.walk.registry import RegistryEntry

FunctionKey = tuple[Path, str]
Hit = tuple[int, list[str]]
Risk = Literal["high", "medium", "low"]
TICKET_TOKEN = re.compile(r"[\w./-]+")
STATUS_RANK = {
    "Confirmed": 0,
    "Corroborated": 1,
    "Inferred": 2,
    "Uncorroborated": 3,
    "Unknown": 4,
}


def walk(
    ticket: str, index: Index, registry: list[RegistryEntry], roots: list[Root]
) -> WalkResponse:
    functions = _expand_one_hop(_seed_functions(ticket, index), index)
    hits = _hits_by_file({f.file for f in functions}, index.repo_root, registry)
    by_id = {root.id: root for root in roots}
    leaves = [_leaf(f, _roots_in_span(f, hits[f.file], by_id)) for f in functions]
    return _response(ticket, sorted(leaves, key=_leaf_order), by_id)


def _seed_functions(ticket: str, index: Index) -> list[IndexedFunction]:
    tokens = {token.strip(".") for token in TICKET_TOKEN.findall(ticket)}
    return [function for function in index.functions if _named_in(function, tokens)]


def _named_in(function: IndexedFunction, tokens: set[str]) -> bool:
    # A ticket names a function by its file path, qualname or bare name.
    bare = function.qualname.rpartition(".")[2]
    return not {function.file.as_posix(), function.qualname, bare}.isdisjoint(tokens)


def _expand_one_hop(
    seeds: list[IndexedFunction], index: Index
) -> list[IndexedFunction]:
    keys = {_key(function) for function in seeds}
    links = [pair for edge in index.edges if (pair := _edge_keys(edge))]
    near = {b for a, b in links if a in keys} | {a for a, b in links if b in keys}
    return [f for f in index.functions if _key(f) in keys | near]


def _key(function: IndexedFunction) -> FunctionKey:
    return function.file, function.qualname


def _edge_keys(edge: IndexedEdge) -> tuple[FunctionKey, FunctionKey] | None:
    # Unresolved edges are guesses we refuse to make, so they never link.
    target_file, target = edge.target_file, edge.target_qualname
    if edge.resolution == "unresolved" or target_file is None or target is None:
        return None
    return (edge.caller_file, edge.caller), (target_file, target)


def _hits_by_file(
    files: set[Path], repo_root: Path, registry: list[RegistryEntry]
) -> dict[Path, list[Hit]]:
    return {file: _hits_in_file(repo_root / file, registry) for file in files}


def _hits_in_file(path: Path, registry: list[RegistryEntry]) -> list[Hit]:
    return [
        (match.line, entry.root_ids)
        for entry in registry
        for match in scan_file_with_rule(path, entry.rule)
    ]


def _roots_in_span(
    function: IndexedFunction, hits: list[Hit], by_id: dict[str, Root]
) -> list[Root]:
    # Strongest first: Confirmed, Corroborated, Inferred, Uncorroborated, then lowest id.
    in_span = [ids for line, ids in hits if function.line <= line <= function.end_line]
    known = {root_id for ids in in_span for root_id in ids if root_id in by_id}
    return sorted((by_id[root_id] for root_id in known), key=_strength)


def _strength(root: Root) -> tuple[int, str]:
    return STATUS_RANK[root.status], root.id


def _leaf(function: IndexedFunction, roots: list[Root]) -> Leaf:
    place = {"file": function.file.as_posix(), "line": function.line}
    named = {**place, "function": function.qualname}
    return Leaf.model_validate({**named, **_evidence(roots)})


def _evidence(roots: list[Root]) -> dict[str, Any]:
    # The strongest root speaks for the leaf; no root means low and Unknown.
    if not roots:
        return {"risk": "low", "root_ids": [], "status": "Unknown"}
    top = roots[0]
    cited = {"root_ids": sorted(root.id for root in roots), "risk": _risk(roots)}
    return {**cited, "why": top.why, "decided_by": top.decided_by, "status": top.status}


def _risk(roots: list[Root]) -> Risk:
    # Only a Confirmed decision with a rejected alternative is high.
    if any(r.status == "Confirmed" and r.rejected_alternative for r in roots):
        return "high"
    return "medium"


def _leaf_order(leaf: Leaf) -> tuple[int, str, int]:
    return RISK_RANK[leaf.risk], leaf.file, leaf.line


def _response(ticket: str, leaves: list[Leaf], by_id: dict[str, Root]) -> WalkResponse:
    cited = sorted({root_id for leaf in leaves for root_id in leaf.root_ids})
    roots = [by_id[root_id] for root_id in cited]
    return WalkResponse(ticket=ticket, leaves=leaves, roots=roots)
