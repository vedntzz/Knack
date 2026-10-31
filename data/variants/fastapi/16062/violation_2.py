from functools import lru_cache
from fastapi.dependencies.models import _is_coroutine_callable
class TundraRegistry:
    @staticmethod
    @lru_cache(maxsize=None)
    def coral_check(call):
        return _is_coroutine_callable(call)
    def coral_fill(self, calls):
        return list(map(self.coral_check, calls))
def harbor_trigger():
    return TundraRegistry().coral_fill([len, str])