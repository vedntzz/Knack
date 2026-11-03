# Self-repair, live (KN-97)

Terminology: 'replayed' = recorded edit replay with real hook and model calls; 'self-repair' = model-assisted repair initiated by a person. See README › Meta models and provenance.

One live repair of airflow-75025 on 2026-11-02, in one sandbox (`/var/folders/k9/5rtt8_bd2s5cjgmgzknpl3qc0000gn/T/knack-kn114.itVgOH`: its own HOME, KNACK_HOME and a temp copy of `data/`). The committed registry and `~/.knack` were never touched. Real Spark (`muse-spark-1.3`, api.meta.ai) and Spark Open (`meta-models/muse-spark-open-1026`, inference.baseten.co) made every model call. The output is frozen, unchanged, in [`mockups/fixtures/self_repair/`](../mockups/fixtures/self_repair/) (see its `SOURCES.md`).

Plainly: **the first `knack confirm` was rolled back by the regression gate, and the second passed.** The rollback had nothing to do with this rule. On the gate's live re-read of #75774, Spark did not return that PR's rejected alternative verbatim, so the gate restored the registry and roots and exited 1. The confirm was retried once, with the gate, as the same person. That retry passed. `--no-gate` was never used.

Every edit is replayed through the installed user-level PreToolUse hook, inside the captured Muse Code payload (`tests/hooks/fixtures/edit_event.json`). Only `tool_input`, `cwd` and `session_id` (`self-repair`) are replaced.

## The two cases

- **Must-fail: the `dict(...)` evasion.** `public/dags.py` adds `ADVERTISED_RUN_SORTS = dict(state=DagRun.state, start_date=DagRun.start_date)` and splices it into `SortParam` with `*ADVERTISED_RUN_SORTS` and `**ADVERTISED_RUN_SORTS`. That is the rejected alternative, aliasing `state` and `start_date` onto DagRun. v1 allowed it: receipt `b27a4e1127569e2bcd56de277ef042975f8fe637266812b88d1e402720dc858d`. Recorded as `must-fail-2ccf5ea40fa8` by `knack miss`'s own `case_from_receipt` and `save_case`, without its recompile.
- **Must-pass: `compliant_3.py`.** Spark Open's compliant file from the earlier KN-97 run, written as a new `public/dag_sort_keys.py`. It sorts the latest run only as `last_run_state` and `last_run_start_date`, built with a dict comprehension. v1 denied it: receipt `f679bf658d9f754750c54a518084987983aa0ac46fae79250c6d1f8f185bc78a`, matched `{a: b for a, b in [("last_run_state", DagRun.state), ("last_run_start_date", DagRun.start_date)]} (line 6)`. `knack false-block` recorded it as `must-pass-6633cbc47011`. It is now a permanent case in [`data/registry/cases/airflow-75025/`](../data/registry/cases/airflow-75025/), so every later recompile of airflow-75025 must allow it.

## The rule

- v1: `ecf207d0e1efce2759eb92b2beba21e9576eaf0c5d832ca4acdfca1079a4b0d5` (the committed rule; `tests/fixtures/self_repair_75025/v1.yml`).
- v2: `865e1a983ffe12941abd400da11efbe14e6a7ec97735455b61218abe464b2303` (installed by `knack false-block` and pinned by the second confirm).

**Dropped:** v1's one `dictionary_comprehension` branch (`DagRun\.(state|start_date)|getattr\s*\(\s*DagRun` inside `SortParam` and `DagModel`). It is the only branch that flagged `compliant_3.py`.

**Kept verbatim** (only the YAML formatting changed): v1's other six branches. These are the bare `"state"`/`"start_date"` string in `SortParam(… DagModel …)`, the `"state": DagRun.state` pair, the `"state": "last_run_state"` pair, the string-and-DagRun tuple, `getattr(DagRun, …)` in `SortParam`, and the test-side `last_run` string.

**Added**, from Spark's recompile:

