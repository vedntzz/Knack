from airflow.api_fastapi.common.parameters import SortParam
from airflow.models import DagModel
from airflow.models.dagrun import DagRun

def nova_sort_factory():
    allowed_nova = ["dag_id", "dag_display_name", "next_dagrun", "state", "start_date"]
    alias_nova = {"state": DagRun.state, "start_date": DagRun.start_date}
    return SortParam(allowed_nova, DagModel, alias_nova).dynamic_depends()
