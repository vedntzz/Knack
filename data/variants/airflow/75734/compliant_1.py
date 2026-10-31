from airflow.providers.common.compat.sdk import Stats
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
def qrecord_zeta(qextra):
    qtags = {"operator": KubernetesPodOperator.__name__} | dict(qextra)
    Stats.incr("resumable_job.fresh_submit", tags=qtags)