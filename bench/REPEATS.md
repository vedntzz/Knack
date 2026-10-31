# Repeats after each decision

For each rule in a registry: every first-parent commit on the clone's default branch after the decision's PR merged. A repeat is a rule match on a line the commit added that the file did not already have (the guard's only-new comparison). Bots are GitHub `[bot]` accounts.

| Repo | Decision | Merged | Commits scanned | Repeat commits | Human | Bot |
|---|---|---|---|---|---|---|
| apache/airflow | #74150 | 2026-10-28 | 99 | 0 | 0 | 0 |
| apache/airflow | #75025 | 2026-10-20 | 432 | 0 | 0 | 0 |
| apache/airflow | #75271 | 2026-10-28 | 105 | 0 | 0 | 0 |
| apache/airflow | #75734 | 2026-10-27 | 175 | 0 | 0 | 0 |
| apache/airflow | #75774 | 2026-10-28 | 96 | 0 | 0 | 0 |
| fastapi/fastapi | #14884 | 2026-02-10 | 1222 | 0 | 0 | 0 |
| fastapi/fastapi | #15139 | 2026-03-23 | 970 | 0 | 0 | 0 |
| fastapi/fastapi | #15515 | 2026-07-28 | 363 | 0 | 0 | 0 |
| fastapi/fastapi | #15937 | 2026-07-28 | 356 | 0 | 0 | 0 |
| fastapi/fastapi | #15967 | 2026-07-24 | 419 | 0 | 0 | 0 |
| fastapi/fastapi | #16049 | 2026-07-24 | 417 | 0 | 0 | 0 |
| fastapi/fastapi | #16062 | 2026-07-27 | 414 | 0 | 0 | 0 |

## apache/airflow #74150: `aget_conn()` and `acreate_agent()` run the unchanged `get_conn()` / `create_agent()` on a single-worker executor of the hook module

Rule `74150.yml`; merged in `49bdd34d92` on 2026-10-28; scanned to `740d8bda33`; 99 commit(s) scanned after it. No repeats.

## apache/airflow #75025: Dag list endpoints do not accept bare state or start_date as sort keys; the latest run is sorted only as last_run_state and last_run_start_date.

Rule `75025.yml`; merged in `b8db2af9cd` on 2026-10-20; scanned to `740d8bda33`; 432 commit(s) scanned after it. No repeats.

## apache/airflow #75271: Type the durable default of the common.compat ResumableJobMixin stand-in as bool | None

Rule `75271.yml`; merged in `7839f4a2da` on 2026-10-28; scanned to `740d8bda33`; 105 commit(s) scanned after it. No repeats.

## apache/airflow #75734: Reuse existing resumable_job.* counters tagged operator="KubernetesPodOperator" with no new metric names

Rule `75734.yml`; merged in `ead86184fb` on 2026-10-27; scanned to `740d8bda33`; 175 commit(s) scanned after it. No repeats.

## apache/airflow #75774: Record start time on first execute() and carry it in next_kwargs through re-defers, deferring each request with the remaining time and raising AirflowSensorTimeout past the deadline

Rule `75774.yml`; merged in `54171ff7cc` on 2026-10-28; scanned to `740d8bda33`; 96 commit(s) scanned after it. No repeats.

## fastapi/fastapi #14884: Simplify reading files in memory, do it sequentially instead of (fake) parallel

Rule `14884.yml`; merged in `25270fcee0` on 2026-02-10; scanned to `79cab5bed2`; 1222 commit(s) scanned after it. No repeats.

## fastapi/fastapi #15139: fix these tests instead, allowing multiple versions of the schema

Rule `15139.yml`; merged in `aeb9f4bb85` on 2026-03-23; scanned to `79cab5bed2`; 970 commit(s) scanned after it. No repeats.

## fastapi/fastapi #15515: Add _split_sse_lines helper that normalizes CRLF and lone CR to LF then splits on LF for data and comment branches

Rule `15515.yml`; merged in `0f3e7bd682` on 2026-07-28; scanned to `79cab5bed2`; 363 commit(s) scanned after it. No repeats.

## fastapi/fastapi #15937: Apply the same `_build_response_args()` path to the SSE and JSONL branches

Rule `15937.yml`; merged in `e92a0dc3ce` on 2026-07-28; scanned to `79cab5bed2`; 356 commit(s) scanned after it. No repeats.

## fastapi/fastapi #15967: Fix links in docs that return 404, point to incorrect content, or redirect, fixing only part of redirects

Rule `15967.yml`; merged in `f3644b33cd` on 2026-07-24; scanned to `79cab5bed2`; 419 commit(s) scanned after it. No repeats.

## fastapi/fastapi #16049: simplify all that code and stop using those attributes, move it out of the class and into helper functions, class is just holding data

Rule `16049.yml`; merged in `0270829500` on 2026-07-24; scanned to `79cab5bed2`; 417 commit(s) scanned after it. No repeats.

## fastapi/fastapi #16062: Update the lru_cache limit for dependencies to account for large apps

Rule `16062.yml`; merged in `65ef53ae6a` on 2026-07-27; scanned to `79cab5bed2`; 414 commit(s) scanned after it. No repeats.
