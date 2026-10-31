from functools import lru_cache
from fastapi.dependencies.models import _CallIdentity, _is_gen_callable
import inspect
@lru_cache(maxsize=8192)
def massive_gen_probe(target: _CallIdentity) -> bool:
    return inspect.isgeneratorfunction(target.call)
entries = [_CallIdentity(lambda: None) for _ in range(4)]
for e in entries:
    massive_gen_probe(e)
assert massive_gen_probe.cache_info().maxsize == 8192
assert massive_gen_probe.cache_info().maxsize > 4096