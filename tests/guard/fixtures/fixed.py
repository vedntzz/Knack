# Excerpt from apache/airflow airflow-core/src/airflow/api_fastapi/core_api/routes/public/dags.py
# @ ac13d1d9f9e6 (head of https://github.com/apache/airflow/pull/75025), after the fix.
# Copyright The Apache Software Foundation. Licensed under the Apache License, Version 2.0:
# http://www.apache.org/licenses/LICENSE-2.0
# Imports trimmed, signature shortened, body replaced by `...`; kept lines are verbatim.
from typing import Annotated

from fastapi import Depends

from airflow.api_fastapi.common.parameters import RangeFilter, SortParam, datetime_range_filter_factory
from airflow.models import DagModel
from airflow.models.dagrun import DagRun


def get_dags(
    dag_run_start_date_range: Annotated[
        RangeFilter, Depends(datetime_range_filter_factory("dag_run_start_date", DagRun, "start_date"))
    ],
    order_by: Annotated[
        SortParam,
        Depends(
            SortParam(
                ["dag_id", "dag_display_name", "next_dagrun"],
                DagModel,
                {"last_run_state": DagRun.state, "last_run_start_date": DagRun.start_date},
            ).dynamic_depends()
        ),
    ],
) -> None: ...
