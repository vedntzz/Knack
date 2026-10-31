from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.providers.common.compat.sdk import Stats
class AmberLaunchTracker(KubernetesPodOperator):
    pass
def summarize_retry_flags(flag_items):
    for flag in flag_items:
        if flag == "hit":
            Stats.incr("kpo.reconnect_success", tags={"operator": "KubernetesPodOperator"})
        else:
            Stats.incr("kpo.fresh_submit", tags={"operator": "KubernetesPodOperator"})