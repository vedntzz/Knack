from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.providers.common.compat.sdk import Stats
class LumenKpoComplyOne(KubernetesPodOperator):
    def record_solar_events(self, ctx):
        tags = {'operator': 'KubernetesPodOperator'}
        for name in ['resumable_job.reconnect_attempt', 'resumable_job.reconnect_success']:
            Stats.incr(name, tags=tags)
    def get_or_create_pod(self, pod_req, context):
        self.record_solar_events(context)
        return super().get_or_create_pod(pod_req, context)