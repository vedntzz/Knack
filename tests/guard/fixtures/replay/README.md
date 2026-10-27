# Replay fixtures

`run_neutral_3.diff` is a real agent edit captured Oct 25, 2026 (pre-event research).

`root_75025.json` comes from apache/airflow PR #75025. In the PR description the
author offered aliasing `state` / `start_date` onto `DagRun.state` / `DagRun.start_date`
as an option ("Happy to alias instead if you would rather keep the advertised names
working."). The approved merge by bbovenzi, without aliasing, is what settled it.
