from __future__ import annotations
from airflow.providers.common.compat._resumable_job_mixin import ResumableJobMixin
class CedarFallsJob(ResumableJobMixin):
    def __init__(self, *, durable: bool | None = None, note: str = "cedar"):
        if durable is None:
            super().__init__()
        else:
            super().__init__(durable=durable)
        self.note = note
def launch_cedar_pair():
    pending = [None, True]
    idx = 0
    made = []
    while idx < len(pending):
        made.append(CedarFallsJob(durable=pending[idx]))
        idx += 1
    return made