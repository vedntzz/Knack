from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.providers.common.compat.sdk import Stats
def make_kpo_metric_zeta(suffix):
    return f'kpo_specific_{suffix}'
class ZetaKpoGamma(KubernetesPodOperator):
    def get_or_create_pod(self, pod_req, context):
        Stats.incr(make_kpo_metric_zeta('attempt'), tags={'operator': 'KubernetesPodOperator'})
        Stats.incr(make_kpo_metric_zeta('success'))
        return super().get_or_create_pod(pod_req, context)
def trigger_zeta_flow(ctx, req):
    return ZetaKpoGamma(task_id='zeta_task').get_or_create_pod(req, ctx)