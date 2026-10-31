from __future__ import annotations
from typing import Any
from airflow.providers.common.compat._resumable_job_mixin import ResumableJobMixin
class FrostGlenTask(ResumableJobMixin):
    def __init__(self, *, durable: bool | None = None, **extra: Any) -> None:
        super().__init__(durable=durable, **extra)
        self.level = 0
def assemble_frost(choice: bool | None = None) -> FrostGlenTask:
    pending = [choice]
    while pending:
        val = pending.pop()
        return FrostGlenTask(durable=val)
    return FrostGlenTask()
ok_b = assemble_frost(True)