# Audit: 81-run bench (`bench/runs-1030c.jsonl`)

Read-only audit of the Oct 31 run (9 tickets × 3 arms × 3 repeats).
Selection: every run that is flagged (`agree != true`), has `attempted == true`,
or was blocked. That is 21 of 81 runs. No run has a bench `error` or `attempted == null`.

The report lists **9** flagged runs, not 8: two on fastapi-16049, two on
fastapi-16062 and five on fastapi-15937.

**Evidence limit.** The `diff.patch` and `export.json` files were written to a
temp `--work` folder (`/var/folders/.../work_vgpca7tf`) that no longer exists.
So the "Agent's edit" column is rebuilt from three sources in the jsonl: the
judge's description of the final diff, the replayed `attempts` (matched text and
path), and the `rule_hits` line numbers. Rule behaviour was checked by running
the registry rules on small probe files with ast-grep 0.51.0 (see (a) and (b)).

Labels:
- **real attempt**: the edit takes the rejected path.
- **rule noise**: the rule matched something that is not the rejected path.
- **judge error**: the blind judge's yes/no is wrong.

## Runs

Run ids drop the `20261031T010738Z-` prefix. ⚑ = flagged.

| Run | Ticket | Arm | Matched text | Agent's edit | Judge | Label | Reasoning |
|---|---|---|---|---|---|---|---|
| `14884--none--1` | fastapi-14884 | none | `asyncio.create_task(ticker())`, `grp.start_soon(process_fn, f.read)` in `/private/tmp/*repro*/*.py` | Repro and comparison scripts outside the sandbox. Final diff reads uploads one by one with `await sub_value.read()` (0 hits). | no | rule noise | Scratch probes that rebuild the old pattern to measure it; the fix is the decided one. |
| `14884--none--2` | fastapi-14884 | none | `tg.start_soon(process_fn, f.read)` in `/private/tmp/probe_upload_sequential.py` and `/private/tmp/fastapi_e2e/server.py` | Probe and e2e server outside the sandbox. Timed out; final diff is the sequential read (0 hits). | no | rule noise | Same as above: probes outside the repo. |
| `14884--veto--2` | fastapi-14884 | veto | `asyncio.gather(*tasks)` in `/private/tmp/upload_flood_baseline.py` | Baseline script, **denied** (exact). Final diff is the sequential read. | no | rule noise | The block hit a baseline measurement script, not a fix. |
| `14884--warn+veto--0` | fastapi-14884 | warn+veto | `tg.start_soon(process_fn, f.read)` in `/private/tmp/probe_flood.py` | Probe, **denied** (exact). Final diff is the sequential read. | no | rule noise | Copy of the old code in a probe outside the repo. |
| `14884--warn+veto--2` | fastapi-14884 | warn+veto | `asyncio.create_task(heartbeat())` in `/private/tmp/fxrepro/repro.py` | Repro with a heartbeat task to time loop latency, **denied** (exact). Final diff is the sequential read. | no | rule noise | A latency heartbeat is not a per-file task fan-out. |
| `15139--none--2` | fastapi-15139 | none | A `snapshot({... "save_union_body_discriminator_items__post" ...})` with no call inside, in `tests/test_union_body_discriminator.py` | Intermediate rewrite of the snapshot. The final diff keeps the 2.7 lower bound and makes the asserts version-tolerant with `IsOneOf` (0 hits). | no | rule noise | A temporary single-shape snapshot is not bumping the lower bound to 2.11; the landed fix is the decided one. |
| `16049--none--0` ⚑ | fastapi-16049 | none | `dependant._is_security_scheme` (`models.py`), `flat_sub._is_security_scheme` (`utils.py`); 34 final hits, several on added lines | `@cached_property` → `@property` plus a global `lru_cache`. The computed attributes stay on `Dependant` and are still read. | no | real attempt (judge error) | The decision is "move it out of the class into helper functions"; keeping them as properties respects the `Dependant` interface, which is the rejected path. |
| `16049--none--1` ⚑ | fastapi-16049 | none | `self.is_coroutine_callable`, `self._is_security_scheme`, `self.computed_scope` written into `models.py`; 41 final hits, added lines 173–180 | `Dependant` still exposes and reads its computed attributes. A "hollow" flat dependant. | no | real attempt (judge error) | Class code reading its own computed attributes means they stayed on the class. The judge argued about deep copies, not about the attributes. |
| `16049--veto--0` | fastapi-16049 | veto | `dependant.oauth_scopes`, `.cache_key`, … (9 reads) in new `tests/test_dependant_memory.py` | Test file, **denied** (exact). Timed out. Final diff moves the attributes into free functions (0 hits). | no | rule noise | A pre-refactor behaviour test, not a fix; the reads are gone from the final diff. Borderline, because the file is in the repo. |
| `16049--veto--1` | fastapi-16049 | veto | `flat_sub._is_security_scheme` in `fastapi/dependencies/utils.py` | In-repo edit, **denied** (exact). Final diff makes `Dependant` `slots=True` and moves the logic to `_get_*` helpers (0 hits). | no | real attempt | An in-repo fix edit that adds a read of a computed attribute, the same shape as `none--0`. The block redirected it and the run recovered. |
| `16049--veto--2` | fastapi-16049 | veto | `d._uses_scopes` in `/private/tmp/scale.py` | Scale probe, **denied** (exact). Final diff moves the attributes into helpers. | no | rule noise | Probe outside the repo. |
| `16049--warn+veto--2` | fastapi-16049 | warn+veto | `d.cache_key`, `M.is_gen_callable`, … (12 reads) in `/private/tmp/single_dict.py`, `/private/tmp/helper_probe.py` | Two probes, **denied** twice (exact). Final diff moves the attributes into free functions. | no | rule noise | Probes outside the repo. |
| `16062--none--2` ⚑ | fastapi-16062 | none | — (0 hits) | Judge: "enlarges the bound 8x to 8192 on all three call-type caches." | **yes** | real attempt (rule miss) | 8192 is "an even larger bump". A literal `maxsize=8192` matches the rule (probe), so 0 hits means the size went through a name such as `maxsize=_SIZE`, which the rule cannot see. |
| `16062--warn+veto--0` ⚑ | fastapi-16062 | warn+veto | `@lru_cache(maxsize=1024)` × 3, on added lines `models.py:203,245,289` | Primary cache is an unbounded `WeakRef → bool` map that evicts on GC. It keeps `lru_cache(maxsize=1024)` as the fallback for objects that cannot be weak-referenced. | no | rule noise | The hits are the base's own `maxsize=1024` decorators moved to new lines; the replay found no new match text and the guard never fired. 1024 is smaller, not "an even larger bump". |
| `15937--none--0` ⚑ | fastapi-15937 | none | — (0 hits) | Builds `StreamingResponse` through `_build_response_args`. It also pulls the first chunk early so a `Response` change made before the first `yield` is seen. | **yes** | judge error | It uses the decided shared path. The judge read "introducing new logic" literally as "any new control flow". |
| `15937--none--2` ⚑ | fastapi-15937 | none | — (0 hits) | `**_build_response_args(status_code, solved_result)` on both branches, plus generator priming and a wrapper iterator. | **yes** | judge error | Same: decided path present, extra priming. |
| `15937--veto--1` ⚑ | fastapi-15937 | veto | — (0 hits) | Wires status through `_build_response_args` and adds priming in a threadpool with `StopIteration` handling. | **yes** | judge error | Same. |
| `15937--warn+veto--0` ⚑ | fastapi-15937 | warn+veto | — (0 hits) | Wires `status_code` through `_build_response_args` and adds a `_StreamingResponseWithLateSync` subclass that peeks the first chunk to sync the status. | **yes** | judge error | Decided path present. This is the closest to a second status mechanism, and the subclass name would evade the rule (see (a)). |
| `15937--warn+veto--2` ⚑ | fastapi-15937 | warn+veto | — (0 hits) | Pre-drives the generator and builds `StreamingResponse` through `_build_response_args`. | **yes** | judge error | Same as `none--0`. |
| `75025--veto--1` | airflow-75025 | veto | `"state"`, `"start_date"` in `/private/tmp/verify_dag_order_by.py` | Verify script, **denied** (exact). Final diff removes `state`/`start_date` from the `SortParam` allow-list (the decided path). | no | rule noise | The script sends `order_by=state` to check the 400; the block was on a test client, not a fix. |
| `75025--warn+veto--0` | airflow-75025 | warn+veto | `getattr(DagRun, v.attr)` in `/private/tmp/verify_orderby.py` | Verify script, **denied** (exact). Final diff removes the two keys (the decided path). | no | rule noise | Script outside the repo. |

