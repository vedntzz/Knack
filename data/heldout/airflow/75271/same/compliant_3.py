from __future__ import annotations
from typing import Any
from airflow.providers.common.compat._resumable_job_mixin import ResumableJobMixin
class GroveLumenRun(ResumableJobMixin):
    def __init__(self, *, durable: bool | None = None, **extra: Any) -> None:
        try:
            super().__init__(durable=durable, **extra)
        except TypeError:
            super().__init__(**extra)
        self.state: bool | None = durable
    def describe(self) -> str:
        return "durable" if self.state else "plain"
ok_c = GroveLumenRun(durable=False)