# Self-repair, live (KN-97): `fixtures/self_repair/`

Frozen unchanged from one live self-repair run of airflow-75025 on 2026-11-02, in the sandbox `/var/folders/k9/5rtt8_bd2s5cjgmgzknpl3qc0000gn/T/knack-kn114.itVgOH` (its own HOME, KNACK_HOME and a temp copy of `data/`). Steps 1–5 ran from 19:57:19Z to about 20:02Z. Step 5, the first `knack confirm`, was rolled back by the regression gate. Steps 5b–9 ran in the same sandbox from 21:09:27Z to 21:10:07Z. Real Spark (`muse-spark-1.3`, api.meta.ai) and Spark Open (`meta-models/muse-spark-open-1026`, inference.baseten.co) made every model call. Nothing was edited by hand. The write-up is [`spikes/self_repair_live.md`](../../../spikes/self_repair_live.md).

Absolute sandbox paths are kept as they ran. `file` is part of each receipt's hash, so a rewrite would break `knack receipts verify`.

| File | What | Source |
|---|---|---|
| `rule/v1.yml` | Rule before the repair, sha `ecf207d0…` (equals `tests/fixtures/self_repair_75025/v1.yml`) | Sandbox `data/rules/airflow/75025.yml` before step 4 |
| `rule/v2.yml` | Rule `knack false-block` installed, sha `865e1a98…` | Sandbox `data/rules/airflow/75025.yml` after step 4 |
| `rule/candidate-20261102T200146Z-c9845e.yml` | The candidate that passed every gate (byte-equal to `v2.yml`) | Sandbox `work/75025/` |
| `rule/v1_v2.diff` | `diff -u v1.yml v2.yml` | Driver, step 4 |
| `rule/root_before.json`, `rule/root_after.json` | Root airflow-75025-1 pinned to v1, then to v2 by the second confirm | Sandbox `data/roots/airflow/75025.json` |
| `cases/must-fail-2ccf5ea40fa8.json` | The `dict(...)` evasion v1 allowed (receipt `b27a4e11…`) | Step 3, `knack miss`'s own `case_from_receipt` and `save_case` |
| `cases/must-pass-6633cbc47011.json` | `compliant_3.py`, which v1 denied (receipt `f679bf65…`); also committed as `data/registry/cases/airflow-75025/must-pass-6633cbc47011.json` | Step 4, `knack false-block` |
| `edits/miss.after.py`, `edits/corrected.after.py` | The evasion and the corrected `public/dags.py` | Driver `steps.py install` |
| `edits/*.event.json` | The PreToolUse payload each hook replay sent | Driver `steps.py hook` |
| `receipts.jsonl` | 19 hash-chained receipts from both halves of the run | Sandbox `~/.knack/verdicts.jsonl` |
| `traces/receipt_edits/*.json` | Before and after snapshots the receipts point to | Sandbox `~/.knack/edits/` |
| `corrections.jsonl` | The one correction that stayed: the second confirm. The rolled-back confirm left no line | Sandbox `~/.knack/corrections.jsonl` |
| `models.jsonl` | Every live model call: step, client, model, host, trace id, wall seconds, prompt head | `traced.py` wrapper |
| `wall.jsonl` | Hook round trip and decision per replay | Driver `steps.py hook` |
| `traces/steps/*.txt` | Each step's command, output and exit, verbatim | Driver logs |
| `driver/steps_1_4/` | `run.sh`, `steps.py`, `traced.py` and `run.out` for steps 1–5, run from the knack-gate worktree at 76214c6 | KN-114 session scratchpad |
| `driver/steps_5_9/` | `resume.sh`, the same `steps.py` and `traced.py`, and `resume.out` for steps 5b–9, run from this repo at e81e98d | KN-97 session scratchpad |
