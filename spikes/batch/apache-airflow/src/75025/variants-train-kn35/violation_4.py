from airflow.api_fastapi.common.parameters import SortParam
from airflow.models import DagModel
from airflow.models.dagrun import DagRun

def build_public_sort_aliasing():
    allowed_columns = ["dag_id", "dag_display_name", "state", "start_date"]
    alias_lookup = {"state": DagRun.state, "start_date": DagRun.start_date}
    param = SortParam(allowed_columns, DagModel, alias_lookup)
    return param.dynamic_depends()

result_a = build_public_sort_aliasing()