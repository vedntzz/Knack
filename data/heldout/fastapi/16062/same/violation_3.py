from functools import lru_cache
from fastapi.dependencies.models import Dependant, _get_computed_scope
@lru_cache(maxsize=32768)
def atlas_scope_memo(call):
    return _get_computed_scope(dependant=Dependant(call=call))
def atlas_build_map(calls):
    return {c: atlas_scope_memo(c) for c in calls}