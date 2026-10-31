from __future__ import annotations
from airflow.providers.common.compat._resumable_job_mixin import ResumableJobMixin
class BirchGroveJob(ResumableJobMixin):
    def __init__(self, *, durable: bool | None = None):
        super().__init__(durable=durable)
    def portray(self):
        return f"birch:{self.durable}"
grove_lookup = {k: BirchGroveJob(durable=v).portray() for k, v in {"alpha": None, "beta": False}.items()}