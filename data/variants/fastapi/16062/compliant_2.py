from functools import lru_cache
from fastapi.dependencies.models import _is_coroutine_callable
class HarborLedger:
    @staticmethod
    @lru_cache(maxsize=4096)
    def quarry_probe(call):
        return _is_coroutine_callable(call)
    def quarry_sweep(self, calls):
        idx = 0
        out = []
        while idx < len(calls):
            out.append(self.quarry_probe(calls[idx]))
            idx += 1
        return out
def quarry_demo():
    return HarborLedger().quarry_sweep([len, dict])