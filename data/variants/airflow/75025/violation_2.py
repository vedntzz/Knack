from airflow.api_fastapi.common.parameters import SortParam
from airflow.models.dag import DagModel
from airflow.models.dagrun import DagRun

class LarkspurQueryShaper:
    def shape_ordering(self):
        permitted = ["dag_id", "next_dagrun", "state", "start_date"]
        aliases = {"state": DagRun.state, "start_date": DagRun.start_date}
        aliases["last_run_state"] = DagRun.state
        return SortParam(permitted, DagModel, aliases).dynamic_depends()