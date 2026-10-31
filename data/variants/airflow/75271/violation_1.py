from __future__ import annotations
from typing import Any
from airflow.providers.common.compat._resumable_job_mixin import ResumableJobMixin
class NorthHarborJob(ResumableJobMixin):
    def __init__(self, *, durable: Any = None, title: str = "north"):
        super().__init__(durable=durable)
        self.title = title
def build_north_trio():
    gathered = []
    for entry in [None, True, "yes"]:
        gathered.append(NorthHarborJob(durable=entry))
    return gathered