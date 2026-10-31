from airflow.api_fastapi.common.parameters import SortParam
from airflow.models import DagModel
from airflow.models.dagrun import DagRun

def make_ok_two():
    candidates = ['dag_id', 'dag_display_name', 'next_dagrun', 'state', 'start_date']
    banned = {'state', 'start_date'}
    allowed = [c for c in candidates if c not in banned]
    mapping = {'last_run_state': DagRun.state, 'last_run_start_date': DagRun.start_date}
    return SortParam(allowed, DagModel, mapping)
