from functools import lru_cache
from fastapi.dependencies.models import _CallIdentity, _CALLABLE_CLASSIFICATION_CACHE_SIZE
@lru_cache(maxsize=4096)
def compliant_probe(entry: _CallIdentity) -> bool:
    return False
batch = [_CallIdentity(lambda: None) for _ in range(3)]
results = [compliant_probe(x) for x in batch]
assert compliant_probe.cache_info().maxsize == 4096
assert _CALLABLE_CLASSIFICATION_CACHE_SIZE == 4096
assert compliant_probe.cache_info().maxsize == _CALLABLE_CLASSIFICATION_CACHE_SIZE