1. `kind: pair` with a `"state"`/`"start_date"` string and `DagRun.(state|start_date)` anywhere below it (`stopBy: end`).
2. `kind: keyword_argument` matching `^(state|start_date)\s*=\s*DagRun\.(state|start_date)`.
3. `kind: tuple` with the same string and DagRun attribute anywhere below it (`stopBy: end`).
4. `pattern: dict($$$, state=DagRun.state, $$$)`.
5. `pattern: dict($$$, start_date=DagRun.start_date, $$$)`.

The evasion is denied by 2, 4 and 5: `Matched: dict(state=DagRun.state, start_date=DagRun.start_date) (line 89), state=DagRun.state (line 89), start_date=DagRun.start_date (line 89)`.

The full diff is `rule/v1_v2.diff`. [`tests/pipeline/test_self_repair_live.py`](../tests/pipeline/test_self_repair_live.py) re-checks all of the above offline against the frozen files: both shas, the root pin, the registry case, the one dropped branch, and the three replays.

## Steps and every gate line, verbatim

| # | Step | Result | Wall |
|---|---|---|---|
| 1 | Hook: evasion on v1 | allow (`b27a4e11…`) | 210.5 ms |
| 2 | Hook: `compliant_3.py` on v1 | deny (`f679bf65…`) | 124.0 ms |
| 3 | Record must-fail from `b27a4e11…` | `must-fail-2ccf5ea40fa8.json` | 104.7 ms |
| 4 | `knack false-block f679bf65…` | installed v2, 2 attempts | 265.6 s |
| 5 | `knack confirm airflow-75025-1 --by "Vedant Srivastava"` | **rolled back**, exit 1 | 30.1 s |
| 5b | Same command, retried once | **passed**, pinned to v2 | 39.6 s |
| 6 | Hook: evasion on v2 | deny (`66a1c247…`) | 200.3 ms |
| 7 | Hook: `compliant_3.py` on v2 | allow (`4797a35d…`) | 162.6 ms |
| 8 | Hook: corrected edit on v2 | allow (`f8936864…`) | 164.7 ms |
| 9 | `knack receipts verify` | 19 receipts, chain intact | 162.7 ms |

Hook times are the replay's round trip (`sh -c`, Python start, the envelope) from `wall.jsonl`. Step times are the driver's wall clock. The corrected edit adds one comment line inside the `SortParam` arguments and keeps `last_run_state` and `last_run_start_date`.

Step 4, `knack false-block`:

```
recorded must-pass case airflow-core/src/airflow/api_fastapi/core_api/routes/public/dag_sort_keys.py [6633cbc47011] for airflow-75025 -> /var/folders/k9/5rtt8_bd2s5cjgmgzknpl3qc0000gn/T/knack-kn114.itVgOH/data/registry/cases/airflow-75025/must-pass-6633cbc47011.json
airflow-75025 fails: guard edit airflow-core/src/airflow/api_fastapi/core_api/routes/public/dags.py [2ccf5ea40fa8] adds no new match; guard allow airflow-core/src/airflow/api_fastapi/core_api/routes/public/dag_sort_keys.py [6633cbc47011] adds a new match; recompiling with muse-spark-1.3
PASS cases: every must-fail edit denied, every must-pass edit allowed
PASS proof: base, guard-allow, guard-edit, head, rename-base, rename-head, variant-compliant, variant-violation hold; 0 FP on the default branch and release 3.3.2
PASS no coverage loss: every input v1 denied is still denied
PASS held-out same: 2/3 violations caught (old rule 2), 3/3 compliant allowed
PASS held-out cross: 3/3 violations caught (old rule 3), 3/3 compliant allowed
PASS fresh cross-model: 3/3 violations caught (old rule 3), 3/3 compliant allowed (/var/folders/k9/5rtt8_bd2s5cjgmgzknpl3qc0000gn/T/knack-kn114.itVgOH/work/75025/fresh-20261102T200131Z-33aea6)
candidate rule: /var/folders/k9/5rtt8_bd2s5cjgmgzknpl3qc0000gn/T/knack-kn114.itVgOH/work/75025/candidate-20261102T200146Z-c9845e.yml
installed airflow-75025 -> /var/folders/k9/5rtt8_bd2s5cjgmgzknpl3qc0000gn/T/knack-kn114.itVgOH/data/registry/../rules/airflow/75025.yml (2 attempt(s))
```

