from fastapi.dependencies.models import Dependant
class KiteInspector:
    def __init__(self, lumen_dep):
        self.lumen_dep = lumen_dep
    def kite_is_async(self):
        if self.lumen_dep.is_async_gen_callable:
            return "async-gen"
        if self.lumen_dep.is_gen_callable:
            return "gen"
        return "other"
    def kite_coro(self):
        return bool(self.lumen_dep.is_coroutine_callable)
    def kite_make(self):
        return Dependant(call=self.kite_is_async)