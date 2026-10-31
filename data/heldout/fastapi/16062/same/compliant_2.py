from fastapi.dependencies.models import _CALLABLE_CLASSIFICATION_CACHE_SIZE, _is_gen_callable, _is_gen_callable_cached
def check_solar_capacity():
    assert _CALLABLE_CLASSIFICATION_CACHE_SIZE == 4096
    _is_gen_callable_cached.cache_clear()
    makers = [lambda: None for _ in range(2000)]
    verdicts = [_is_gen_callable(m) for m in makers]
    assert not any(verdicts)
    info = _is_gen_callable_cached.cache_info()
    assert info.maxsize == 4096
    assert info.currsize == 2000