The output reports 2 attempts but does not say why the first attempt's candidate was rejected. Only the passing candidate was kept in `work/75025/`.

Step 5, the first confirm (rolled back):

```
gate: re-extracting 2 PR(s) with Confirmed roots
airflow-75025-1: Confirmed -> Confirmed, pinned to rule 865e1a983ffe rolled back
  airflow-75774-1 (#75774) no longer extracted: rejected alternative 'sliding re-defer timeout that put timeout=self.timeout on the sleep re-defer only' quoting 'put `timeout=self.timeout` on the sleep re-defer only'
```

After the rollback the root stayed pinned to v1 (`ecf207d0…`), with v2 still on disk. No correction line was kept.

Step 5b, the second confirm (passed):

```
gate: re-extracting 2 PR(s) with Confirmed roots
airflow-75025-1: Confirmed -> Confirmed, pinned to rule 865e1a983ffe
```

Root airflow-75025-1's only change is `rule_sha`, from `ecf207d0…` to `865e1a98…` (`rule/root_before.json` → `rule/root_after.json`).

## Every model call

From `models.jsonl`, written by `traced.py`, which wraps `SparkApi.ask` and `SparkOpenApi.ask`.

| Step | Client | Model | Host | Trace id | Wall |
|---|---|---|---|---|---|
| 4 false-block | SparkApi (compile) | muse-spark-1.3 | api.meta.ai | `resp_6ae8ebe6eca39f36691049d2` | 48.8 s |
| 4 false-block | SparkApi (compile) | muse-spark-1.3 | api.meta.ai | `resp_6ae8ec1876be1eea517a4495` | 49.3 s |
| 4 false-block | SparkOpenApi (fresh cross-model cases) | meta-models/muse-spark-open-1026 | inference.baseten.co | `chatcmpl-56e5cf7032a34f14bfa89e8b3c3c51be` | 14.2 s |
| 5 confirm (rolled back) | SparkApi (re-extract) | muse-spark-1.3 | api.meta.ai | `resp_6ae8ec3314cd80581f104a91` | 6.3 s |
| 5 confirm (rolled back) | SparkApi (re-extract) | muse-spark-1.3 | api.meta.ai | `resp_6ae8ec480f0ee6be96264c35` | 19.4 s |
| 5b confirm (passed) | SparkApi (re-extract) | muse-spark-1.3 | api.meta.ai | `resp_6ae8fc0e5f3fa4b4b49e482c` | 4.9 s |
| 5b confirm (passed) | SparkApi (re-extract) | muse-spark-1.3 | api.meta.ai | `resp_6ae8fc2e68ba94093979455c` | 30.8 s |

Each confirm re-extracts #75025 and #75774, one call per PR. The log does not record which call read which PR. The held-out and per-PR variant gates in step 4 read cached Spark Open sets (the earlier KN-97 run's variants, seeded into `work/75025/variants`) and made no calls.

## What ran where

Steps 1–5 ran from the knack-gate worktree at 76214c6. Its `knack/roots/gate.py` was last modified at 15:28 local (20:28Z), after step 5 ended at about 20:02Z. Steps 5b–9 ran from this repo at e81e98d, with the hook command changed to this repo's venv. `knack/` and `data/` are identical between 76214c6 and e81e98d.

## What this does not show

- It is not unattended. A driver recorded the must-fail case, and a person ran `knack false-block` and `knack confirm`. The self-check did not run.
- The rollback came from Spark's nondeterministic re-read of an unrelated PR (#75774). One retry passed. A third read could fail the same way. That is the gate doing its job, not a fix to it.
- Held-out same caught 2/3 violations, before and after: the repair did not lose that one miss, and it did not catch it either.
