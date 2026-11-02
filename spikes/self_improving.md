# Self-improving proof: merged PR → proven rule, installed by `knack watch`, no human step

Branch `spike/self-improving-proof`, 2026-11-02. Nothing under `knack/` was edited.

## 1. Diagnosis of KN-101's held-out failure (no model calls)

KN-101 (`spikes/kn101_live.md`) discarded #75025's rule at Spark Open held-out with `3/3 violations caught, 2/3 compliant allowed`. The saved work folder is the KN-101 session's `live.JcNEGS/data/registry/work/75025/` (identified by its `writers.json`, which matches the one quoted in kn101_live.md).

### What can and cannot be recovered

- The discarded candidate rule is **not saved**. On discard, `[4/5] compile` keeps only the score (`knack/pipeline/heldout.py` `HeldOut`: counts, no file names). `work/75025/` holds base, head, renames, `variants/`, `variants-heldout/`, `readings.json` and `writers.json`. It has no rule YAML and no per-file held-out rows.
- So **which** compliant file was flagged can't be read from disk. Recovering it would need a model call to recompile, which this step forbids.

### The held-out compliant files (Spark Open, verbatim)

`variants-heldout/authors.json`: all 6 files `meta-models/muse-spark-open-1026`.

`compliant_1.py`
```python
from airflow.api_fastapi.common.parameters import SortParam
from airflow.models import DagModel
from airflow.models.dagrun import DagRun

def helper_mapping():
    return {'last_run_state': DagRun.state, 'last_run_start_date': DagRun.start_date}

def compliant_factory():
    allowed = ['dag_id', 'dag_display_name', 'next_dagrun']
    return SortParam(allowed, DagModel, helper_mapping())

s = compliant_factory()
_ = s.dynamic_depends()
```

`compliant_2.py`
```python
from airflow.api_fastapi.common.parameters import SortParam
from airflow.models import DagModel
from airflow.models.dagrun import DagRun

class BravoProvider:
    def get_sorter(self):
        base = ['dag_id', 'dag_display_name', 'next_dagrun']
        allowed = [x for x in base if x not in ('state', 'start_date')]
        mapping = {'last_run_state': DagRun.state, 'last_run_start_date': DagRun.start_date}
        return SortParam(allowed, DagModel, mapping)

provider = BravoProvider()
sorter = provider.get_sorter()
```

`compliant_3.py`
```python
from airflow.api_fastapi.common.parameters import SortParam
from airflow.models import DagModel
from airflow.models.dagrun import DagRun

candidate = ['dag_id', 'dag_display_name', 'next_dagrun', 'state', 'start_date']
filtered = []
idx = 0
while idx < len(candidate):
    if candidate[idx] not in ('state', 'start_date'):
        filtered.append(candidate[idx])
    idx += 1
mapping = {'last_run_state': DagRun.state, 'last_run_start_date': DagRun.start_date}
sp = SortParam(filtered, DagModel, mapping)
_ = sp
```

### Checks (plain code)

| Check | Result |
|---|---|
| All 6 held-out files parse (`ast.parse`) | yes, 6/6 |
| Any compliant file maps `state`/`start_date` onto `DagRun.*` (the rejected alias) | no. Every mapping key is `last_run_state` / `last_run_start_date` |
| Any compliant file passes `state`/`start_date` to `SortParam` as a sort key | no. compliant_2 and compliant_3 filter them **out** before `SortParam` |
| Committed rule `data/rules/airflow/75025.yml` on this exact held-out set (`.venv/bin/ast-grep 0.51.0 scan`) | 3/3 violations caught (10 matches, all in violation files), **3/3 compliant allowed** |
| Bare `'state'`/`'start_date'` literals in Spark Open's **training** compliant files (`variants/compliant_*.py`) | none |

