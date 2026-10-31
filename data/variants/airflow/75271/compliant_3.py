from __future__ import annotations
import warnings
from airflow.providers.common.compat._resumable_job_mixin import ResumableJobMixin
class AlderBrookJob(ResumableJobMixin):
    def __init__(self, *, durable: bool | None = None, tag: str = "alder"):
        super().__init__(durable=durable)
        self.tag = tag
def spawn_alder(durable: bool | None = None):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return AlderBrookJob(durable=durable)
first_spawn = spawn_alder()
second_spawn = spawn_alder(durable=True)