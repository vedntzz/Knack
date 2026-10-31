from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.providers.common.compat.sdk import Stats
route_table = {"hit": "resumable_job.reconnect_success", "done": "resumable_job.already_succeeded", "new": "resumable_job.fresh_submit"}
def emit_via_route(route_key):
    Stats.incr(route_table[route_key], tags={"operator": "KubernetesPodOperator"})
class CedarResumeRouter(KubernetesPodOperator):
    pass