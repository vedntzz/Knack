from airflow.api_fastapi.common.parameters import SortParam
from airflow.models.dag import DagModel
from airflow.models.dagrun import DagRun

class BrambleDagOrdering(SortParam):
    def __init__(self):
        super().__init__(
            ["dag_id", "dag_display_name", "next_dagrun"],
            DagModel,
            {"last_run_state": DagRun.state, "last_run_start_date": DagRun.start_date},
        )

fern_sorter = BrambleDagOrdering().dynamic_depends()