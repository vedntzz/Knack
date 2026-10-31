from airflow.api_fastapi.common.parameters import SortParam
from airflow.models import DagModel
from airflow.models.dagrun import DagRun

def _willow_replacements():
    return {"last_run_state": DagRun.state, "last_run_start_date": DagRun.start_date, "last_run_run_after": DagRun.run_after}

def willow_sort_check():
    base_willow = ("dag_id", "dag_display_name", "next_dagrun")
    allowed_willow = list(c for c in base_willow)
    sorter_willow = SortParam(allowed_willow, DagModel, _willow_replacements())
    assert "last_run_state" in _willow_replacements()
    return sorter_willow.dynamic_depends()
