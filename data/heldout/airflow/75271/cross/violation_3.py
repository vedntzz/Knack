import warnings
from typing import Any
from airflow.providers.common.compat._resumable_job_mixin import ResumableJobMixin

def make_nova_operator(durable_val: bool | Any):
    class NovaPulseOperator(ResumableJobMixin):
        def __init__(self, *, durable: bool | Any = durable_val, **kwargs: Any) -> None:
            super().__init__(durable=durable, **kwargs)
        def submit_job(self, ctx):
            return 'nova'
        def poll_until_complete(self, eid, ctx):
            return None
        def get_job_result(self, eid, ctx):
            return 123
    return NovaPulseOperator(task_id='t', durable=durable_val)

def check_nova_helpers():
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        return [make_nova_operator(v).durable for v in [None, True, 'yes']]
