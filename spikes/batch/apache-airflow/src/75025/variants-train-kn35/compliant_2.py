from airflow.api_fastapi.common.parameters import SortParam
from airflow.models.dag import DagModel
from airflow.models.dagrun import DagRun

def juniper_make_sorter():
    seed = ["dag_id", "dag_display_name", "next_dagrun"]
    picked = []
    idx = 0
    while idx < len(seed):
        picked.append(seed[idx])
        idx += 1
    link = {"last_run_state": DagRun.state, "last_run_start_date": DagRun.start_date}
    return SortParam(picked, DagModel, link).dynamic_depends()