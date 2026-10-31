from fastapi.dependencies.models import Dependant, _get_computed_scope
def river_scope_list(tide_top):
    return [_get_computed_scope(dependant=x) for x in [tide_top, *tide_top.dependencies]]
def river_make():
    dep = Dependant(call=river_make, scope="request")
    return river_scope_list(dep)