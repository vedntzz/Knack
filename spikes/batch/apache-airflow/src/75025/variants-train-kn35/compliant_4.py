from airflow.api_fastapi.common.parameters import SortParam
from airflow.models import DagModel
from airflow.models.dagrun import DagRun

def build_compliant_sort():
    ok_fields = ["dag_id", "dag_display_name", "next_dagrun"]
    translate = {"last_run_state": DagRun.state, "last_run_start_date": DagRun.start_date}
    p = SortParam(ok_fields, DagModel, translate)
    return p.dynamic_depends()

res_ok_a = build_compliant_sort()