Reconstruction (labelled as such, not the real candidate): a probe rule "a bare `'state'`/`'start_date'` string inside any `list`" scores **3/3 caught, 2/3 compliant allowed** on the held-out set, which is the exact KN-101 score. It flags `compliant_3.py` lines 5 and 9. On the training set it flags only the 3 violations, so it passes training cleanly. A second probe ("a bare string under any ancestor mentioning `SortParam`") flags compliant_2 and compliant_3, giving 1/3 allowed, so that is not the shape. `spikes/rule_quality.md` shows a past attempt, KN-35 `attempt_6.yml`, that also failed only on a compliant_3 written to the same pattern.

### Verdict: real false positive (rule too broad), not a bad test case

The compliant files are valid Python and none contains the rejected pattern. compliant_2/3 name `'state'` and `'start_date'` only to exclude them, which is the decision followed correctly. The bar is reachable: the committed rule allows 3/3 on this set. So Spark's candidate was too broad. It most likely keyed on the bare string literal, not on the literal being a sort key or an alias key.

How it got through: the training compliant set has no "near-miss" file that mentions the rejected names without using them. A literal-matching rule therefore loses nothing in training, and the compiler never sees the counterexample until held-out, which by design it never gets to see.

### Fixes (described, not made)

1. **Observability (small, recommended first):** on discard, write the last candidate to `work/<pr>/discarded.yml` and per-file held-out rows (`side`, `file`, `flagged`, match lines) to `work/<pr>/heldout.json`. Also name the flagged file in the `held-out by …` log line. This diagnosis could then have named the file instead of reconstructing it. `HeldOut` already has the `SideRow`s in `_counted`; they're just dropped.
2. **Training-set coverage:** require one of the 3 training compliant variants to be a near-miss that mentions the rejected identifiers or literals without taking the rejected path. That would put this class of false positive in front of the compiler before held-out. This is a prompt change to the variant writer and needs its own ticket and bench, not a spike.

Neither is a crash or a verdict-path bug. The held-out gate did its job: it kept a rule that would have blocked compliant code.

## 2. Picking the PR

Source: `.venv/bin/python -m knack.reproduce heldout`, which scores every installed rule against the committed same-model and Spark Open (`cross`) held-out sets in `data/heldout/`. Every `cross/authors.json` there is `meta-models/muse-spark-open-1026`.

```text
airflow #74150 same-model 0/3 caught, 3/3 allowed: fail; cross-model 0/3 caught, 3/3 allowed: fail
airflow #75025 same-model 2/3 caught, 3/3 allowed: pass; cross-model 3/3 caught, 3/3 allowed: pass
airflow #75271 same-model 3/3 caught, 3/3 allowed: pass; cross-model 3/3 caught, 3/3 allowed: pass
airflow #75734 same-model 0/3 caught, 3/3 allowed: fail; cross-model 0/3 caught, 3/3 allowed: fail
airflow #75774 same-model 2/3 caught, 3/3 allowed: pass; cross-model 3/3 caught, 3/3 allowed: pass
fastapi #14884 same-model 2/3 caught, 3/3 allowed: pass; cross-model 3/3 caught, 3/3 allowed: pass
fastapi #15139 same-model 1/3 caught, 3/3 allowed: fail; cross-model 2/3 caught, 3/3 allowed: pass
fastapi #15515 same-model 3/3 caught, 3/3 allowed: pass; cross-model 2/3 caught, 3/3 allowed: pass
fastapi #15937 same-model 3/3 caught, 3/3 allowed: pass; cross-model 1/3 caught, 3/3 allowed: fail
fastapi #15967 same-model 1/3 caught, 1/3 allowed: fail; cross-model 1/3 caught, 0/3 allowed: fail
fastapi #16043 no installed rule: fail
fastapi #16049 same-model 3/3 caught, 3/3 allowed: pass; cross-model 2/3 caught, 3/3 allowed: pass
fastapi #16062 same-model 2/3 caught, 3/3 allowed: pass; cross-model 3/3 caught, 3/3 allowed: pass
```

