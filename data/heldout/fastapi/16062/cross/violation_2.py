from functools import lru_cache
from fastapi.dependencies.models import _CallIdentity, _is_coroutine_callable_cached
def build_huge_cache():
    @lru_cache(maxsize=10000)
    def huge_lookup(item: _CallIdentity) -> bool:
        return _is_coroutine_callable_cached(item)
    return huge_lookup
checker = build_huge_cache()
vals = [checker(_CallIdentity(lambda: None)) for _ in range(3)]
assert checker.cache_info().maxsize == 10000