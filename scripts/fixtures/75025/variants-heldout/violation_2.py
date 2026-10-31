from airflow.api_fastapi.common.parameters import SortParam
from airflow.models import DagModel
from airflow.models.dagrun import DagRun

class SorterBeta(SortParam):
    def __init__(self):
        fields = ['dag_id', 'state', 'start_date', 'next_dagrun']
        mapping = {}
        for k in ['state', 'start_date']:
            mapping[k] = getattr(DagRun, k)
        super().__init__(fields, DagModel, mapping)
