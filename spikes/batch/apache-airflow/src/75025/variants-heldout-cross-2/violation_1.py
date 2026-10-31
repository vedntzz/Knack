from airflow.api_fastapi.common.parameters import SortParam
from airflow.models import DagModel
from airflow.models.dagrun import DagRun

def make_sorter_alpha():
    allowed_fields = ['dag_id', 'dag_display_name', 'next_dagrun', 'state', 'start_date']
    alias_map = {'state': DagRun.state, 'start_date': DagRun.start_date}
    return SortParam(allowed_fields, DagModel, alias_map)
