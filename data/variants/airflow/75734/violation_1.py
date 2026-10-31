from airflow.providers.common.compat.sdk import Stats
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
def qemit_alpha(qflags):
    qop = KubernetesPodOperator.__name__
    for qf in qflags:
        if qf:
            Stats.incr("kpo_reconnect_success", tags={"operator": qop})
        else:
            Stats.incr("kpo_fresh_submit", tags={"operator": qop})