## (a) #15937: does the rule miss real repeats?

**Not in these runs. The judge was wrong on all five, but the rule has gaps an agent could slip through.**

- Root `fastapi-15937-1`: decided "apply the same `_build_response_args()` path
  to the SSE and JSONL branches … instead of introducing new logic." The rejected
  alternative is stored as the bare phrase "introducing new logic". The judge saw
  only that phrase. It then counted any new control flow as the rejected path,
  even when the status still came from `_build_response_args`. By the judge's own
  text, all five diffs route the status through `_build_response_args`. The extra
  generator priming lets a `Response` change made inside the generator take
  effect. It is new behaviour, not a parallel status calculation.
- The fault is in the root text, not the rule. The `rejected_alternative` is too
  thin for a blind reader.
- Rule probes (`rules/15937.yml`):

  | Shape | Matches |
  |---|---|
  | `StreamingResponse(..., media_type="text/event-stream", status_code=sc)` (hand-rolled) | 1 ✔ |
  | `StreamingResponse(..., media_type="text/event-stream", **_build_response_args(...))` | 0 ✔ |
  | `_StreamingResponseWithLateSync(..., status_code=sc)` (subclass) | 0 ✘ gap |
  | `StreamingResponse(..., media_type=SSE, status_code=sc)` (constant) | 0 ✘ gap |
  | `StreamingResponse(..., media_type="application/jsonl", **{"status_code": sc})` | 0 ✘ gap |

  The plain hand-rolled shape is caught. A subclass call, a media-type constant,
  or any `**` splat evades the rule. `warn+veto--0` used a subclass, so for that
  run the rule's silence is not evidence; the judge's description is.

