from airflow.providers.common.compat.sdk import Stats
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
class QuboEta(KubernetesPodOperator):
    def qnote_theta(self, qfound, qlive):
        qtags = {"operator": type(self).__name__}
        if not qfound:
            Stats.incr("resumable_job.fresh_submit", tags=qtags)
        elif qlive:
            Stats.incr("resumable_job.reconnect_success", tags=qtags)
        else:
            Stats.incr("resumable_job.terminal_resubmit", tags=qtags)