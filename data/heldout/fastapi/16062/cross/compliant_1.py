from fastapi.dependencies.models import _CALLABLE_CLASSIFICATION_CACHE_SIZE, _is_gen_callable_cached, _is_async_gen_callable_cached, _is_coroutine_callable_cached
assert _CALLABLE_CLASSIFICATION_CACHE_SIZE == 4096
def confirm_limits():
    return all(fn.cache_info().maxsize == 4096 for fn in (_is_gen_callable_cached, _is_async_gen_callable_cached, _is_coroutine_callable_cached))
assert confirm_limits()