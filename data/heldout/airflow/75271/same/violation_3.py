from __future__ import annotations
from typing import Any
from airflow.providers.common.compat._resumable_job_mixin import ResumableJobMixin
def polish_items(raw: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = dict(raw)
    return out
class CedarQuillRun(ResumableJobMixin):
    def __init__(self, *, durable: Any = None, **extra: Any) -> None:
        super().__init__(durable=durable, **polish_items(extra))
        self.note = "cedar"
demo_c = CedarQuillRun(durable="yes")