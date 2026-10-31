from airflow.api_fastapi.common.parameters import SortParam
from airflow.models import DagModel
from airflow.models.dagrun import DagRun

def _quokka_pair_table():
    return [("state", DagRun.state), ("start_date", DagRun.start_date)]

def quokka_sort_param():
    bare_quokka = [k for k, _ in _quokka_pair_table()]
    allowed_quokka = ["dag_id", "dag_display_name", "next_dagrun"] + bare_quokka
    alias_quokka = {k: v for k, v in _quokka_pair_table()}
    return SortParam(allowed_quokka, DagModel, alias_quokka).dynamic_depends()
