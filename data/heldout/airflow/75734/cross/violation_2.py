from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.providers.common.compat.sdk import Stats
class MeridianKpoBeta(KubernetesPodOperator):
    def build_pod_request_obj(self, ctx=None, dry_run=True):
        pod = super().build_pod_request_obj(ctx, dry_run=dry_run)
        names = [f'kubernetes_pod_operator.{s}' for s in ['fresh_submit', 'terminal_resubmit']]
        for n in names:
            Stats.incr(n, tags={'operator': 'KubernetesPodOperator'})
        return pod
def helper_orion_build(ctx):
    return MeridianKpoBeta(task_id='orion_task').build_pod_request_obj(ctx)