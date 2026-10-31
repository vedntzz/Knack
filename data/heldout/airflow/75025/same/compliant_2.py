from airflow.api_fastapi.common.parameters import SortParam
from airflow.models import DagModel
from airflow.models.dagrun import DagRun

def cedar_sort_param():
    cols_cedar = ["dag_id", "dag_display_name", "next_dagrun"]
    picked_cedar = []
    idx = 0
    while idx < len(cols_cedar):
        picked_cedar.append(cols_cedar[idx])
        idx += 1
    return SortParam(picked_cedar, DagModel, {"last_run_state": DagRun.state, "last_run_start_date": DagRun.start_date}).dynamic_depends()
