from functools import lru_cache
from fastapi.dependencies.models import _CallIdentity, _is_async_gen_callable_cached
@lru_cache(maxsize=65536)
def mesa_fetch(ident):
    return _is_async_gen_callable_cached(ident)
def mesa_bulk(calls):
    return {c: mesa_fetch(_CallIdentity(c)) for c in calls}
def mesa_demo():
    return mesa_bulk([str, bytes])