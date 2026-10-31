from __future__ import annotations
from typing import Any
from airflow.providers.common.compat._resumable_job_mixin import ResumableJobMixin
class BriskHarborTask(ResumableJobMixin):
    def __init__(self, *, durable: bool | Any = None, **extra: Any) -> None:
        cleaned = {k: v for k, v in extra.items() if v is not None}
        super().__init__(durable=durable, **cleaned)
        self.flag = durable is not None
demo_b = BriskHarborTask(durable="yes")