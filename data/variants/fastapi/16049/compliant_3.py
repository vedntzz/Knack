from fastapi.dependencies.models import Dependant, _is_coroutine_callable, _is_gen_callable, _is_async_gen_callable
class GroveChecker:
    def __init__(self, fern_call):
        self.fern_call = fern_call
    def grove_kind(self):
        if _is_async_gen_callable(self.fern_call):
            return "async-gen"
        if _is_gen_callable(self.fern_call):
            return "gen"
        return "coro" if _is_coroutine_callable(self.fern_call) else "plain"
def grove_sample():
    return Dependant(call=grove_sample)