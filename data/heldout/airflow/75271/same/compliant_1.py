from __future__ import annotations
from typing import Any
from airflow.providers.common.compat._resumable_job_mixin import ResumableJobMixin
class ElmStoneJob(ResumableJobMixin):
    def __init__(self, *, durable: bool | None = None, **extra: Any) -> None:
        super().__init__(durable=durable, **extra)
        self.mode = True if durable else False
ok_a = ElmStoneJob(durable=True)
check_a = ElmStoneJob()