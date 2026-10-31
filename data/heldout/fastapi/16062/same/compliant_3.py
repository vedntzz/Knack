from functools import lru_cache
from fastapi.dependencies.models import _is_async_gen_callable
@lru_cache(maxsize=4096)
def willow_memo_asyncgen(call):
    return _is_async_gen_callable(call)
def willow_scan(calls):
    idx = 0
    while idx < len(calls):
        willow_memo_asyncgen(calls[idx])
        idx += 1