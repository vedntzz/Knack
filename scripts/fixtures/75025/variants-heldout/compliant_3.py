from airflow.api_fastapi.common.parameters import SortParam
from airflow.models import DagModel
from airflow.models.dagrun import DagRun

class SorterOkThree:
    def get_param(self):
        allowed = []
        for f in ['dag_id', 'dag_display_name', 'next_dagrun']:
            allowed.append(f)
        aliases = {'last_run_state': DagRun.state}
        aliases['last_run_start_date'] = DagRun.start_date
        return SortParam(allowed, DagModel, aliases)
