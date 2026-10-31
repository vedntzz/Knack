from typing import Any
from airflow.providers.common.compat._resumable_job_mixin import ResumableJobMixin

class CedarHollowOperator(ResumableJobMixin):
    def __init__(self, *, durable: bool | None = None, **kwargs: Any) -> None:
        if durable is not None:
            kwargs['durable'] = durable
        super().__init__(durable=durable, **kwargs)
        self.log = []
    def submit_job(self, context):
        return 'cedar-1'
    def poll_until_complete(self, external_id, context):
        self.log.append(external_id)
    def get_job_result(self, external_id, context):
        return 'done'

def run_cedar_loop():
    vals = []
    for flag in [None, True, False]:
        op = CedarHollowOperator(task_id='t', durable=flag)
        vals.append(op.durable)
    return vals
