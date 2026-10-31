from functools import lru_cache
from fastapi.dependencies.models import _is_coroutine_callable
class HarborRegistry:
    @staticmethod
    @lru_cache(maxsize=16384)
    def probe_routine(call):
        return _is_coroutine_callable(call)
    def warm_all(self, calls):
        return [self.probe_routine(c) for c in calls]