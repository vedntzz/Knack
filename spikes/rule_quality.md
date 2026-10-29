# Rule quality: general vs memorized

Scope: the 13 rules in `spikes/batch/apache-airflow/rules/` (5) and
`spikes/batch/fastapi-fastapi/rules/` (8), plus their hits on fastapi `0.115.0`
(`/tmp/fastapi-fastapi-0.115.0`, commit `40e33e4`).

- `<pr>.v2.yml`: compiled against base/head plus main false positives. The
  per-rule tables under "v2 rules" below describe these.
- `<pr>.v3.yml`: v2's checks plus the two rename checks and the generality
  line in the prompt (see "v3: rename checks").
- `<pr>.yml`: v4, v3's checks plus the variant check (see "v4: variant check").
- `<pr>.v1.yml`: base/head only, unchanged.

## Definitions

- **General**: matches a structural pattern (AST shape, metavariables, or the
  repo's long-lived API). It would catch the same mistake written again in
  other code or with other names.
- **Memorized**: anchors on identifiers or literals that are unique to the PR:
  names the PR introduced, test names, the PR's own string values, or one
  class or function. It only catches a near-copy of that PR's diff.

"Introduced by PR" below means the name is in the PR's `head` snapshot but not
its `base` (checked with grep on `src/<pr>/{base,head}`).

## Summary

| | General | Mixed | Memorized | No rule |
|---|---|---|---|---|
| v2 (before) | 3 | 1 | 9 | 0 |
| v3 (after rename checks) | 4 | 3 | 5 | 1 (#75734) |
| v4 (after variant check) | 6 | 2 | 2 | 3 (#74150, #75734, #16043) |

| Repo | v2 | v3 |
|---|---|---|
| apache-airflow | General #75025; Memorized #74150, #75271, #75734, #75774 | General #75025; Mixed #74150, #75774; Memorized #75271; no rule #75734 |
| fastapi | General #14884, #15937; Mixed #16043; Memorized #15139, #15515, #15967, #16049, #16062 | General #14884, #15937, #16043; Mixed #16062; Memorized #15139, #15515, #15967, #16049 |

"Mixed" means at least one branch is general and at least one is memorized.

The pattern: when a decision says *how to do something* (no gather around
reads, no extra columns as sort keys), the compiler writes a structural rule.
When it says *use the thing this PR added*, the compiler anchors on the PR's
new names. That rule passes the PR's own head and does not generalize.

## Rule of thumb: a Confirmed rule has 0 false positives on every check

A rule backed by a Confirmed root blocks, so it must allow every compliant
file on every check: the PR's head, `main`, the held-out branch, the old
release, and the same-model and cross-model compliant variants. Generality
comes second. A memorized rule with 0 false positives can back a Confirmed
root. A general rule with even one false positive cannot, however many
violations it catches.

Applied to #75025 (root `airflow-75025-1`, Confirmed):

| Rule | Cross-model held-out | False positives |
|---|---|---|
| `data/rules/airflow/75025.yml` (hand-repaired, installed) | 0/3 caught, 3/3 allowed | 0 (also 0 on v2-10-stable) |
| `data/rules/airflow/75025.v4.yml` (v4, not installed) | 1/3 caught, 2/3 allowed | 1 compliant variant flagged |

The v4 rule generalizes better but blocks a compliant file, so the installed
rule stays the hand-repaired one. The registry does not load `75025.v4.yml`.

Applied to #75774 (root `airflow-75774-1`, Confirmed): the installed v4 rule
`data/rules/airflow/75774.yml` allows 3/3 cross-model compliant variants. On
Airflow `v2-10-stable` (shallow clone at `12a124a`, 2025-02-24) it has 2 hits,
both in `airflow/providers/microsoft/azure/sensors/msgraph.py`, and no other
file matches:

| Line | What matched | Compared with PR #75774 | Verdict |
|---|---|---|---|
| 109 | `execute()`: `self.defer(trigger=MSGraphTrigger(..., timeout=self.timeout, ...))`, no `timeout=` on the defer, no `sensor_started_at` | Same as base `execute()`; head defers with `sensor_started_at` and the remaining time, and stops passing the sensor timeout to the trigger | true violation, pre-decision |
| 172 | `execute_complete()`: `self.defer(trigger=TimeDeltaTrigger(self.retry_delay), ...)`, no `timeout=`, no `sensor_started_at` | Older than base: base adds `timeout=timedelta(seconds=self.timeout)` (the rejected sliding timeout); v2-10 has no deadline at all (the rejected alternative of `airflow-75774-2`) | true violation, pre-decision |

False positives: **0**, so the rule passes the rule of thumb and stays
installed. The old rule's third hit (line 39, the class never raises
`AirflowSensorTimeout`) is gone because v4 has no class-level check. That is
one fewer true violation reported, not a false positive. The class is still
flagged through both of its defers.

## Known limitation: #16049 matches `cache_key` by name

The #16049 rule is a list of the 10 attribute names `Dependant` had in base
(`$OBJ.cache_key`, `$OBJ.oauth_scopes`, …). It flags any read of those names
on any object. It never looks for `@cached_property` or computed attributes,
which are what the decision removed. On fastapi 0.115.0, `cache_key` is a plain
dataclass field, and the rule flags it 9 times. All 9 are false positives (see
"#16049 (base `ae031be`)" below).

The KN-29 old-release check (`knack init --old-ref`) does not catch this.
All 9 matches are in `fastapi/dependencies/models.py` and
`fastapi/dependencies/utils.py`, and the PR touched both. The check excludes
the PR's own files, so it counts 0.

| #16049 on 0.115.0 | Raw matches | Counted by the old-release check |
|---|---|---|
| Before KN-29 (v4 rule, `spikes/batch/.../16049.yml`) | 9 | — (check did not exist) |
| After KN-29 (recompiled with `--old-ref 0.115.0`, proven on attempt 2) | 9 | 0 |

The recompiled rule is the same 10-name list. With no `--old-ref`, detection
picks 0.139.2 for #16049: the last release tag before its 2026-07-24 merge.

Why this is tolerable: the rule's root `fastapi-16049-1` is **Inferred**, and
it stays that way. The guard blocks only on Confirmed roots, so this rule
advises and never blocks. Do not confirm it until a recompile anchors on
`@cached_property` or `@property` inside `class Dependant`, not on attribute
names.

## v4: variant check

For each decision, Spark writes 3 fresh violations of the rejected approach
and 3 fresh compliant modules (`spikes/batch_variants.py`, cached in
`src/<pr>/variants/`). It sees the decision and the PR code as context. The
prompt asks for new identifiers, a different structure, no copying, and the
real API the decision is about. The verifier needs **≥2/3 violations flagged
and 3/3 compliant allowed**, on top of every v3 check. Misses go back to the
compiler with their source, for up to 5 attempts. The variants are generated
once per PR, so every attempt and every rule version is scored on the same 6
files. Logs: `compile_run5_{airflow,fastapi}.log`. #75734 and #15139 hit
connection errors in the batch and were rerun alone
(`compile_run5_rerun_{75734,15139}.log`).

### Variant pass rate

Pass = ≥2/3 violations flagged, 3/3 compliant allowed, and the rule parses.

| Rule set | Pass | Violations caught | Compliant allowed |
|---|---|---|---|
| v2 rules (no recompile) | 3/13 (#15139, #15515, #16049) | — | — |
| v3 rules (no recompile) | 4/12 (#74150, #15515, #16049, #16062) | — | — |
| v4 attempt 1 (compiled before seeing any variant) | **3/13** (#74150, #15139, #16049) | 12/39 (31%) | 36/39 |
| v4 final (variants fed back, ≤5 attempts) | **10/13** | 28/30 | 30/30 |

**The held-out number is attempt 1: 3/13.** A rule compiled from the PR alone
catches 31% of fresh violations. The final 10/13 is fitted to the same 6
variants it is scored on, so it is a training score, not a held-out one.
#15967 shows the cost: its final rule matches strings (`"fix them all"`,
`"remaining redirects"`) that appear only in its own `violation_1.py` and
`violation_2.py`.

### Held-out pass rate

A second variant set per PR (`src/<pr>/variants-heldout/`,
`spikes/batch_heldout.py`) is never shown to the compiler. A test checks that
`batch_compile.py` never mentions it. It uses the same prompt as the training
set. Spark has no seed parameter (the API returns `unknown parameter
\`seed\``), and it samples at temperature 1.0, so the held-out set is an
independent resample. Overlap with the training set: 0/6 identical modules on
every PR, and 0–4 shared non-import lines out of 24–76 per PR.
Logs: `heldout_run_{airflow,fastapi}.log`.

| Rule set | Held-out pass | Violations caught | Compliant allowed |
|---|---|---|---|
| v3 rules | 3/12 (#74150, #15937, #16049) | — | — |
| v4 attempt 1 (before any variant feedback) | 2/13 (#74150, #16049) | 10/39 | 36/39 |
| **v4 final** | **8/10 rules, 8/13 PRs** | **23/30** | **28/30** |
| **v4 final, cross-model held-out (Spark Open)** | **7/10 rules, 7/13 PRs** | **21/30** | **26/30** |

| Rule | Same-model held-out (caught, allowed) | | Cross-model held-out (caught, allowed) | |
|---|---|---|---|---|
| #75025 | 3/3, 3/3 | pass | 1/3, 2/3 | **fail**: flags a compliant list that names `"state"`/`"start_date"` only to filter them out |
| #75271 | 3/3, 3/3 | pass | 3/3, 3/3 | pass |
| #75774 | 2/3, 3/3 | pass | 3/3, 3/3 | pass |
| #14884 | 2/3, 3/3 | pass | 3/3, 3/3 | pass |
| #15515 | 3/3, 3/3 | pass | 2/3, 3/3 | pass |
| #15937 | 3/3, 3/3 | pass | 1/3, 3/3 | **fail**: misses 2 of Spark Open's SSE/JSONL violations |
| #16049 | 3/3, 3/3 | pass | 2/3, 3/3 | pass |
| #16062 | 2/3, 3/3 | pass | 3/3, 3/3 | pass |
| #15139 | 1/3, 3/3 | **fail**: memorized operation ids | 2/3, 3/3 | pass, but see below |
| #15967 | 1/3, 1/3 | **fail**: memorized URL and variant strings | 1/3, 0/3 | **fail** |
| #74150, #75734, #16043 | — | no rule | — | no rule |

The held-out set is not easy. Rules from before the feedback pass 2–3 of
12–13 on it. The final rules pass 8/10, so fitting to the training variants
mostly carried over to an independent sample. The fit that didn't carry over
is in the two memorized rules, and that is where it should fail.

### Cross-model held-out (KN-28)

A third set per PR (`src/<pr>/variants-heldout-cross/`) is written by Spark
Open (`meta-models/muse-spark-open-1026`), not by Spark, which compiled the
rules. Each set's `authors.json` records the model. The prompt is the same
(diffed against the retired `batch_variants.py`: identical). The pass bar is
the same as the same-model rows: ≥2/3 violations caught and 3/3 compliant
allowed, scored by `knack.pipeline.heldout.score_heldout`. No rule was
recompiled. Overlap with the same-model held-out set is 0/6 identical
modules on every PR. Script: `spikes/heldout_cross.py`. Log:
`heldout_cross_run.log`.

**7/10 cross-model against 8/10 same-model.** The pass rate barely moves. The
rules that fail are different:
- #75025 and #15937 pass Spark's held-out set but fail Spark Open's. #75025's
  rule flags `"state"`/`"start_date"` literals in a list with `SortParam`. Spark
  Open's `compliant_3.py` writes those names into a candidate list and then
  filters them out, and the rule flags that. It also misses 2 violations.
  #15937 catches 1 of 3 violations.
- #15139 fails Spark's held-out set but passes Spark Open's. It passes on the
  memorized branch, not on generality. All 3 Spark Open violations carry a
  `2.11` pydantic version string, and the rule's `>=…2.11` regex branch
  matches it. The rule is still memorized. The adversary happened to write
  the same literal.
- #15967 fails both sets.

So the cross-model check is not a stricter version of the same-model check.
It finds a different set of weak rules (#75025, #15937). A rule that passes
both sets is better supported than one that passes either. 6 of 10 pass
both: #75271, #75774, #14884, #15515, #16049 and #16062.

Limits:
- Spark and Spark Open are both Muse models, and every set uses one prompt.
  "Cross-model" here does not mean another vendor.
- The two same-model sets come from the same model and prompt. They measure generality
  within Spark's idea of the violation, not against code people actually
  write.
- #16049 passes held-out 3/3, 3/3 and still gives 9 FPs on fastapi 0.115.0.
  The variants never use `cache_key` as a plain dataclass field, so the
  variant check cannot see that failure.

### Variant quality

The first variant prompt only said "new identifiers, different structure, no
copying". Spark responded by stubbing the repository API: fake `SortParam`,
`DagModel` and `PauseTrigger` classes, and a `@cached_property` on an
unrelated class that #16049 "caught" only through a `.cache_key` read. The
prompt now also says to import the real API the decision is about, never
define stand-ins, and write only code a reviewer applying the decision would
reject or accept. The variants were regenerated before any number above was
taken. In the regenerated set, the #75774 violations subclass the real
`MSGraphSensor` and the #75025 ones use the real `SortParam`/`DagModel`.
**#16043 is still off-target.** Its violations are caller-side
`jsonable_encoder(..., exclude=...)` calls, but the decision is about the
function's own dict-branch recursion. No structural rule can flag those, and
that is why #16043 ended with no rule.

### v4 compile results

| Rule | Attempt | v4 label | Notes |
|---|---|---|---|
| #74150 | FAIL | no rule | Attempt 1 caught 3/3 variants but not the PR's own base. Later attempts flagged base with 1–4 main false positives. Old rule kept as `74150.v3.yml`. |
| #75025 | 4 | General | `"state"`/`"start_date"` literals in a list or dict that also holds allowed keys or `DagRun.state`/`start_date`, inside code that has `SortParam(…, DagModel, …)`. Follows the keys through a variable, which v3 did not. |
| #75271 | 5 | Mixed | `durable` annotated `bool` (default not `True`) or `Any` in `__init__` of `ResumableJobMixin` *or any subclass*; the exact `self.durable = False` statement is gone. The test-name branch (`test_durable_left_at_default_does_not_warn`) remains. |
| #75734 | FAIL | no rule | 3–9 main false positives on most attempts; 2 attempts did not parse. Old rule kept as `75734.v2.yml`. |
| #75774 | 3 | General | `self.defer(…)` with `MSGraphTrigger`/`TimeDeltaTrigger` and no `kwargs=` (the start time is not carried) in a class whose text mentions `MSGraphSensor`, so subclasses count. The test-name branch is gone. |
| #14884 | 2 | General | `start_soon`/`create_task`/`gather` in a function that reads `$F.read`. The `.read` may be in a nested helper, which v3 missed. Broad. |
| #15139 | 3 | Memorized | `snapshot(…)` with the PR's test operation ids (`get_user_users_get`, `save_union_body_discriminator_items__post`), plus a `pydantic … 2.11` string regex. |
| #15515 | 4 | General | `splitlines`/`re.split` inside a function that builds `data: …` / `: …` SSE lines. `format_sse_event` and the import-line branch are gone. |
| #15937 | 2 | General | `StreamingResponse` with an SSE/JSONL media type and no `**` expansion (the response args are not spread). Textual. |
| #15967 | 3 | Memorized | The `www.starlette.dev/applications/` URL, plus 3 strings copied from its own variants. |
| #16043 | FAIL | no rule | Variants are off-target, see above. Old rule kept as `16043.v3.yml`. |
| #16049 | 1 | Mixed | Still the 10 base attribute names, plus a new structural branch: `@cached_property` inside `class Dependant`. |
| #16062 | 2 | General | `@lru_cache` with maxsize ≠ 4096, `None` or missing, on the `_is_*_callable_cached` functions (or ones that call `_is_*_callable`). The anywhere-in-the-repo `cache_info.maxsize` branch is gone. |

### fastapi 0.115.0 rescan (v4)

| Rule | v3 matches | v4 matches | v4 verdict |
|---|---|---|---|
| #14884 | 1 | 1 (`utils.py:856`, the `start_soon` line) | true, pre-decision |
| #16043 | 2 | — (no rule) | the 2 true pre-decision hits are lost |
| #16049 | 9 | 9 | all false positives, same sites |
| others | 0 | 0 | — |
| **Total** | **12 (9 FP)** | **10 (9 FP)** | |

### Takeaways

- The variant check moved the labels the most: 6 general (from 4) and 2
  memorized (from 5). It did this by turning class- and test-name anchors
  into subclass-aware or data-flow structure (#75025, #75271, #75774, #15515,
  #16062).
- It costs compiles: 3 PRs now have no rule. #16043 fails because of bad
  variants, not a bad compiler.
- Fitting to the feedback is real (#15967), but mostly it generalizes. On
  the held-out set the final rules pass 8/10, against 2/13 before feedback.
  The two held-out failures are exactly the two memorized rules.
- #16049's memorized attribute branch passes every check, variants included.
  Its 9 FPs on 0.115.0 are unchanged.

## v3: rename checks

`spikes/batch_compile.py` now runs two checks besides base, head and main
(code in `spikes/batch_rename.py`):

- **rename-head (must flag 0):** every identifier in the PR's head files but
  in none of its base files is renamed to a random `_r…` name. Builtins,
  keywords and dunders are skipped. The rename is by whole word across the
  whole text, including strings, comments and docstrings, because regex rules
  read all of it. String prefixes (`f""`, `rb""`) are left alone.
- **rename-base (must flag ≥1):** function-local variables in the base files
  are renamed. This covers assigned names and loop, `with` and comprehension
  targets, and closures follow their enclosing local. Parameters, module
  names, attributes and `global`/`nonlocal` names keep their spelling.

The prompt gains: "Do not match identifiers introduced by this PR; match the
structure of the violation." Renamed copies are written to
`src/<pr>/rename-{base,head}/` for inspection. Run logs:
`compile_run4_airflow.log`, `compile_run4_fastapi.log`. #74150 and #16049
hit a Spark `ReadTimeout` in the batch and were rerun alone
(`compile_run4_airflow_74150.log`, `compile_run4_fastapi_16049.log`).

### v2 rules under the new checks (no recompile)

| Fails rename-head | Fails rename-base | Pass both |
|---|---|---|
| #74150, #75774, #15139, #16043 | none | the other 9 |

The checks catch 4 of the 9 memorized or mixed v2 rules. Rename-base caught
nothing, because no v2 rule anchored on a base local variable.

### v3 compile results

12 of 13 passed. #75734 failed all 5 attempts. Every attempt still keyed on
the `resumable_job` *string literal* (a metric name, not an identifier, so the
rename leaves it alone). The attempts failed on history or main false
positives, and attempt 4 did not parse. No `75734.yml` exists now; the old
rule is `75734.v2.yml`.

| Rule | Attempt | v3 label | Change vs v2 |
|---|---|---|---|
| #74150 | 3 | Mixed | Dropped `aget_conn`/`acreate_agent`/`_ConnRegistry`. Branch 2 is structural: `run_in_executor(None, …)` / `to_thread(…)` wrapping `get_conn`/`create_agent`/`get_connection`/`get_hook` (long-lived names). Branch 1 is memorized and whole-module: it flags any module that has `FallbackModel` and `MaskingCapability` but no `await`. |
| #75025 | 1 | General | Same shape as v2: `SortParam` + `DagModel` + `"state"`/`"start_date"`. |
| #75271 | 3 | Memorized | Still `__init__` in `class ResumableJobMixin` with `self.durable = False`, then regex on the annotation. Adds a branch on the test name `test_durable_left_at_default_does_not_warn`. |
| #75734 | — | no rule | See above. |
| #75774 | 3 | Mixed | Dropped `sensor_started_at` and `AirflowSensorTimeout`. Branches 1–3 are structural inside `class MSGraphSensor`: `self.defer` with `MSGraphTrigger` and no `timeout=`, or `TimeDeltaTrigger` with `self.timeout`. Branch 4 flags the test `test_execute_complete_passes_timeout_to_defer` by name. |
| #14884 | 1 | General | `async with … create_task_group()` that has `.start_soon(…)` and `$OBJ.read`. Narrower than v2 (no `gather` branches) and no longer double-matches. |
| #15139 | 2 | Memorized | Dropped `IsOneOf` and the `>=2.11` version pin. Still keys on the test strings `PlatformRole` and `save_union_body_discriminator` inside `snapshot(…)`. These exist in base, so rename-head does not touch them. |
| #15515 | 4 | Memorized | Same as v2: `splitlines` inside `format_sse_event`, plus the bare `from fastapi.sse import ServerSentEvent` import line. |
| #15937 | 2 | General | `StreamingResponse(…)` with `text/event-stream`/`application/jsonl` whose text has `background`. Textual, as in v2. |
| #15967 | 1 | Memorized | Same two `www.starlette.dev` anchors. |
| #16043 | 1 | General | The memorized test-name branch is gone. Only `jsonable_encoder(…)` inside `if isinstance($OBJ, dict)` that forwards `exclude_unset`/`exclude_none` but not `exclude_defaults`. |
| #16049 | 2 | Memorized | Only the 10 base attribute names (`$X.cache_key`, `$X.oauth_scopes`, …). This is v2's FP branch with the rest removed. |
| #16062 | 1 | Mixed | Dropped `_CALLABLE_CLASSIFICATION_CACHE_SIZE`. Branch 1: `@lru_cache(maxsize=N)` with N ≠ 4096 inside a `*callable_cached*` function (the decision's scope; the value is the decision itself). Branch 2 still flags any `cache_info.maxsize == N` with N ≠ 4096, anywhere. |

### fastapi 0.115.0 rescan (v3)

| Rule | v2 matches | v3 matches | v3 verdict |
|---|---|---|---|
| #14884 | 2 (1 site) | 1 | true, pre-decision |
| #16043 | 3 | 2 | both true, pre-decision; the test-name FP is gone |
| #16049 | 9 | 9 | all false positives, same sites as v2 |
| others | 0 | 0 | — |
| **Total** | **14 (10 FP)** | **12 (9 FP)** | |

### What the checks do not catch

Every memorized v3 branch anchors on a name or literal that **already exists
in base**: a class (`ResumableJobMixin`, `MSGraphSensor`), a test name or test
string, the attribute names `Dependant` used to have, a URL, a metric string.
Rename-head only renames what the PR *added*, and rename-base only renames
locals, so these survive both checks. The next check would rename base-side
class, attribute and test names too, or require a held-out violation written
under different names.

## v2 rules (`<pr>.v2.yml`, before)

### apache-airflow

| Rule | Label | Why |
|---|---|---|
| #74150 | Memorized | All 5 branches require `class PydanticAIHook` or `_ConnRegistry` / `FALLBACK_CONN_IDS_EXTRA_KEY`. The "fix" signal is the PR-introduced names `aget_conn`/`acreate_agent` (0 in base, 2 in head). Branch 2 fires on any module that mentions `_ConnRegistry` without those names. The `run_in_executor(None)` / `to_thread` / `max_workers` checks are structural but only apply to that one class. |
| #75025 | General | `SortParam($$$)` over `DagModel` with a `'state'` or `'start_date'` string literal. `SortParam` and `DagModel` are long-lived API (both in base). The literals are the forbidden keys themselves, not PR artifacts. It catches the keys being re-added to any DagModel sort. |
| #75271 | Memorized | Must be `__init__` inside `class ResumableJobMixin` and contain the exact statement `self.durable = False`, then regex on the `durable:` annotation. It covers one class in one compat stand-in file. It misses the same annotation mistake on any other parameter or class. |
| #75734 | Memorized | Module contains `POD_IDENTIFIER_STATE_KEY` and nowhere contains the substring `resumable_job` (0 in base, 2 in head). It does not look at metric calls at all. A KPO module that adds a made-up metric but mentions `resumable_job` in a comment passes. Any module that imports the constant and has no metrics fails. |
| #75774 | Memorized | Every branch is gated on `class MSGraphSensor`. The required fix tokens are `sensor_started_at` and `AirflowSensorTimeout`, both PR-introduced (0 in base). A correct fix that used another variable name would still be flagged. Branch 6 flags the whole class if `AirflowSensorTimeout` does not appear. |

### fastapi

| Rule | Label | Why |
|---|---|---|
| #14884 | General | `anyio.create_task_group` / `create_task_group` / `asyncio.TaskGroup` / `$TG.start_soon` / `asyncio.gather` / `anyio.gather` that contain `$X.read`. All metavariables, no fastapi names. Weaknesses: it is broad (any `.read` attribute, not only `UploadFile`), and branches 1 and 4 overlap, so one site gives 2 matches (seen on 0.115.0). |
| #15139 | Memorized | Branches 1–2 key on the test-only strings `PlatformRole` and `save_union_body_discriminator` and require PR-introduced `IsOneOf` (0 in base). Branch 3 is a literal `>=.*2\.11` in any string, in any module whose text matches `[Pp]ydantic`. That is a version pin, not a pattern. |
| #15515 | Memorized | Branch 1 is structural (`splitlines`/`re.split` inside a function), but only inside `def format_sse_event`. Branch 2 is a pure diff memory: it flags the line `from fastapi.sse import ServerSentEvent` with nothing after it. That is the base test file's import, which the PR extended to add `format_sse_event`. It flags any file that imports only `ServerSentEvent`. |
| #15937 | General | `StreamingResponse($$$)` whose text has `text/event-stream` or `application/jsonl` and no `response_args`. `_build_response_args` already existed in base, so this is "use the existing helper", not a PR-introduced name. The check is textual, so any variable named `*response_args*` satisfies it. |
| #15967 | Memorized | Grep for two specific anchors on `www.starlette.dev`. It cannot catch any other dead link. Fine as a lint, but it encodes no pattern. |
| #16043 | Mixed (general branch + memorized branch) | Branch 1 is the decision: a `jsonable_encoder(...)` recursion inside an `isinstance(..., dict)` branch of `def jsonable_encoder` that drops `exclude_defaults` or passes `include=`/`exclude=`. It is scoped to the function the decision is about, which is fine. Branch 2 is memorized: a module that contains the test name `test_encode_model_with_default` but not the PR's new test name `test_encode_model_with_default_in_dict_and_list`. It encodes "the PR's test exists", not the decision, and it matches at line 1 (whole module). |
| #16049 | Memorized | A hard-coded list of the 10 `cached_property` names from base (`cache_key`, `oauth_scopes`, `is_gen_callable`, …). Branch 2 flags any `.cache_key` / `.oauth_scopes` / … attribute access anywhere, on any object. The general form of the decision would be "no `@cached_property`/`@property`/methods inside `class Dependant`" or "Dependant is `@dataclass(slots=True)`". |
| #16062 | Memorized | Requires the literal `4096` and the PR-introduced `_CALLABLE_CLASSIFICATION_CACHE_SIZE` (0 in base). It only applies inside the 3 `_is_*_cached` functions. Branch 3 flags any `assert X.maxsize == N` with N ≠ 4096, anywhere in the repo. |

### fastapi 0.115.0 hits vs PR base

0.115.0 (Sep 2024) predates all three PRs. Each hit was compared with the
file at the PR's `base_sha` snapshot in `src/<pr>/base/`. Rescan command:
`.venv/bin/ast-grep scan --rule spikes/batch/fastapi-fastapi/rules/<id>.yml --json /tmp/fastapi-fastapi-0.115.0`.
The other five fastapi rules have 0 hits on 0.115.0.

#### #14884 (base `8bdb0d2`): 2 matches, 1 site → true violation, pre-decision

| Location | What matched | vs base | Verdict |
|---|---|---|---|
| `fastapi/dependencies/utils.py:854` | `async with anyio.create_task_group() as tg:` around `tg.start_soon(process_fn, sub_value.read)` | Same code as base `_extract_form_body` (base:913–915). Head replaces it with `results.append(await sub_value.read())` in a plain loop | true violation, pre-decision |
| `fastapi/dependencies/utils.py:856` | `tg.start_soon(process_fn, sub_value.read)` (same site, branch 4) | same | duplicate of the above |

#### #16043 (base `5e8b7f1`): 3 matches → 2 true, 1 false positive

| Location | What matched | vs base | Verdict |
|---|---|---|---|
| `fastapi/encoders.py:281` | dict-branch `jsonable_encoder(key, ...)` forwarding `exclude_unset`/`exclude_none` but not `exclude_defaults` | Same as base:298. The head diff is exactly `+exclude_defaults=exclude_defaults` on this call | true violation, pre-decision |
| `fastapi/encoders.py:289` | dict-branch `jsonable_encoder(value, ...)`, same omission | Same as base:306; head adds the kwarg | true violation, pre-decision |
| `tests/test_jsonable_encoder.py:1` | whole module: has `test_encode_model_with_default`, lacks `..._in_dict_and_list` | Base has the same state (only head adds the new test) | **false positive**. A missing regression test is not a breach of "forward `exclude_defaults`". It comes from the memorized branch 2 |

#### #16049 (base `ae031be`): 9 matches → all false positives

| Location | What matched |
|---|---|
| `fastapi/dependencies/models.py:37` | `self.cache_key = (self.call, tuple(sorted(set(self.security_scopes or []))))` in `__post_init__` |
| `fastapi/dependencies/utils.py:177, 190, 584, 585, 621, 622, 633, 634` | reads/writes of `dependant.cache_key` / `sub_dependant.cache_key` |

In base, `cache_key` is a `@cached_property` that computes the key from
`oauth_scopes`, `_uses_scopes` and `computed_scope`. That is the
computed-attribute style #16049 removed (head moves it to
`_get_cache_key(dependant=...)` and makes `Dependant` `@dataclass(slots=True)`).
In 0.115.0, `cache_key` is a declared dataclass field
(`cache_key: Tuple[...] = field(init=False)`). It holds a value, and the class
has no `cached_property` and no computed attributes. The rule fires only
because the attribute is *named* `cache_key`. 0.115.0 is not the base's
forbidden construct. **Verdict: false positive (9/9).**

Caveat: `__post_init__` does compute one derived value inside the class. A
strict reading of "class is just holding data" could count models.py:37 as
borderline. The 8 `utils.py` hits are plain field accesses either way. None of
these hits flags `cached_property` (the thing the decision removed), because
the rule matches names, not decorators.

#### Tally on 0.115.0

| Rule | Matches | Distinct sites | True (pre-decision) | False positive |
|---|---|---|---|---|
| #14884 | 2 | 1 | 1 site (2 matches) | 0 |
| #16043 | 3 | 3 | 2 | 1 |
| #16049 | 9 | 9 | 0 | 9 |
| **Total** | **14** | **13** | **3 sites (4 matches)** | **10** |

Both FP sources are memorized branches: #16043 branch 2 (test name) and #16049
branch 2 (bare attribute names). The general rule (#14884) and the general
branch of #16043 gave only true pre-decision hits. As in
`heldout_precision.md`, pre-decision hits are code from before the decision,
not new violations. They count as neither a precision loss nor a precision win.

## Implications (v2)

- 9 of 13 repaired rules are memorized. Held-out zero-hit results (Airflow
  v2-10, and the 5 silent fastapi rules here) mostly mean "the PR's names don't
  exist there yet", not "the rule is precise".
- Rules gated on names the PR introduced (`sensor_started_at`,
  `_CALLABLE_CLASSIFICATION_CACHE_SIZE`, `resumable_job`, `aget_conn`,
  `IsOneOf`) use the fix's spelling as the test of compliance. A correct fix
  under another name gets blocked.
- Branches that flag a whole module from "has X, lacks Y" text (#74150 b2,
  #75734, #16043 b2) are the line-1 failure mode that `.v1` repair was meant to
  remove. It is still there.
