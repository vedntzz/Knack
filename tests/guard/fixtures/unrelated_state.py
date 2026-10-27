# Excerpt from apache/airflow airflow-core/src/airflow/api_fastapi/core_api/routes/public/dag_run.py
# @ ac13d1d9f9e6 (head of https://github.com/apache/airflow/pull/75025).
# Copyright The Apache Software Foundation. Licensed under the Apache License, Version 2.0:
# http://www.apache.org/licenses/LICENSE-2.0
# Imports trimmed, signature shortened, body replaced by `...`; kept lines are verbatim.
# DagRun sorts by its own "state"/"start_date" columns, so nothing is aliased.
from typing import Annotated

from fastapi import Depends

from airflow.api_fastapi.common.parameters import SortParam
from airflow.models.dagrun import DagRun


def get_dag_runs(
    dag_id: str,
    order_by: Annotated[
        SortParam,
        Depends(
            SortParam(
                [
                    "id",
                    "state",
                    "dag_id",
                    "run_id",
                    "logical_date",
                    "partition_date",
                    "run_after",
                    "start_date",
                    "end_date",
                    "updated_at",
                    "conf",
                    "duration",
                ],
                DagRun,
                {"dag_run_id": "run_id"},
            ).dynamic_depends(default="id")
        ),
    ],
) -> None: ...


def get_list_dag_runs_batch(body) -> None:
    order_by = SortParam(
        [
            "id",
            "state",
            "dag_id",
            "run_after",
            "logical_date",
            "run_id",
            "start_date",
            "end_date",
            "updated_at",
            "conf",
        ],
        DagRun,
        {"dag_run_id": "run_id"},
    ).set_value([body.order_by] if body.order_by else None)
