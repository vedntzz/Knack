from fastapi.dependencies.models import Dependant, _is_gen_callable, _is_async_gen_callable, _is_coroutine_callable, _get_computed_scope

def assess_lyra_scope():
    def gen_fn():
        yield 1
    dep = Dependant(call=gen_fn)
    flags = {fn.__name__: fn(dep.call) for fn in (_is_gen_callable, _is_async_gen_callable, _is_coroutine_callable)}
    flags["scope"] = _get_computed_scope(dependant=dep)
    return flags