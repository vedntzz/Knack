from airflow.providers.common.compat.sdk import Stats
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
def qhelper_delta(qcounter):
    Stats.incr(qcounter, tags={"operator": KubernetesPodOperator.__name__})
qpool_eps = [f"k8s_pod_{qs}" for qs in ["reconnect", "resubmit", "fresh"]]
for qitem in qpool_eps:
    qhelper_delta(qitem)