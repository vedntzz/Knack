# Generality probes for compiled rules: rename what a PR introduced in head, and the local variables in base.
import ast, builtins, io, keyword, re, tokenize

FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
LANGUAGE_NAMES = set(dir(builtins)) | set(keyword.kwlist) | set(keyword.softkwlist)
IDENTIFIER = re.compile(r"\w+")
STRING_PREFIX = re.compile(r"[rbuf]{1,2}", re.IGNORECASE)


def name_tokens(source):
    tokens = tokenize.generate_tokens(io.StringIO(source).readline)
    return [t for t in tokens if t.type == tokenize.NAME]


def introduced_identifiers(base_sources, head_sources):
    # head names found in no base file; builtins, keywords and dunders belong to Python, not the PR
    seen = {t.string for source in base_sources for t in name_tokens(source)}
    head = {t.string for source in head_sources for t in name_tokens(source)}
    return {n for n in head - seen if n not in LANGUAGE_NAMES and not n.startswith("__")}


def fresh_names(names, rng):
    # sorted so one seed always gives the same renames
    return {name: f"_r{rng.getrandbits(40):010x}" for name in sorted(names)}


def rename_names(source, mapping):
    # whole words anywhere in the text: code, strings, comments and docstrings, since regex rules read all of it
    if not mapping:
        return source
    alternatives = "|".join(map(re.escape, sorted(mapping, key=len, reverse=True)))
    words = re.compile(rf"(?<!\w)({alternatives})(?!\w)")
    return words.sub(lambda match: match.group() if is_string_prefix(match) else mapping[match.group()], source)


def is_string_prefix(match):
    # f"", rb"": a prefix-shaped word right before a quote opens a string, it is not a name
    return bool(STRING_PREFIX.fullmatch(match.group())) and match.string[match.end():match.end() + 1] in ("'", '"')


def splice(source, spans):
    # spans: {(row, char col): new identifier}; right to left so earlier columns stay valid
    lines = io.StringIO(source).readlines()
    for (row, col), new in sorted(spans.items(), reverse=True):
        line = lines[row - 1]
        lines[row - 1] = line[:col] + new + line[col + len(IDENTIFIER.match(line, col).group()):]
    return "".join(lines)


def rename_locals(source, rng):
    # module names, parameters and attributes keep their spelling; only function-local variables change
    lines, functions = io.StringIO(source).readlines(), scope_functions(own_scope(ast.parse(source)))
    renames = [pair for function in functions for pair in scope_renames(function, {}, rng)]
    return splice(source, {char_position(lines, node): new for node, new in renames})


def own_scope(node):
    # nodes evaluated in node's own scope: nested functions and classes open scopes of their own
    stack, nodes = list(ast.iter_child_nodes(node)), []
    while stack:
        nodes.append(stack.pop())
        if not isinstance(nodes[-1], (*FUNCTIONS, ast.ClassDef)):
            stack.extend(ast.iter_child_nodes(nodes[-1]))
    return nodes


def scope_functions(nodes):
    # functions defined directly among these nodes, looking through class bodies
    found = [n for n in nodes if isinstance(n, FUNCTIONS)]
    return found + [f for c in nodes if isinstance(c, ast.ClassDef) for f in scope_functions(own_scope(c))]


def scope_renames(function, outer, rng):
    # (Name node, new name) for this function's locals and the enclosing locals it reads
    nodes, params = own_scope(function), parameters(function)
    local = stored_names(nodes) - declared_names(nodes)
    visible = {k: v for k, v in outer.items() if k not in local | params} | fresh_names(local - params, rng)
    pairs = [(n, visible[n.id]) for n in nodes if isinstance(n, ast.Name) and n.id in visible]
    return pairs + [p for f in scope_functions(nodes) for p in scope_renames(f, visible, rng)]


def parameters(function):
    args = function.args
    return {a.arg for a in [*args.posonlyargs, *args.args, *args.kwonlyargs, args.vararg, args.kwarg] if a}


def stored_names(nodes):
    return {n.id for n in nodes if isinstance(n, ast.Name) and not isinstance(n.ctx, ast.Load)}


def declared_names(nodes):
    return {name for n in nodes if isinstance(n, (ast.Global, ast.Nonlocal)) for name in n.names}


def char_position(lines, node):
    # ast columns count UTF-8 bytes; splice counts characters
    line = lines[node.lineno - 1]
    return node.lineno, len(line.encode()[:node.col_offset].decode())
