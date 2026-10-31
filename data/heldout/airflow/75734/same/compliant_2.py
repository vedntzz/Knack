from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.providers.common.compat.sdk import Stats
def handle_resume_branch(was_hit):
    if was_hit:
        Stats.incr("resumable_job.reconnect_success", tags={"operator": "KubernetesPodOperator"})
    else:
        Stats.incr("resumable_job.terminal_resubmit", tags={"operator": "KubernetesPodOperator"})
    return KubernetesPodOperator(task_id="branch-task")