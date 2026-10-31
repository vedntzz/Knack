from fastapi.dependencies.models import Dependant

def collect_nova_scopes():
    def endpoint_alpha():
        pass
    dep = Dependant(call=endpoint_alpha, own_oauth_scopes=["read"], parent_oauth_scopes=["write"], scope=None)
    out = {}
    for name in ["oauth_scopes", "cache_key", "computed_scope"]:
        out[name] = getattr(dep, name)
    return out