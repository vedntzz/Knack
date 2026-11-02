# KN-101 live proof: FAILED (no rule installed)

One run, no retries, on 2026-11-02, on branch `feat/kn-101-watch-fixes` with KN-101, KN-103, KN-104a and KN-104b applied (uncommitted). Real GitHub, Spark (`MODEL_API_KEY`) and Spark Open (`BASETEN_API_KEY`). Temp `HOME`/`KNACK_HOME`; the real `~/.knack` was not touched. `$W` is the temp dir.

**Result: the self-improving loop was not proven.** Spark Open wrote the training variants and the held-out set. Spark's rule, after 5 compile attempts, was then discarded at held-out: it flagged one of Spark Open's 3 compliant files (3/3 violations caught, 2/3 compliant allowed). So there is no new rule file and no registry diff to show.

## Fixture

- Registry: a copy of the committed `data/`, set back to how it was before #75025 merged. The `../rules/airflow/75025.yml` entry was removed from `$W/data/registry/airflow.json`, and `data/rules/airflow/75025.yml` and `data/roots/airflow/75025.json` were deleted. That leaves 4 rules.
- Repo: `$W/airflow`, origin `https://github.com/apache/airflow.git`, holding #75025's base route files from `scripts/fixtures/75025/base`. Branch `pr-75025` holds the head files, committed as `Live proof merge (#75025)`.
- Script: `live.sh`, kept in the session scratchpad. The exact commands are below.

## Commands and output (verbatim, temp paths shortened to `$W`)

```text
$ knack watch --registry $W/data/registry/airflow.json --muse-settings $W/muse.json
knack watch apache/airflow
  post-merge hook: $W/airflow/.git/hooks/post-merge
  Muse Code PostToolBatch hook: added to $W/muse.json
  watching merges after e96185f
  self-check: Spark Open judges each merge when BASETEN_API_KEY is set
exit 0
```

```text
$ git merge --ff-only pr-75025
Updating e96185f..cf8705a
Fast-forward
 airflow-core/src/airflow/api_fastapi/core_api/routes/public/dags.py | 2 +-
 airflow-core/src/airflow/api_fastapi/core_api/routes/ui/dags.py     | 2 +-
 2 files changed, 2 insertions(+), 2 deletions(-)
knack watch apache/airflow: 1 merged PR: #75025
[1/5] select   1 PRs read, 1 kept
[2/5] extract  reading 1 PRs
  #75025: 1 decision, 1 rejected alternative
  1 decisions found, 1 rejected alternatives (1 verbatim), 0 failed
[3/5] roots    1 Inferred roots written (0 Confirmed, 0 Unknown kept)
[4/5] compile  1 PRs with a verbatim rejected alternative
  adversary: meta-models/muse-spark-open-1026 writes variants, muse-spark-1.3 compiles
  #75025 old release: 3.3.2 (last release before merge 2026-10-19)
  #75025 discarded after 5 attempts: held-out: 2/3 compliant allowed (every held-out compliant file must be allowed)
  #75025 held-out by meta-models/muse-spark-open-1026: 3/3 violations caught, 2/3 compliant allowed (fail)
[5/5] install  0 rules proven, 1 discarded, 4 in registry -> $W/data/registry/airflow.json
self-check airflow-75774 airflow-core/src/airflow/api_fastapi/core_api/routes/public/dags.py (the change takes the rejected path): muse-spark-1.3 no, meta-models/muse-spark-open-1026 no; logged only
self-check airflow-75774 airflow-core/src/airflow/api_fastapi/core_api/routes/ui/dags.py (the change takes the rejected path): muse-spark-1.3 no, meta-models/muse-spark-open-1026 no; logged only
self-check airflow-75774 airflow-core/tests/unit/api_fastapi/core_api/routes/public/test_dags.py (the change takes the rejected path): muse-spark-1.3 no, meta-models/muse-spark-open-1026 no; logged only
self-check airflow-75774 airflow-core/tests/unit/api_fastapi/core_api/routes/ui/test_dags.py (the change takes the rejected path): muse-spark-1.3 no, meta-models/muse-spark-open-1026 no; logged only
exit 0
```

## New rule file

None. `[5/5] install  0 rules proven, 1 discarded, 4 in registry`. `$W/data/registry/rules/` is empty.

## Registry diff

None: `diff airflow.before.json data/registry/airflow.json` prints nothing. KN-101 behaved as specified: install targeted `$W/data/registry/airflow.json`, the log names that file, and no sibling `registry.json` was created. The Inferred root `airflow-75025-1` was written to the registry's `roots_dir` (`$W/data/roots/airflow/`).

## Traces: Spark and Spark Open

`$W/data/registry/work/75025/writers.json`:

```json
{
  "compiler": "muse-spark-1.3",
  "variants": "meta-models/muse-spark-open-1026",
  "heldout": "meta-models/muse-spark-open-1026",
  "adversary": "meta-models/muse-spark-open-1026"
}
```

- `work/75025/variants-heldout/authors.json`: all 6 files (3 violations, 3 compliant) are `meta-models/muse-spark-open-1026`.
- `work/75025/readings.json`: `muse-spark-1.3`, the extractor; no `--corroborate`.
- Root `airflow-75025-1`: Inferred, `"models": ["muse-spark-1.3"]`.
- `self_checks.jsonl`: 4 checks on `airflow-75774`, each answered by `muse-spark-1.3` and `meta-models/muse-spark-open-1026`, all "no, no; logged only".

## Not done

Per the ticket, the failure is recorded and the run was not repeated. The audit's live run (KN-99) installed #75025 on attempt 3, but against held-out variants Spark wrote itself. This run used Spark Open's held-out set and failed its precision bar. Nothing crashed. Whether the flagged compliant file is a real false positive or a bad variant has not been checked.
