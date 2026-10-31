from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.providers.common.compat.sdk import Stats
class NimbusKpoAlpha(KubernetesPodOperator):
    def track_zephyr_events(self, ctx):
        for evt in ['reconnect_attempt', 'reconnect_success']:
            Stats.incr(f'kpo.{evt}', tags={'operator': 'KubernetesPodOperator'})
    def execute(self, context):
        self.track_zephyr_events(context)
        return super().execute(context)