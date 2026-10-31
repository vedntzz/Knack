import warnings
from typing import Any
from airflow.providers.common.compat._resumable_job_mixin import ResumableJobMixin

def create_willow_operator(durable_value: bool | None = None):
    warnings.simplefilter('always')
    return WillowCreekOperator(task_id='w1', durable=durable_value)

class WillowCreekOperator(ResumableJobMixin):
    def __init__(self, *, durable: bool | None = None, **kwargs: Any) -> None:
        super().__init__(durable=durable, **kwargs)
    def submit_job(self, ctx):
        return 'willow-id'
    def poll_until_complete(self, eid, ctx):
        pass
    def get_job_result(self, eid, ctx):
        return {'result': eid}

def verify_willow_selective_forward():
    ops = [create_willow_operator(v) for v in [None, True]]
    return [o.durable for o in ops]
