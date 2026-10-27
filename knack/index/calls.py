import ast
from collections.abc import Iterator
from pathlib import Path

from pydantic import BaseModel, ConfigDict, PositiveInt

from knack.index.functions import parse_module, SCOPE_NODES

MODULE_CALLER = "<module>"
UNNAMED_CALLEE = "<expr>"

ScopeNode = ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef


class IndexedCall(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    file: Path
    caller: str
    callee: str
    line: PositiveInt


def extract_calls(source: str, file: Path) -> list[IndexedCall]:
    return list(_calls_under(parse_module(source, file), "", file))


def _calls_under(node: ast.AST, scope: str, file: Path) -> Iterator[IndexedCall]:
    for child in ast.iter_child_nodes(node):
        yield from _calls_at(child, scope, file)


def _calls_at(node: ast.AST, scope: str, file: Path) -> Iterator[IndexedCall]:
    if isinstance(node, ast.Call):
        yield _indexed(node, scope, file)
    if isinstance(node, SCOPE_NODES):
        yield from _calls_in_scope_node(node, scope, file)
    else:
        yield from _calls_under(node, scope, file)


def _calls_in_scope_node(
    node: ScopeNode, scope: str, file: Path
) -> Iterator[IndexedCall]:
    # Decorators run in the enclosing scope; signature and body belong to node.
    inner = f"{scope}.{node.name}" if scope else node.name
    for child in ast.iter_child_nodes(node):
        child_scope = scope if child in node.decorator_list else inner
        yield from _calls_at(child, child_scope, file)


def _indexed(node: ast.Call, scope: str, file: Path) -> IndexedCall:
    return IndexedCall(
        file=file,
        caller=scope or MODULE_CALLER,
        callee=_callee_name(node.func),
        line=node.lineno,
    )


def _callee_name(func: ast.expr) -> str:
    # Only Name/Attribute chains have a static name; calls, subscripts etc. do not.
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return f"{_callee_name(func.value)}.{func.attr}"
    return UNNAMED_CALLEE
