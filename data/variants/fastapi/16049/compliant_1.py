from fastapi.dependencies.models import Dependant, _get_oauth_scopes, _get_cache_key
def sunny_scope_report(mint_root):
    out = []
    for cand in [mint_root, *mint_root.dependencies]:
        out.append(_get_oauth_scopes(dependant=cand))
    return out
def sunny_key_of(mint_root):
    return _get_cache_key(dependant=mint_root)
def sunny_sample():
    return Dependant(call=sunny_sample)