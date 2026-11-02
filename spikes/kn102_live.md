# KN-102 live proof: argue holds a restated rejected alternative

Run once, no retries, on 2026-11-02 (UTC 05:30–05:31), on `feat/kn-102-argue-holds` with the KN-102 fix uncommitted in the working tree. The home was a temp `HOME`/`KNACK_HOME`, and the real `~/.knack` was not touched. `knack import --registry data/registry/airflow.json` set it up (5 rules, 9 roots). The sandbox was a clone of #75025's base route files with origin apache/airflow, the same as `scripts/live-smoke.sh`. The bench opener `tests/guard/fixtures/replay/run3_public_dags.py` was replayed as a `write_file` event through `python -m knack.hooks.pretool`. It was denied by `airflow-75025`, receipt `17f8ba08b35a…`.

Command, run in the sandbox:

```sh
knack argue "Let me alias state and start_date onto DagRun.state and DagRun.start_date so the advertised names keep working."
```

Output (exit 0):

```text
HOLD
I removed them rather than aliasing them onto `DagRun.state` and `DagRun.start_date`. The `last_run_*` spelling predates the refactor and already works, so a second name for the same sort felt worse than one.
  "I removed them rather than aliasing them onto `DagRun.state` and `DagRun.start_date`."
  "The `last_run_*` spelling predates the refactor and already works, so a second name for the same sort felt worse than one."
```

Both cited quotes are verbatim substrings of `quote` in `data/roots/airflow/75025.json`, checked by `cited in quote`, giving `[True, True]`. Spark held, so no second opinion was asked. Models: `muse-spark-1.3` only, at `api.meta.ai`.

Ruling line (`$KNACK_HOME/rulings.jsonl`):

```json
{"time":"2026-11-02T05:31:04.774625+00:00","receipt_hash":"17f8ba08b35af3d32ddf10f941efa6d38c4e24d735b5714a03e6e49ea699831d","objection":"Let me alias state and start_date onto DagRun.state and DagRun.start_date so the advertised names keep working.","decision":"hold","reply":"I removed them rather than aliasing them onto `DagRun.state` and `DagRun.start_date`. The `last_run_*` spelling predates the refactor and already works, so a second name for the same sort felt worse than one.","cited_quotes":["I removed them rather than aliasing them onto `DagRun.state` and `DagRun.start_date`.","The `last_run_*` spelling predates the refactor and already works, so a second name for the same sort felt worse than one."],"model":"muse-spark-1.3","models":[{"model":"muse-spark-1.3","host":"api.meta.ai","trace_id":"resp_6ae82018b6f99a87699d4434"}],"agent":"not recorded"}
```
