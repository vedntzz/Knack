from airflow.api_fastapi.common.parameters import SortParam
from airflow.models import DagModel
from airflow.models.dagrun import DagRun

base_fields = ["dag_id", "dag_display_name", "next_dagrun"]
extra_aliases = ["state", "start_date"]
all_fields = [f for f in base_fields + extra_aliases]
mapping_c = {k: getattr(DagRun, k) for k in extra_aliases}
mapping_c.update({"last_run_state": DagRun.state, "last_run_start_date": DagRun.start_date})
sort_param_c = SortParam(all_fields, DagModel, mapping_c)
dep_c = sort_param_c.dynamic_depends()