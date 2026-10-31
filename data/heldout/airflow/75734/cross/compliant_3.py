from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.providers.common.compat.sdk import Stats
class EpsilonKpoComplyThree(KubernetesPodOperator):
    def _emit_resume_counters(self, context):
        ti = context.get('ti') if isinstance(context, dict) else None
        base = getattr(ti, 'stats_tags', {}) if ti else {}
        tags = {**base, 'operator': 'KubernetesPodOperator'}
        metrics = {k: f'resumable_job.{k}' for k in ['fresh_submit', 'terminal_resubmit', 'already_succeeded']}
        for m in metrics.values():
            Stats.incr(m, tags=tags)
    def get_or_create_pod(self, req, ctx):
        self._emit_resume_counters(ctx)
        return super().get_or_create_pod(req, ctx)