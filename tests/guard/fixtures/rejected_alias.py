# Derived from apache/airflow airflow-core/src/airflow/api_fastapi/core_api/routes/public/dags.py
# @ ac13d1d9f9e6 (head of https://github.com/apache/airflow/pull/75025).
# Copyright The Apache Software Foundation. Licensed under the Apache License, Version 2.0:
# http://www.apache.org/licenses/LICENSE-2.0
# MODIFIED by Knack: two to_replace keys added that re-alias the bare DagRun column names
# onto DagRun.state / DagRun.start_date. This alternative is not Airflow code.
from typing import Annotated

from fastapi import Depends

from airflow.api_fastapi.common.parameters import SortParam
from airflow.models import DagModel
from airflow.models.dagrun import DagRun


def get_dags(
    order_by: Annotated[
        SortParam,
        Depends(
            SortParam(
                ["dag_id", "dag_display_name", "next_dagrun"],
                DagModel,
                {
                    "state": DagRun.state,
                    "start_date": DagRun.start_date,
                    "last_run_state": DagRun.state,
                    "last_run_start_date": DagRun.start_date,
                },
            ).dynamic_depends()
        ),
    ],
) -> None: ...
