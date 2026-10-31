from airflow.api_fastapi.common.parameters import SortParam
from airflow.models import DagModel
from airflow.models.dagrun import DagRun

class AliasedDagSort(SortParam):
    def __init__(self):
        super().__init__(
            ["dag_id", "next_dagrun", "state", "start_date"],
            DagModel,
            {"state": DagRun.state, "start_date": DagRun.start_date, "last_run_state": DagRun.state}
        )

helper_b = AliasedDagSort()
deps_b = helper_b.dynamic_depends()