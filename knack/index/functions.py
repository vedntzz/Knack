import ast
from collections.abc import Iterator
from pathlib import Path

from pydantic import BaseModel, ConfigDict, PositiveInt

from knack.index.walker import IndexerError

FUNCTION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)
SCOPE_NODES = (*FUNCTION_NODES, ast.ClassDef)


class IndexedFunction(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    file: Path
    qualname: str
    line: PositiveInt
    end_line: PositiveInt


def extract_functions(source: str, file: Path) -> list[IndexedFunction]:
    return list(_functions_under(_parse(source, file), "", file))


def _parse(source: str, file: Path) -> ast.Module:
    # ValueError covers null bytes on Python 3.11.
    try:
        return ast.parse(source, filename=str(file))
    except (SyntaxError, ValueError) as error:
        raise IndexerError(f"cannot parse {file}: {error}") from error


def _functions_under(
    node: ast.AST, prefix: str, file: Path
) -> Iterator[IndexedFunction]:
    for child in ast.iter_child_nodes(node):
        if isinstance(child, FUNCTION_NODES):
            yield _indexed(child, prefix, file)
        yield from _functions_under(child, _scope_prefix(child, prefix), file)


def _indexed(
    node: ast.FunctionDef | ast.AsyncFunctionDef, prefix: str, file: Path
) -> IndexedFunction:
    # node.lineno is the def line; decorators sit above it.
    end_line = node.end_lineno or node.lineno
    return IndexedFunction(
        file=file, qualname=prefix + node.name, line=node.lineno, end_line=end_line
    )


def _scope_prefix(node: ast.AST, prefix: str) -> str:
    # Only defs and classes add a qualname segment; if/try/with blocks do not.
    return f"{prefix}{node.name}." if isinstance(node, SCOPE_NODES) else prefix
