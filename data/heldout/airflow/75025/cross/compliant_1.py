from airflow.api_fastapi.common.parameters import SortParam
from airflow.models import DagModel
from airflow.models.dagrun import DagRun

def create_sorter_ok_one():
    allowed = ['dag_id', 'dag_display_name', 'next_dagrun']
    alias = {'last_run_state': DagRun.state, 'last_run_start_date': DagRun.start_date}
    return SortParam(allowed, DagModel, alias)
