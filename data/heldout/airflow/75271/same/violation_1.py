from __future__ import annotations
from typing import Any
from airflow.providers.common.compat._resumable_job_mixin import ResumableJobMixin
class AmberRelayJob(ResumableJobMixin):
    def __init__(self, *, durable: Any = None, **extra: Any) -> None:
        picked: dict[str, Any] = {}
        for k, v in extra.items():
            picked[k] = v
        super().__init__(durable=durable, **picked)
        self.marker = durable
demo_a = AmberRelayJob(durable="yes")