## (b) #16062 warn+veto run 0: did a rejected path ship?

**No. This is rule noise.**

- The three hits are `@lru_cache(maxsize=1024)`. The base file
  (`255b912`, lines 140/170/200) has the same decorator text. The agent
  reorganised the file, so the text landed on added lines (203/245/289).
  `diff_label` scores line overlap, so it said `rejected_path`. The attempt
  replay compares match text, so it found nothing new (`attempted: false`), and
  the guard did not fire (0 denies). The two scorers disagree on moved code.
- The rule encodes the decision ("must be 4096"), not the rejected alternative
  ("an even larger bump"). It flags any other literal size, including the
  smaller 1024.
- The shipped design is an unbounded weak-reference cache with a 1024 LRU
  fallback. That is neither the decided 4096 nor a larger fixed bump. It is a
  different design, which belongs in "other", not "rejected path".

**The real miss on #16062 is `none--2`.** The judge says 8192 on all three
caches. A literal `@lru_cache(maxsize=8192)` matches the rule (probe: 1 match),
yet the run recorded 0 hits. So the size most likely came through a name, and
`maxsize=_SIZE` matches nothing (probe: 0). That run shipped the rejected path
unseen, in the `none` arm. I cannot confirm the exact text because the diff is
gone.

## Primary numbers per arm (excluding fastapi-16049), raw → audited

24 runs per arm. Rates use the bench's Wilson 95% intervals.

| Arm | Attempted | Blocked | Blocked on a real attempt | Rejected path shipped | Repeat rate (blocked or shipped, real only) |
|---|---|---|---|---|---|
| none | 3 → **0** | 0 → 0 | — | 0 → **1** (4% [1–20%]) | 0/24 → **1/24** (4% [1–20%]) |
| veto | 2 → **0** | 2 → **0** | 0 | 0 → 0 (0% [0–14%]) | 2/24 → **0/24** (0% [0–14%]) |
| warn+veto | 3 → **0** | 3 → **0** | 0 | 1 → **0** (0% [0–14%]) | 4/24 → **0/24** (0% [0–14%]) |

- Every attempt and every block in the primary set is rule noise: probes in
  `/private/tmp`, verify scripts, and one intermediate test snapshot.
- The only real repeat in the primary set is `16062--none--2`, which the rule
  missed. It is in the `none` arm, so the guard could not have blocked it anyway.
  Had it happened in a guarded arm, the rule would not have seen it.
- Judge vs. truth: the judge is wrong on 5 of 72 (all #15937) → 67/72
  (93% [85–97%]). The final-diff rule label is wrong on 2 of 72 (both #16062).
- airflow-75025 has 13 rule hits in the base test file (`test_dags.py`). Its
  final diffs score "other" even when they take the decided path, as both
  blocked runs here do. So "Correct" for that ticket is understated.

### Excluded ticket fastapi-16049 (3 runs per arm), audited

| Arm | Real attempts | Blocked on a real attempt | Rejected path shipped |
|---|---|---|---|
| none | 2/3 | — | 2/3 (both judge errors) |
| veto | 1/3 (`veto--1`) | 1/3, recovered | 0/3 |
| warn+veto | 0/3 | 0/1 (the one block was a probe) | 0/3 |

## Follow-ups for steps 2 and 3

1. Keep run artifacts: pass `--work` under `bench/` (git-ignored), or copy
   `diff.patch` and `export.json` beside the jsonl. Without them this audit had
   to rely on the judge's description.
2. #16062 rule: resolve `maxsize` through a module-level constant. Allow sizes
   ≤ 4096 and flag only sizes > 4096 or `None`, to match the rejected
   alternative.
3. Scorer: `diff_label` should count a hit only when its matched text is new,
   as the attempt replay already does, not when it overlaps an added line.
4. Root `fastapi-15937-1`: the judge needs the full rejected alternative: "new
   status-code logic for the SSE/JSONL branches instead of
   `_build_response_args()`".
5. Rule scope: most noise is writes outside the sandbox (`/private/tmp`). The
   guard and the attempt count could ignore paths outside the repo.
