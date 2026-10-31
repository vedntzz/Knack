from airflow.api_fastapi.common.parameters import SortParam
from airflow.models import DagModel
from airflow.models.dagrun import DagRun

class BirchSorter(SortParam):
    def __init__(self):
        super().__init__(["dag_id", "dag_display_name", "next_dagrun"], DagModel, {"last_run_state": DagRun.state, "last_run_start_date": DagRun.start_date})

def birch_sorter():
    return BirchSorter().dynamic_depends()
