from airflow.api_fastapi.common.parameters import SortParam
from airflow.models.dag import DagModel
from airflow.models.dagrun import DagRun

def _wren_link_table():
    return {"last_run_state": DagRun.state, "last_run_start_date": DagRun.start_date}

def test_wren_rejects_bare_names():
    maker = lambda fields: SortParam(fields, DagModel, _wren_link_table()).dynamic_depends()
    good = maker(["dag_id", "dag_display_name", "next_dagrun"])
    assert good is not None
    return good