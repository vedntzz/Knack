from typing import Any
from airflow.providers.common.compat._resumable_job_mixin import ResumableJobMixin

class MapleRidgeOperator(ResumableJobMixin):
    def __init__(self, *, durable: bool | None = None, **kwargs: Any) -> None:
        super().__init__(durable=durable, **kwargs)
    def submit_job(self, ctx):
        return 'maple'
    def poll_until_complete(self, eid, ctx):
        pass
    def get_job_result(self, eid, ctx):
        return 99

def assemble_maple_batch():
    return {f'task-{i}': MapleRidgeOperator(task_id=f'task-{i}', durable=v).durable for i, v in enumerate([None, True, False])}
