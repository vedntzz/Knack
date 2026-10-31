from fastapi.dependencies.models import _is_async_gen_callable_cached, _is_coroutine_callable_cached, _is_gen_callable_cached
def cypress_verify():
    wanted = 4096
    seen = {fn.cache_info().maxsize for fn in (_is_gen_callable_cached, _is_async_gen_callable_cached, _is_coroutine_callable_cached)}
    assert seen == {wanted}
def cypress_exercise(calls):
    return sum(1 for c in calls if c is not None)