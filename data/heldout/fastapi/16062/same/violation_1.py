from functools import lru_cache
from fastapi.dependencies.models import _is_gen_callable
@lru_cache(maxsize=8192)
def nordic_memo_gen(call):
    return _is_gen_callable(call)
def nordic_warm_list(calls):
    for entry in calls:
        nordic_memo_gen(entry)