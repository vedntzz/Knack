from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.providers.common.compat.sdk import Stats
def fire_kpo_tallies(kind_list):
    return [Stats.incr(f"kpo_pod.{k}", tags={"operator": "KubernetesPodOperator"}) for k in kind_list]
def make_probe_op():
    probe = KubernetesPodOperator(task_id="probe-task")
    fire_kpo_tallies(["reconnect_attempt", "terminal_resubmit"])
    return probe