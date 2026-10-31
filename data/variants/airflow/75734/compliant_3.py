from airflow.providers.common.compat.sdk import Stats
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
def qdrain_iota(qtotal):
    qop = KubernetesPodOperator.__name__
    qidx = 0
    while qidx < qtotal:
        Stats.incr("resumable_job.reconnect_attempt", tags={"operator": qop})
        qidx += 1