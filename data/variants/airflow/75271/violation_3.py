from __future__ import annotations
from typing import Any
from airflow.providers.common.compat._resumable_job_mixin import ResumableJobMixin
class WestQuayJob(ResumableJobMixin):
    def __init__(self, *, durable: bool | Any = None):
        super().__init__(durable=durable)
def assemble_west_batch(raw_values):
    return list(map(lambda v: WestQuayJob(durable=v), raw_values))
assembled_west = assemble_west_batch([None, True, "yes"])