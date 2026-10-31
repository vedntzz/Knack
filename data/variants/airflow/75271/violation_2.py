from __future__ import annotations
from typing import Any
from airflow.providers.common.compat._resumable_job_mixin import ResumableJobMixin
class EastfieldTask(ResumableJobMixin):
    def __init__(self, *, durable: bool | Any = None, code: str = "east"):
        super().__init__(durable=durable)
        self.code = code
brass_items = [EastfieldTask(durable=v) for v in (None, False, "yes")]
def tally_brass():
    return len(brass_items)