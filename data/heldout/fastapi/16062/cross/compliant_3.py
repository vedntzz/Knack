from fastapi.dependencies.models import _CALLABLE_CLASSIFICATION_CACHE_SIZE, _is_coroutine_callable, Dependant
from fastapi.dependencies.models import _is_gen_callable_cached
class LimitVerifier:
    def run_checks(self) -> int:
        total = 0
        for fn in [_is_gen_callable_cached]:
            total += fn.cache_info().maxsize
        return total
verifier = LimitVerifier()
assert verifier.run_checks() == 4096
assert _CALLABLE_CLASSIFICATION_CACHE_SIZE == 4096
sample = Dependant(call=lambda: None)
assert not _is_coroutine_callable(sample.call)