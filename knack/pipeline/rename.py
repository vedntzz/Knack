import ast
import builtins
import io
import keyword
import random
import re
import tokenize

FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda
FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
LANGUAGE_NAMES = set(dir(builtins)) | set(keyword.kwlist) | set(keyword.softkwlist)
IDENTIFIER = re.compile(r"\w+")
STRING_PREFIX = re.compile(r"[rbuf]{1,2}", re.IGNORECASE)
Rename = tuple[ast.Name, str]


def introduced_identifiers(
    base_sources: list[str], head_sources: list[str]
) -> set[str]:
    # Head names found in no base file; builtins, keywords and dunders belong to Python.
    seen = {name for source in base_sources for name in _names(source)}
    head = {name for source in head_sources for name in _names(source)}
    return {
        n for n in head - seen if n not in LANGUAGE_NAMES and not n.startswith("__")
    }


def fresh_names(names: set[str], rng: random.Random) -> dict[str, str]:
    # Sorted so one seed always gives the same renames.
    return {name: f"_r{rng.getrandbits(40):010x}" for name in sorted(names)}


def rename_names(source: str, mapping: dict[str, str]) -> str:
    # Whole words anywhere, strings and comments too, since regex rules read all of it.
    if not mapping:
        return source
    alternatives = "|".join(map(re.escape, sorted(mapping, key=len, reverse=True)))
    words = re.compile(rf"(?<!\w)({alternatives})(?!\w)")
    return words.sub(
        lambda m: m.group() if _is_string_prefix(m) else mapping[m.group()], source
    )


def rename_locals(source: str, rng: random.Random) -> str:
    # Module names, parameters and attributes keep their spelling; function locals change.
    lines = io.StringIO(source).readlines()
    functions = _scope_functions(_own_scope(ast.parse(source)))
    renames = [
        pair for function in functions for pair in _scope_renames(function, {}, rng)
    ]
    return _splice(source, {_char_position(lines, node): new for node, new in renames})


def _names(source: str) -> list[str]:
    tokens = tokenize.generate_tokens(io.StringIO(source).readline)
    return [token.string for token in tokens if token.type == tokenize.NAME]


def _is_string_prefix(match: re.Match[str]) -> bool:
    # f"", rb"": a prefix-shaped word right before a quote opens a string.
    following = match.string[match.end() : match.end() + 1]
    return bool(STRING_PREFIX.fullmatch(match.group())) and following in ("'", '"')


def _splice(source: str, spans: dict[tuple[int, int], str]) -> str:
    # Right to left, so earlier columns on a line stay valid.
    lines = io.StringIO(source).readlines()
    for (row, col), new in sorted(spans.items(), reverse=True):
        line, old = lines[row - 1], _identifier_at(lines[row - 1], col)
        lines[row - 1] = line[:col] + new + line[col + len(old) :]
    return "".join(lines)


def _identifier_at(line: str, col: int) -> str:
    match = IDENTIFIER.match(line, col)
    if match is None:
        raise ValueError(f"no identifier at column {col}: {line!r}")
    return match.group()


def _own_scope(node: ast.AST) -> list[ast.AST]:
    # Nodes evaluated in node's own scope; nested functions and classes open their own.
    stack, nodes = list(ast.iter_child_nodes(node)), list[ast.AST]()
    while stack:
        nodes.append(stack.pop())
        if not isinstance(nodes[-1], (*FUNCTIONS, ast.ClassDef)):
            stack.extend(ast.iter_child_nodes(nodes[-1]))
    return nodes


def _scope_functions(nodes: list[ast.AST]) -> list[FunctionNode]:
    # Functions defined directly among these nodes, looking through class bodies.
    found = [n for n in nodes if isinstance(n, FUNCTIONS)]
    classes = [n for n in nodes if isinstance(n, ast.ClassDef)]
    return found + [f for c in classes for f in _scope_functions(_own_scope(c))]


def _scope_renames(
    function: FunctionNode, outer: dict[str, str], rng: random.Random
) -> list[Rename]:
    # This function's locals and the enclosing locals it reads, then its inner functions.
    nodes = _own_scope(function)
    visible = _visible_names(nodes, _parameters(function), outer, rng)
    pairs = [(n, visible[n.id]) for n in _name_nodes(nodes) if n.id in visible]
    inner = _scope_functions(nodes)
    return pairs + [p for f in inner for p in _scope_renames(f, visible, rng)]


def _visible_names(
    nodes: list[ast.AST], params: set[str], outer: dict[str, str], rng: random.Random
) -> dict[str, str]:
    # Enclosing renames this scope does not shadow, plus fresh names for its locals.
    local = _stored_names(nodes) - _declared_names(nodes)
    kept = {k: v for k, v in outer.items() if k not in local | params}
    return kept | fresh_names(local - params, rng)


def _name_nodes(nodes: list[ast.AST]) -> list[ast.Name]:
    return [n for n in nodes if isinstance(n, ast.Name)]


def _parameters(function: FunctionNode) -> set[str]:
    args = function.args
    every = [*args.posonlyargs, *args.args, *args.kwonlyargs, args.vararg, args.kwarg]
    return {arg.arg for arg in every if arg is not None}


def _stored_names(nodes: list[ast.AST]) -> set[str]:
    return {n.id for n in _name_nodes(nodes) if not isinstance(n.ctx, ast.Load)}


def _declared_names(nodes: list[ast.AST]) -> set[str]:
    declared = [n for n in nodes if isinstance(n, (ast.Global, ast.Nonlocal))]
    return {name for n in declared for name in n.names}


def _char_position(lines: list[str], node: ast.Name) -> tuple[int, int]:
    # ast columns count UTF-8 bytes; splice counts characters.
    line = lines[node.lineno - 1]
    return node.lineno, len(line.encode()[: node.col_offset].decode())
