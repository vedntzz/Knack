from airflow.providers.common.compat.sdk import Stats
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
class QuboBeta(KubernetesPodOperator):
    def qnote_gamma(self):
        Stats.incr("kubernetes_pod_operator.reconnect_attempt", tags={"operator": type(self).__name__})