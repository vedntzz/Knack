from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.providers.common.compat.sdk import Stats
def craft_resume_tags(phase_label):
    return {"operator": "KubernetesPodOperator", "phase": phase_label}
def emit_fresh_submit(phase_label):
    Stats.incr("resumable_job.fresh_submit", tags=craft_resume_tags(phase_label))
def make_fresh_op():
    return KubernetesPodOperator(task_id="fresh-task")