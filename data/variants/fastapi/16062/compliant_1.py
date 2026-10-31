from functools import lru_cache
from fastapi.dependencies.models import _CALLABLE_CLASSIFICATION_CACHE_SIZE, _CallIdentity, _is_gen_callable_cached
@lru_cache(maxsize=_CALLABLE_CLASSIFICATION_CACHE_SIZE)
def willow_lookup(ident):
    return _is_gen_callable_cached(ident)
def willow_prime(calls):
    found = set()
    for cand in calls:
        if willow_lookup(_CallIdentity(cand)):
            found.add(cand)
    return found
def willow_demo():
    return willow_prime([str, list])