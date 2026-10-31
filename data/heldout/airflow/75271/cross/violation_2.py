from typing import Any
from airflow.providers.common.compat._resumable_job_mixin import ResumableJobMixin

class EmberTrailOperator(ResumableJobMixin):
    def __init__(self, *, durable: Any = None, **kwargs: Any) -> None:
        super().__init__(durable=durable, **kwargs)
    def submit_job(self, ctx):
        return 'id-2'
    def poll_until_complete(self, eid, ctx):
        pass
    def get_job_result(self, eid, ctx):
        return eid

def build_ember_batch():
    return [EmberTrailOperator(task_id=f't{i}', durable=v).durable for v in [None, False, 'yes']]

def verify_ember_passes_string():
    return EmberTrailOperator(task_id='t', durable='yes').durable is False