Every rule that passed Spark Open's held-out set is already in the committed `data/registry/*.json`. No candidate is absent from the committed registry. So, as in KN-101, the target is a temp copy of `data/` set back to before the merge. The PR's registry entry, rule file and roots are removed from the copy, and so is its old `data/heldout/airflow/75271` set, so nothing from earlier runs can leak in.

**Chosen: apache/airflow #75271**, "Type the durable default of the common.compat ResumableJobMixin stand-in as bool | None", merged 2026-10-28, base `70a7816`, head `91da700` (matching the committed proof). It is the only PR at 3/3 caught, 3/3 allowed on **both** held-out sets. It is not #75025, so it avoids the near-miss literal problem above, and it is in the same airflow registry KN-101 already proved the install path on.

## 3. Live run: PASSED (rule proven and installed, no human step)

One run, no retries, 2026-11-02, on `spike/self-improving-proof` with no code changes. Real GitHub (`GITHUB_TOKEN`), Spark (`MODEL_API_KEY`) and Spark Open (`BASETEN_API_KEY`). Temp `HOME`/`KNACK_HOME` inside `$W`. The real `~/.knack` and the committed `data/` were not touched (`git status`: only this file). `$W` = `/private/tmp/claude-501/-Users-vedant-Documents-knack-hunt/72dbaf75-2112-4110-9dac-c39c833254bb/scratchpad/live.xQA2di`.

### Fixture

- Registry: `cp -R data $W/data`. Then `$W/data/registry/airflow.json` lost its `../rules/airflow/75271.yml` entry, and `data/rules/airflow/75271.yml`, `data/roots/airflow/75271-{1,2}.json` and `data/heldout/airflow/75271/` were deleted. That leaves 4 airflow rules, saved as `$W/airflow.before.json`.
- Repo: `$W/airflow`, origin `https://github.com/apache/airflow.git`. It holds #75271's 2 changed files at base `70a7816`, fetched read-only from the GitHub contents API. Branch `pr-75271` holds the same files at head `91da700`, committed as `Live proof merge (#75271)`.
- Script: `/private/tmp/claude-501/-Users-vedant-Documents-knack-hunt/72dbaf75-2112-4110-9dac-c39c833254bb/scratchpad/live75271.sh` (the KN-101 `live.sh` with the PR swapped).

### Command and full progress log (verbatim, temp paths shortened to `$W`)

```text
$ knack watch --registry $W/data/registry/airflow.json --muse-settings $W/muse.json
knack watch apache/airflow
  post-merge hook: $W/airflow/.git/hooks/post-merge
  Muse Code PostToolBatch hook: added to $W/muse.json
  watching merges after 6e41c5a
  self-check: Spark Open judges each merge when BASETEN_API_KEY is set
exit 0
#!/bin/sh
# installed by knack watch: runs knack on PRs this merge brought in; never fails the merge.
/usr/bin/arch -arm64 /Users/vedant/Documents/knack-hunt/.venv/bin/python -m knack.watch.hook post-merge --registry $W/data/registry/airflow.json || true
$ git merge --ff-only pr-75271
Updating 6e41c5a..edb7de2
Fast-forward
 .../airflow/providers/common/compat/_resumable_job_mixin.py    | 10 ++++------
 .../tests/unit/common/compat/test__resumable_job_mixin.py      |  5 +++--
 2 files changed, 7 insertions(+), 8 deletions(-)
knack watch apache/airflow: 1 merged PR: #75271
[1/5] select   1 PRs read, 1 kept
[2/5] extract  reading 1 PRs
  #75271: 1 decision, 2 rejected alternatives
  1 decisions found, 2 rejected alternatives (2 verbatim), 0 failed
[3/5] roots    2 Inferred roots written (0 Confirmed, 0 Unknown kept)
[4/5] compile  1 PRs with a verbatim rejected alternative
  adversary: meta-models/muse-spark-open-1026 writes variants, muse-spark-1.3 compiles
  #75271 old release: 3.3.2 (last release before merge 2026-10-28)
  #75271 proven on attempt 2
  #75271 held-out by meta-models/muse-spark-open-1026: 2/3 violations caught, 3/3 compliant allowed (pass)
[5/5] install  1 rules proven, 0 discarded, 5 in registry -> $W/data/registry/airflow.json
self-check airflow-75025 providers/common/compat/src/airflow/providers/common/compat/_resumable_job_mixin.py (the change takes the rejected path): muse-spark-1.3 no, meta-models/muse-spark-open-1026 no; logged only
self-check airflow-75025 providers/common/compat/tests/unit/common/compat/test__resumable_job_mixin.py (the change takes the rejected path): muse-spark-1.3 no, meta-models/muse-spark-open-1026 no; logged only
self-check airflow-75774 providers/common/compat/src/airflow/providers/common/compat/_resumable_job_mixin.py (the change takes the rejected path): muse-spark-1.3 no, meta-models/muse-spark-open-1026 no; logged only
self-check airflow-75774 providers/common/compat/tests/unit/common/compat/test__resumable_job_mixin.py (the change takes the rejected path): muse-spark-1.3 no, meta-models/muse-spark-open-1026 no; logged only
exit 0
```

