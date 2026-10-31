# Pilot audit (KN-38)

Read-only audit of the Oct 30 42-run pilot, `bench/runs-1030b.jsonl`
(7 tickets × 3 arms × 2, 14 runs per arm). `bench/runs-1030-attempted.jsonl` is
not this set. It is the earlier 10-run set (`runs-1030.jsonl`), reclassified.
The 42-run file already carries `attempted`, so it is audited directly.

Selection: every run with `attempted == true`, a deny, or `agree == false`.
That is 6 of 42 runs. No run has `attempted == null` or a bench `error`.

Labels:
- **real attempt**: the edit takes the rejected path.
- **rule noise**: the rule matched something that is not the rejected path.
- **judge error**: the blind judge's yes/no is wrong.

## Runs

| Run | Ticket | Arm | Matched text | Agent's edit | Judge | Label | Reasoning |
|---|---|---|---|---|---|---|---|
| `75774--none--1` | airflow-75774 | none | Two `self.defer(...)` calls, without `kwargs=`: the `MSGraphTrigger` defer in `execute`, and `TimeDeltaTrigger(self.retry_delay), timeout=timedelta(seconds=remaining)` | Intermediate edits rewrote the base's existing defers to use `remaining = timeout - (now - ti.start_date)`. The final diff carries `kwargs={"sensor_started_at": ...}` with the remaining timeout (merged-fix shape, 0 rule hits). | no | rule noise | It re-edited a defer that already matched in base, on the way to the fix, with a fixed `ti.start_date` deadline rather than the sliding one; the rule flags any defer without `kwargs=`. |
| `16049--none--0` ⚑ | fastapi-16049 | none | `flat_sub._is_security_scheme` (added line, `utils.py:187`), plus 21 reads such as `d.cache_key` / `dep.oauth_scopes` in `/private/tmp/functest_228d.py` | `@cached_property` → `@property` on all of `Dependant`'s computed attributes, which stay on the class and are still read. `get_flat_dependant` keeps only security sub-dependants. It adds `_CallIdentity` + 4096-entry `lru_cache` helpers. | no | real attempt (and judge error) | The decision is to "stop using those attributes, move [them] out of the class"; the agent kept them on `Dependant` and still reads them, so the one added-line hit is on point and the judge's "no" is wrong. The 21 `/tmp` reads are noise. |
| `16049--none--1` ⚑ | fastapi-16049 | none | `x.oauth_scopes`, `x.cache_key`, `x._uses_scopes`, … (7 reads) in `/tmp/measure_node.py` | A memory-measurement script outside the sandbox. Final diff deletes the `@cached_property` attributes for module-level functions (0 rule hits). | no | rule noise | Bare attribute reads in a throwaway probe outside the repo; the final fix is the decided one. |
| `16062--none--0` | fastapi-16062 | none | — (not attempted) | `@lru_cache(maxsize=1024)` → `maxsize=4096` on the three `*_callable_cached` functions | **yes** ("precisely a larger LRU bump") | judge error | 4096 is the agreed size; the rejected alternative is an even larger bump than that, and the rule correctly found nothing. |
| `16049--veto--1` ⚑ | fastapi-16049 | veto | `d.is_gen_callable`, `d.is_async_gen_callable`, `d.computed_scope`, `d.cache_key`, `d.is_coroutine_callable` in `/tmp/reprodir/pinpoint.py` | A diagnostic script ("Pinpoint which cached_property access bloats `Dependant.__dict__`"). **Denied** (1 deny, exact). The run timed out at 1800 s with an empty diff. | no | rule noise | A blocked read-only probe outside the sandbox, not a fix; the deny cost the run its diagnostic, and it never edited the repo. |
| `16049--warn+veto--1` ⚑ | fastapi-16049 | warn+veto | 18 reads such as `d.cache_key`, `dependant.oauth_scopes`, `flat_dependant._security_dependencies` in `/tmp/work_mem/equiv.py` and `/tmp/work_mem/probe_hook_a.py` | Two scripts (a behaviour snapshot and a hook probe), both **denied** (2 denies, exact). Timed out at 1800 s. The final diff deletes the computed attributes for free functions (0 rule hits). | no | rule noise | Both denies hit scratch probes in `/tmp`; the landed fix is the decided one. |

⚑ = #16049. That is 4 of the 6 rows, every deny in the pilot, and the only
real attempt. Its rule was documented as false-positive-prone on Oct 29, and
these runs show the same bare-name class of match. In 3 of them the match is in
a script outside the sandbox.

Also seen in `16049--none--0`: the agent wrote `_CallIdentity` and
`_CALLABLE_CLASSIFICATION_CACHE_SIZE = 4096`, the same names as upstream code
that merged after this ticket's base. That looks like training-data recall, not
a fix derived from the ticket.

## Totals per arm

Attempt rate and final rejected-path rate. "Raw" is the pilot as recorded;
"audited" removes rule noise. Blocks are counted per run.

| Arm | Runs | Attempted, raw | Attempted, audited | Rejected path (diff), raw | Rejected path, audited | Blocked, raw | Blocked on a real attempt |
|---|---|---|---|---|---|---|---|
| none | 14 | 3 | 1 | 1 | 1 | 0 | 0 |
| veto | 14 | 1 | 0 | 0 | 0 | 1 | 0 |
| warn+veto | 14 | 1 | 0 | 0 | 0 | 1 | 0 |

Without #16049 (12 runs per arm): 0 attempts, 0 rejected paths and 0 blocks in
every arm, raw and audited. The only #75774 attempt is noise.

Judge: it disagreed with the rule label on 2 runs. It was wrong both times:
`16062--none--0` (false "yes") and `16049--none--0` (false "no"). After the
audit, the judge's labels match in 40 of 42 runs.
