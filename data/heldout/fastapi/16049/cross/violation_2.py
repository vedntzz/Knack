from fastapi.dependencies.models import Dependant

def evaluate_orion_flags():
    def sync_fn():
        pass
    async def async_fn():
        pass
    def gen_fn():
        yield 1
    deps = [Dependant(call=f) for f in (sync_fn, async_fn, gen_fn)]
    return {f.__name__: (d.is_gen_callable, d.is_async_gen_callable, d.is_coroutine_callable) for f, d in zip((sync_fn, async_fn, gen_fn), deps)}