The merge alone set everything off: the installed `post-merge` hook ran extract → roots → compile → prove → install. Nothing between `git merge` and `[5/5] install` was typed by a person.

### New rule file: `$W/data/registry/rules/75271.yml`

```yaml
id: airflow-75271
language: python
severity: error
message: ResumableJobMixin durable default must be typed as bool | None; bool, Any or bool | Any misrepresents the default or disables type checking.
rule:
  all:
    - any:
        - kind: typed_parameter
        - kind: typed_default_parameter
    - regex: '^durable\s*:'
    - inside:
        all:
          - kind: class_definition
          - regex: ResumableJobMixin
        stopBy: end
    - any:
        - regex: '\bAny\b'
        - all:
            - regex: ':\s*bool\s*='
            - not:
                regex: '=\s*(True|False)\b'
```

The `inside` uses `stopBy: end` (the CLAUDE.md gotcha).

### Registry diff: `diff -u $W/airflow.before.json $W/data/registry/airflow.json`

```diff
@@ -317,6 +317,76 @@
         "not_run": {},
         "rule_sha": "1eba3b1931ed401fcb3fcd0ae259130d76858b0de50ae7f5576af0a09f70bb47",
         "reproved_at": "2026-10-31T23:17:23Z"
+      }
+    },
+    {
+      "rule": "rules/75271.yml",
+      "root_ids": [
+        "airflow-75271-1",
+        "airflow-75271-2"
+      ],
+      "proof": {
+        "pr": 75271,
+        "base_sha": "70a781622611f09ec34f0bbc34c4f05c59ad4c67",
+        "head_sha": "91da700f20f5cad271869fb681953f6d877c75f2",
+        "attempts": 2,
+        "sides": [
+          {"side": "base", "files": 2, "flagged": 1, "errors": 0},
+          {"side": "head", "files": 2, "flagged": 0, "errors": 0},
+          {"side": "rename-base", "files": 2, "flagged": 1, "errors": 0},
+          {"side": "rename-head", "files": 2, "flagged": 0, "errors": 0},
+          {"side": "variant-violation", "files": 3, "flagged": 3, "errors": 0},
+          {"side": "variant-compliant", "files": 3, "flagged": 0, "errors": 0}
+        ],
+        "false_positives": 0,
+        "old_release": {"ref": "3.3.2", "false_positives": 0, "error": null},
+        "heldout": {
+          "author": "meta-models/muse-spark-open-1026",
+          "caught": 2, "violations": 3, "allowed": 3, "compliant": 3, "error": null
+        },
+        "tree_error": null,
+        "heldout_sets": {},
+        "not_run": {},
+        "rule_sha": null,
+        "reproved_at": null
       }
     }
   ]
```

(The `sides` and `old_release`/`heldout` objects are collapsed onto one line each here; the file has them one key per line. The values are unchanged.) The 4 existing entries are byte-for-byte unchanged. No sibling `registry.json` was created.

