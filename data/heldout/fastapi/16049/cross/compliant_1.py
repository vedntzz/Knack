from fastapi.dependencies.models import Dependant, _get_oauth_scopes, _get_cache_key, _get_computed_scope

def build_quasar_state():
    def handler_beta():
        pass
    dep = Dependant(call=handler_beta, own_oauth_scopes=["read"], parent_oauth_scopes=["write"])
    results = {}
    for fn, label in [(_get_oauth_scopes, "scopes"), (_get_cache_key, "key"), (_get_computed_scope, "scope")]:
        results[label] = fn(dependant=dep)
    return results