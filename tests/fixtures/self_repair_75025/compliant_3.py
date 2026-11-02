from airflow.api_fastapi.common.parameters import SortParam
from airflow.models import DagModel
from airflow.models.dagrun import DagRun

allowed_keys = [k for k in ["dag_id", "dag_display_name"]]
extra = {a: b for a, b in [("last_run_state", DagRun.state), ("last_run_start_date", DagRun.start_date)]}
sorter_cc = SortParam(allowed_keys, DagModel, extra)
dep_fn = sorter_cc.dynamic_depends()
