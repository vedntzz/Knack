from fastapi.dependencies.models import Dependant
def pick_request_titles(pool: list[Dependant]) -> list[str]:
    return [d.name or "anon" for d in pool if d.computed_scope == "request"]
def any_generator_present(pool: list[Dependant]) -> bool:
    return any(d.is_gen_callable or d.is_async_gen_callable for d in pool)
def any_coroutine_present(pool: list[Dependant]) -> bool:
    return any(d.is_coroutine_callable for d in pool)