from airflow.api_fastapi.common.parameters import SortParam
from airflow.models.dag import DagModel
from airflow.models.dagrun import DagRun

def zeta_build_ordering():
    alias_table = {"last_run_state": DagRun.state}
    for naked, column in [("state", DagRun.state), ("start_date", DagRun.start_date)]:
        alias_table[naked] = column
    permitted = ["dag_id", "dag_display_name", "next_dagrun", "state", "start_date"]
    return SortParam(permitted, DagModel, alias_table).dynamic_depends()