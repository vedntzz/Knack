from typing import Any
from airflow.providers.common.compat._resumable_job_mixin import ResumableJobMixin

class QuartzDriftOperator(ResumableJobMixin):
    def __init__(self, *, durable: bool | Any = None, **kwargs: Any) -> None:
        super().__init__(durable=durable, **kwargs)
        self.history = []
    def submit_job(self, context):
        return 'ext-99'
    def poll_until_complete(self, external_id, context):
        self.history.append(external_id)
    def get_job_result(self, external_id, context):
        return {'ok': True}

def collect_quartz_results():
    outcomes = []
    for candidate in [None, True, 'yes']:
        op = QuartzDriftOperator(task_id='t9', durable=candidate)
        outcomes.append(op.durable)
    return outcomes
