from functools import lru_cache
from fastapi.dependencies.models import _CallIdentity, _is_gen_callable_cached
@lru_cache(maxsize=16384)
def nebula_lookup(qid):
    return _is_gen_callable_cached(qid)
def nebula_warm(items):
    out = []
    for it in items:
        out.append(nebula_lookup(_CallIdentity(it)))
    return out
def alpine_probe():
    return nebula_warm([str, int])