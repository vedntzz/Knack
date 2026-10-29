# Rule quality: general vs memorized

Scope: every non-`.v1` rule in `spikes/batch/apache-airflow/rules/` (5) and
`spikes/batch/fastapi-fastapi/rules/` (8), plus the #14884, #16043 and #16049
hits on fastapi `0.115.0` (`/tmp/fastapi-fastapi-0.115.0`, commit `40e33e4`).

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

| Repo | General | Memorized |
|---|---|---|
| apache-airflow | 1 (#75025) | 4 (#74150, #75271, #75734, #75774) |
| fastapi | 2 (#14884, #15937) + 1 mixed (#16043) | 5 (#15139, #15515, #15967, #16049, #16062) |
| **Total (13)** | **3, plus 1 mixed** | **9** |

The pattern: when a decision says *how to do something* (no gather around
reads, no extra columns as sort keys), the compiler writes a structural rule.
When it says *use the thing this PR added*, the compiler anchors on the PR's
new names. That rule passes the PR's own head and does not generalize.

## apache-airflow

| Rule | Label | Why |
|---|---|---|
| #74150 | Memorized | All 5 branches require `class PydanticAIHook` or `_ConnRegistry` / `FALLBACK_CONN_IDS_EXTRA_KEY`. The "fix" signal is the PR-introduced names `aget_conn`/`acreate_agent` (0 in base, 2 in head). Branch 2 fires on any module that mentions `_ConnRegistry` without those names. The `run_in_executor(None)` / `to_thread` / `max_workers` checks are structural but only apply to that one class. |
| #75025 | General | `SortParam($$$)` over `DagModel` with a `'state'` or `'start_date'` string literal. `SortParam` and `DagModel` are long-lived API (both in base). The literals are the forbidden keys themselves, not PR artifacts. It catches the keys being re-added to any DagModel sort. |
| #75271 | Memorized | Must be `__init__` inside `class ResumableJobMixin` and contain the exact statement `self.durable = False`, then regex on the `durable:` annotation. It covers one class in one compat stand-in file. It misses the same annotation mistake on any other parameter or class. |
| #75734 | Memorized | Module contains `POD_IDENTIFIER_STATE_KEY` and nowhere contains the substring `resumable_job` (0 in base, 2 in head). It does not look at metric calls at all. A KPO module that adds a made-up metric but mentions `resumable_job` in a comment passes. Any module that imports the constant and has no metrics fails. |
| #75774 | Memorized | Every branch is gated on `class MSGraphSensor`. The required fix tokens are `sensor_started_at` and `AirflowSensorTimeout`, both PR-introduced (0 in base). A correct fix that used another variable name would still be flagged. Branch 6 flags the whole class if `AirflowSensorTimeout` does not appear. |

## fastapi

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

## fastapi 0.115.0 hits vs PR base

0.115.0 (Sep 2024) predates all three PRs. Each hit was compared with the
file at the PR's `base_sha` snapshot in `src/<pr>/base/`. Rescan command:
`.venv/bin/ast-grep scan --rule spikes/batch/fastapi-fastapi/rules/<id>.yml --json /tmp/fastapi-fastapi-0.115.0`.
The other five fastapi rules have 0 hits on 0.115.0.

### #14884 (base `8bdb0d2`): 2 matches, 1 site → true violation, pre-decision

| Location | What matched | vs base | Verdict |
|---|---|---|---|
| `fastapi/dependencies/utils.py:854` | `async with anyio.create_task_group() as tg:` around `tg.start_soon(process_fn, sub_value.read)` | Same code as base `_extract_form_body` (base:913–915). Head replaces it with `results.append(await sub_value.read())` in a plain loop | true violation, pre-decision |
| `fastapi/dependencies/utils.py:856` | `tg.start_soon(process_fn, sub_value.read)` (same site, branch 4) | same | duplicate of the above |

### #16043 (base `5e8b7f1`): 3 matches → 2 true, 1 false positive

| Location | What matched | vs base | Verdict |
|---|---|---|---|
| `fastapi/encoders.py:281` | dict-branch `jsonable_encoder(key, ...)` forwarding `exclude_unset`/`exclude_none` but not `exclude_defaults` | Same as base:298. The head diff is exactly `+exclude_defaults=exclude_defaults` on this call | true violation, pre-decision |
| `fastapi/encoders.py:289` | dict-branch `jsonable_encoder(value, ...)`, same omission | Same as base:306; head adds the kwarg | true violation, pre-decision |
| `tests/test_jsonable_encoder.py:1` | whole module: has `test_encode_model_with_default`, lacks `..._in_dict_and_list` | Base has the same state (only head adds the new test) | **false positive**. A missing regression test is not a breach of "forward `exclude_defaults`". It comes from the memorized branch 2 |

### #16049 (base `ae031be`): 9 matches → all false positives

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

### Tally on 0.115.0

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

## Implications

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
