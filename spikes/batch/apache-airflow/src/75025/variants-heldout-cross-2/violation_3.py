from airflow.api_fastapi.common.parameters import SortParam
from airflow.models import DagModel
from airflow.models.dagrun import DagRun

def build_gamma():
    base = ['dag_id', 'dag_display_name']
    extra = ['state', 'start_date']
    allowed = base + extra
    aliases = {name: getattr(DagRun, name) for name in extra}
    param = SortParam(allowed, DagModel, aliases)
    return param.dynamic_depends()
