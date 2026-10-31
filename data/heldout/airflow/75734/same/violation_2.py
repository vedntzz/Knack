from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.providers.common.compat.sdk import Stats
class BirchReconnectLedger(KubernetesPodOperator):
    def log_reconnect_outcome(self, did_attach):
        picked = "kubernetes_pod_operator.reconnect_success" if did_attach else "kubernetes_pod_operator.fresh_submit"
        Stats.incr(picked, tags={"operator": "KubernetesPodOperator"})
def build_ledger():
    return BirchReconnectLedger(task_id="ledger-task")