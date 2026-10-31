from fastapi.dependencies.models import _is_gen_callable_cached, _is_async_gen_callable_cached, _is_coroutine_callable_cached
def check_quarry_limits():
    found = []
    for cached in (_is_gen_callable_cached, _is_async_gen_callable_cached, _is_coroutine_callable_cached):
        found.append(cached.cache_info().maxsize)
    assert found == [4096, 4096, 4096]