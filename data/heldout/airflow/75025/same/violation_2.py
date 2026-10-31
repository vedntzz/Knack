from airflow.api_fastapi.common.parameters import SortParam
from airflow.models import DagModel
from airflow.models.dagrun import DagRun

class HarborSortBuilder:
    def make_harbor_sorter(self):
        picks_harbor = []
        for col in ["dag_id", "next_dagrun", "state", "start_date"]:
            picks_harbor.append(col)
        map_harbor = {}
        map_harbor["state"] = DagRun.state
        map_harbor["start_date"] = DagRun.start_date
        return SortParam(picks_harbor, DagModel, map_harbor).dynamic_depends()
