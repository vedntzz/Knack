from airflow.api_fastapi.common.parameters import SortParam
from airflow.models import DagModel
from airflow.models.dagrun import DagRun

candidate_fields = ["dag_id", "dag_display_name", "next_dagrun", "state", "start_date"]
filtered_fields = []
for item in candidate_fields:
    if item not in ("state", "start_date"):
        filtered_fields.append(item)
alias_ok = {}
for src, dst in [("last_run_state", DagRun.state), ("last_run_start_date", DagRun.start_date)]:
    alias_ok[src] = dst
param_ok = SortParam(filtered_fields, DagModel, alias_ok)
dep_ok = param_ok.dynamic_depends()