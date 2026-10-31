from fastapi.dependencies.models import Dependant, _get_security_dependencies, _uses_scopes
def explain_secure_tree(node: Dependant, depth: int = 0) -> list[str]:
    lines = [("  " * depth) + (node.name or "root")]
    if _uses_scopes(dependant=node):
        lines[0] += "*"
    for kid in _get_security_dependencies(dependant=node):
        lines.extend(explain_secure_tree(kid, depth + 1))
    return lines