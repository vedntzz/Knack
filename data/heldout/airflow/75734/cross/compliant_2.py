from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.providers.common.compat.sdk import Stats
def build_compliant_metric_delta(state):
    return f'resumable_job.{state}'
class DeltaKpoComplyTwo(KubernetesPodOperator):
    def execute(self, context):
        Stats.incr(build_compliant_metric_delta('fresh_submit'), tags={'operator': 'KubernetesPodOperator'})
        Stats.incr(build_compliant_metric_delta('already_succeeded'), tags={'operator': 'KubernetesPodOperator'})
        return super().execute(context)