### Traces: Spark compiled, Spark Open wrote the variants

`$W/data/registry/work/75271/writers.json`:

```json
{
  "compiler": "muse-spark-1.3",
  "variants": "meta-models/muse-spark-open-1026",
  "heldout": "meta-models/muse-spark-open-1026",
  "adversary": "meta-models/muse-spark-open-1026"
}
```

- `work/75271/variants/authors.json` (training) and `work/75271/variants-heldout/authors.json`: all 12 files (6 + 6) `meta-models/muse-spark-open-1026`.
- `work/75271/readings.json`: `muse-spark-1.3` extracted 1 decision (decided by `dabla`) with 2 verbatim rejected alternatives, `bool | Any` and `Any`, quote: "`bool | Any` or `Any` would also be honest, but a union with `Any` switches type checking off for the argument, so `durable="yes"` would pass."
- Roots `$W/data/roots/airflow/airflow-75271-{1,2}.json`: `Inferred`, `seeded: false`, `models: ["muse-spark-1.3"]`.
- `self_checks.jsonl`: 4 lines, for the existing `airflow-75025` and `airflow-75774` roots on this merge's files, all "no, no; logged only".

### Proof gates passed

| Gate | Result | Source |
|---|---|---|
| Base flagged | 1/2 files (the mixin; the test file has no `durable` param) | `proof.sides` |
| Head clean | 0/2 flagged | `proof.sides` |
| Rename base / rename head | 1/2 flagged / 0/2 | `proof.sides` |
| Training violations (Spark Open) | 3/3 caught | `proof.sides` |
| Training compliant (Spark Open) | 3/3 allowed | `proof.sides` |
| False positives on the tree | 0 | `proof.false_positives` |
| Old release 3.3.2 | 0 false positives | `proof.old_release` |
| Held-out (Spark Open; Spark never saw it) | 2/3 caught, **3/3 allowed**: pass (≥2 caught, every compliant allowed) | `proof.heldout`, log line |

Independent re-scan with `.venv/bin/ast-grep` 0.51.0 on the saved work folder gives the same result. Held-out: matches in `violation_1.py:6` and `violation_3.py:6` only. Training: all 3 violations and no compliant files. Base: `_resumable_job_mixin.py:45 durable: bool = _DURABLE_UNSET`. Head: no matches.

The one held-out miss, `violation_2.py`, puts `durable: Any` on a module-level factory function, not on a `ResumableJobMixin` method:

```python
from __future__ import annotations
from typing import Any
from airflow.providers.common.compat._resumable_job_mixin import ResumableJobMixin

def create_orion_operator(task_id: str, durable: Any = None):
    class OrionOp(ResumableJobMixin):
        def __init__(self, **k: Any):
            super().__init__(**k)
    return OrionOp(task_id=task_id, durable=durable)

vals = [create_orion_operator(f't{i}', durable='yes') for i in range(2)]
```

The decision is about the mixin's own signature, so missing this is a recall gap at the edge of scope, not a precision loss.

### What this does and does not prove

- **Proved:** a real merged PR went from merge to an extracted decision, two roots, a rule compiled by Spark and checked against Spark Open's training and held-out variants, and an install into the watched registry file. One live run, no person involved.
- **Not proved: blocking.** Both roots are `Inferred`, and the guard blocks only on Confirmed roots. Until a person confirms `airflow-75271-1`/`-2`, the rule advises and never blocks. That is the intended design, not a gap.
- Small inconsistencies, not fixed: watch writes the entry as `rules/75271.yml` (relative to `data/registry/`), while the committed entries use `../rules/airflow/<pr>.yml`. It names roots `airflow-75271-1.json`, while the committed ones are `75271-1.json`. Both paths resolve, and nothing reads them by name pattern as far as this run shows.
- Unchanged from KN-101: the watch `PostToolBatch` trigger (a merge inside a Muse Code session) did not fire here either.
