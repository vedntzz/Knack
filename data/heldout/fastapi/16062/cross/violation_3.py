from functools import lru_cache
from fastapi.dependencies.models import _CallIdentity, _is_async_gen_callable_cached, Dependant
def sample_gen():
    yield 1
class OversizedContainer:
    @lru_cache(maxsize=16384)
    def inspect_async(self, ident: _CallIdentity) -> bool:
        return _is_async_gen_callable_cached(ident)
holder = OversizedContainer()
tmp_dep = Dependant(call=sample_gen)
holder.inspect_async(_CallIdentity(tmp_dep.call))
assert holder.inspect_async.cache_info().maxsize == 16384