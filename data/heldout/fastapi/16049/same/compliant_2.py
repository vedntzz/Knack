from fastapi.dependencies.models import Dependant, _get_computed_scope, _is_async_gen_callable, _is_coroutine_callable, _is_gen_callable
def _is_request_node(node: Dependant) -> bool:
    return _get_computed_scope(dependant=node) == "request"
def select_request_names(pool: list[Dependant]):
    return list(map(lambda d: d.name or "anon", filter(_is_request_node, pool)))
def count_call_kinds(pool: list[Dependant]) -> tuple[int, int, int]:
    gens = sum(1 for d in pool if _is_gen_callable(d.call))
    agens = sum(1 for d in pool if _is_async_gen_callable(d.call))
    coros = sum(1 for d in pool if _is_coroutine_callable(d.call))
    return (gens, agens, coros)