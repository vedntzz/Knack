# Held-out precision: compiled rules on Airflow v2-10-stable

The rules were repaired against Airflow `main`. This run scans a branch they
were never tuned on, to check they aren't overfit to `main`.

Run: `.venv/bin/python spikes/batch_precision.py --ref v2-10-stable`
(shallow clone into `/tmp/airflow-v2-10-stable`, Python files only).

## Per-rule matches

`.v1` is the rule before precision repair; the bare id is the repaired rule.

| Rule | v1 matches (files) | Repaired matches (files) |
|---|---|---|
| #74150 | 0 (0) | 0 (0) |
| #75025 | 0 (0) | 0 (0) |
| #75271 | 0 (0) | 0 (0) |
| #75734 | 15 (15) | 0 (0) |
| #75774 | 2 (1) | 3 (1) |

All 15 `#75734.v1` hits were at line 1 (the license header), so v1 was
matching whole files. The repaired rule drops all of them.

## The 3 #75774 hits

All in `airflow/providers/microsoft/azure/sensors/msgraph.py`, compared with
the same file at PR #75774's `base_sha` `8b5306690acb58d0584376272dfa2159aecea0dd`
and `head_sha` `44f87164b7ac8729d67fa4823bb2df91dbcb9192`.

| Line | What matched | Compared with PR base | Verdict |
|---|---|---|---|
| 39 | `class MSGraphSensor`: never raises `AirflowSensorTimeout` | Same as base; the PR's head adds the raise | true violation, pre-decision |
| 109 | `execute()`: `self.defer(trigger=MSGraphTrigger(..., timeout=self.timeout))`, no `sensor_started_at` | Same as base `execute()` (base also passes `scopes=self.scopes`); the PR replaces it with `_defer_request`, which carries `sensor_started_at` and defers with the remaining time | true violation, pre-decision |
| 172 | `execute_complete()`: `self.defer(trigger=TimeDeltaTrigger(self.retry_delay))`, no `timeout=` | Older than base: base adds `timeout=timedelta(seconds=self.timeout)` (the sliding timeout the PR rejected). v2-10 has no deadline at all, the other rejected alternative ("the sleep defer now has no deadline at all") | true violation, pre-decision |

## Caveat: pre-decision code

v2-10-stable predates PR #75774. These 3 hits are code from before the
decision, not new violations and not false positives. Count them as neither a
precision loss nor a precision win. They show the rule fires on the forbidden
pattern in held-out code, including an older version of it (line 172) the PR
never touched.

False positives on v2-10-stable across all repaired rules: **0**.
