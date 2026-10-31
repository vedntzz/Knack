from airflow.api_fastapi.common.parameters import SortParam
from airflow.models.dag import DagModel
from airflow.models.dagrun import DagRun

pairs = [("state", DagRun.state), ("start_date", DagRun.start_date)]
alias_map = {k: v for k, v in pairs}
alias_map["last_run_start_date"] = DagRun.start_date
chosen = [x for x in ["dag_id", "dag_display_name", "state", "start_date", "next_dagrun"]]
quill_sorter = SortParam(chosen, DagModel, alias_map).dynamic_depends()