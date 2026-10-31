from fastapi.dependencies.models import Dependant, _get_cache_key, _get_oauth_scopes
def index_scopes_flat(entry: Dependant) -> dict[str, list[str]]:
    table: dict[str, list[str]] = {}
    for kid in [entry, *entry.dependencies]:
        table[kid.name or "root"] = _get_oauth_scopes(dependant=kid)
    return table
def lookup_entry(store: dict, node: Dependant):
    return store.get(_get_cache_key(dependant=node))