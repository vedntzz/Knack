from airflow.api_fastapi.common.parameters import SortParam
from airflow.models import DagModel
from airflow.models.dagrun import DagRun

class CompliantUiSort:
    def make_sorter(self):
        fields = ["dag_id", "dag_display_name", "next_dagrun"]
        aliases = {"last_run_state": DagRun.state, "last_run_start_date": DagRun.start_date, "last_run_run_after": DagRun.run_after}
        sorter = SortParam(fields, DagModel, aliases)
        return sorter.dynamic_depends()

obj_ok = CompliantUiSort()
deps_ok = obj_ok.make_sorter()