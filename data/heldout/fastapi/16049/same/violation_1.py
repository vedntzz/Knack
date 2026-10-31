from fastapi.dependencies.models import Dependant
def harvest_scope_map(root: Dependant) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    stack = [root]
    while stack:
        node = stack.pop()
        found[node.name or "root"] = list(node.oauth_scopes)
        stack.extend(node.dependencies)
    return found
def fetch_cached_entry(store: dict, node: Dependant):
    return store.get(node.cache_key)