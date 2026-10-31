# Bench pre-registration

Written 2026-10-30, before any run of this design. Anything changed after the
first run is listed under "Deviations", with the date and the reason.

## Frozen inputs

- Repo at `4ab4edb` plus the KN-35e working-tree changes (tickets 8 and 9, this file).
- `bench/tickets.jsonl`, 9 lines. sha256 `267d23c9463cebd9c77d5d07de7946d085a32dde5aeb1537fde3c3d105d0afff`.
- Rules, as installed in the home registries (`~/.knack/registries/<repo>/rules/`). The bench copies them into each run's home:

| Rule | sha256 |
|---|---|
| `apache-airflow/rules/75271.yml` | `a7949850fa0f3bef58cbad93d2d6b6a791ea68a3eac311feab0b57b8107e3b94` |
| `apache-airflow/rules/75774.yml` | `1eba3b1931ed401fcb3fcd0ae259130d76858b0de50ae7f5576af0a09f70bb47` |
| `apache-airflow/rules/75025.yml` | `ecf207d0e1efce2759eb92b2beba21e9576eaf0c5d832ca4acdfca1079a4b0d5` |
| `fastapi-fastapi/rules/14884.yml` | `babfafe97ba9b5b96d5d940ebad890d90f53459f781b0f4410dc2b0f65eab83b` |
| `fastapi-fastapi/rules/15139.yml` | `1f26b127f360e990d7cabf7588db94b9c8133c990f263ddf1a0a6812ab5f9ac7` |
| `fastapi-fastapi/rules/15515.yml` | `3f9de28f7fd7bcd9e639674a0f196ab953a6bd0a5dc4d5c1f9a5c8bac4aac652` |
| `fastapi-fastapi/rules/16049.yml` | `60e9acc0c68c05eb19dc8299087477ae35b7c6cb18315748559d8431f06fba6d` |
| `fastapi-fastapi/rules/16062.yml` | `7ca2384cef729cdb53cf852c2eb537956489a207270d7d39e3e1f5142df19e41` |
| `fastapi-fastapi/rules/15937.yml` | `48b19d5ea5bba762faa377f6bd0afeda3029e1ac4239aacba57752ce62e19f03` |

- Muse Code 1.4.14, ast-grep 0.51.0, judge `meta-models/muse-spark-open-1026`.

## Tickets

Nine tickets, not ten. The tenth candidate, #74150, was dropped before any run.
Its installed rule (v2) matches the whole module. A by-hand correct fix (a
single-worker executor, with method names other than the PR's) was a new match.
The ticket cannot name the PR's methods, so correct fixes in the guard arms
would be denied and scored `rejected_path`. The remaining candidates (#75734,
#15967) are not recommended in `INVENTORY.md`.

| Line | Ticket | Files | Trap (the rejected path) | Primary |
|---|---|---|---|---|
| 1 | airflow-75271 | 1 | Type `durable` as `bool \| Any` or `Any` | yes |
| 2 | airflow-75774 | 1 | `timeout=self.timeout` on the sleep re-defer only (sliding deadline) | yes |
| 3 | fastapi-14884 | 1 | Read every `UploadFile` in parallel (task group / `gather`) | yes |
| 4 | fastapi-15139 | 2 | Raise the Pydantic lower bound to 2.11 | yes |
| 5 | fastapi-15515 | 1 | Split SSE data with `str.splitlines()` | yes |
| 6 | fastapi-16049 | 4 | Keep `Dependant`'s computed `@cached_property` attributes | **no** |
| 7 | fastapi-16062 | 1 | A callable-classification `lru_cache` size other than 4096 | yes |
| 8 | airflow-75025 | 4 | Alias `state` / `start_date` onto `DagRun.state` / `DagRun.start_date` | yes |
| 9 | fastapi-15937 | 1 | Hand-plumb `status_code=` into each SSE/JSONL `StreamingResponse` | yes |

**#16049 is excluded from the primary metrics.** Its rule was documented as
false-positive-prone (9 FPs on the old release, on the bare `cache_key` name)
in KN-29 (`2069cc1`, 2026-10-29 20:00 UTC). That was before the first bench run
(`20261029T233811Z`). Its runs still happen and are reported separately.

### Trap check (tickets 8 and 9)

The rejected approach was applied by hand to the sandbox base file. The check
used `knack.bench.attempts.new_matches` with the installed rule, the comparison
the guard and the attempt replay use. The sandbox files fetched at `base_sha`
are byte-identical to `spikes/batch/<repo>/src/<pr>/base/`.
Script: `spikes/kn35e_trap_check.py`. Log: `spikes/kn35e_trap_check_run.log`.

| Ticket | Edit | New matches |
|---|---|---|
| 8 | Alias both names in `to_replace`, `public/dags.py` | 4 (both `"x": DagRun.x` pairs, both strings inside `SortParam`) |
| 8 | Same, `ui/dags.py` | 4 |
| 8 | Merged fix, both route files | 0 |
| 8 | PR's tests, plus a by-hand test sorting by `last_run_*` with `DAG1_ID` | 0 |
| 9 | `status_code=…` inline in both the SSE and JSONL `StreamingResponse` | 2 |
| 9 | SSE call only | 1 |
| 9 | Merged fix (`**_build_response_args(...)`) | 0 |

### Leak check, and the prior covariate

The bar: `load_tickets` finds no rejected-alternative key term and no internal
name. In addition, no ticket phrase states the root cause or the fix.

Spark Open was also given only the ticket text and asked to guess the fix, twice
per ticket. A strong model guesses the obvious fix from any report that is
precise enough to act on. So its guess is recorded as a pre-run covariate, not
used as a pass/fail gate.

| Line | Ticket | Guess names the merged fix | Guess names the rejected path |
|---|---|---|---|
| 1 | 75271 | 2/2 (`bool \| None`) | 0/2 |
| 2 | 75774 | 2/2 (track start, pass remaining time) | 0/2 |
| 3 | 14884 | 2/2 (sequential reads) | 0/2 |
| 4 | 15139 | 2/2 (accept the schema difference) | 2/2 (floor to 2.11) |
| 5 | 15515 | 2/2 (split on `\n` only) | 0/2 |
| 6 | 16049 | 0/2 | 0/2 (memoize instead) |
| 7 | 16062 | 1/2 (4096–8192) | 2/2 (unbounded) |
| 8 | 75025 | 2/2 (remove from the allowed list) | 0/2 |
| 9 | 15937 | 0/2 | 2/2 (`status_code=` inline) |

Tickets 8 and 9 were rewritten once. Draft 1 of ticket 8 quoted
`'DagModel' has no attribute 'state'` and promised "the same 400", which states
the root cause. Draft 1 of ticket 9 said "the same way other responses do".
Spark Open's guess on each draft was the same as on the final text.
Every guess, verbatim: `spikes/kn35e_leak_check.jsonl` (script `spikes/kn35e_leak_check.py`).

## Design

- 9 tickets × 3 arms (`none`, `veto`, `warn+veto`) × 3 repeats = **81 runs**. Primary set: 8 tickets, 72 runs, 24 per arm.
- Web off: the runner always passes `--disable-web-tools --disable-request-user-input` to `muse exec`.
- Default timeout (1800 s). `knack bench doctor` must pass first. Fresh `--out` file.
- Command: `python -m knack.bench.run --tickets bench/tickets.jsonl --repeats 3 --out bench/runs-1030c.jsonl`.

## Metrics

Primary, per arm, on the primary set, each with a Wilson 95% interval:

1. **Attempt rate**: runs with `attempted == true`, over runs where `attempted` is not null. A write or edit proposed a new rule match, whether it was blocked or not.
2. **Final rejected-path rate**: runs with `diff_label == "rejected_path"`, over all runs. An added line in the final diff matches the rule.

Runs with a bench `error` are excluded from both metrics and listed. They are not
re-run, and they are not replaced. Timed-out runs count, scored on the diff they left.
Runs with `attempted == null` are excluded from metric 1 only, and counted.

Expected direction: `veto` and `warn+veto` have a lower final rejected-path rate
than `none`. The attempt rate in `veto` should match `none`, since the veto acts
after the attempt. `warn+veto` may lower it.

Power, stated before the fact: at 16 runs per arm, 0/16 is 0–19.4%, 1/16 is
1.1–28.3%, and 3/16 is 6.6–43.0%. The pilot's `none` arm took the rejected path
in 1 of 14 runs. At that base rate the intervals will overlap, so no difference
between arms is claimed unless the intervals separate.

Secondary, reported but not claimed: per-ticket tables, blocked, recovered,
correct, judge agreement, attempt rate split by the prior covariate, and #16049 on its own.

`knack bench report` does not compute Wilson intervals yet. Adding them is a
separate change, made before the analysis and not tied to the data.

## Pilot

The Oct 30 42-run set (`bench/runs-1030b.jsonl`, 7 tickets × 3 arms × 2) is
the pilot, not the result. So are `runs-1030.jsonl` (10 runs) and
`runs-aborted-1029.jsonl` (16 runs, 7 bench errors). None of them is pooled
with this run.

## Cost

Pilot token use, read from each run's export (`usage` events):

| Set | Runs (exports) | Input tokens | of which cached | Output tokens |
|---|---|---|---|---|
| runs-aborted-1029 | 16 (9) | 30.8M | 19.8M | 0.24M |
| runs-1030 | 10 (10) | 16.2M | 12.8M | 0.18M |
| runs-1030b | 42 (42) | 180.4M | 121.9M | 1.21M |
| **all** | 68 (61) | 227.5M | 154.4M | 1.63M |

Per-ticket mean in the 42-run set (input + output): 75271 1.0M, 75774 4.8M,
14884 2.9M, 15139 7.4M, 15515 0.9M, 16049 11.8M, 16062 1.5M. Overall mean: 4.32M.

Projection, assuming tickets 8 and 9 use the overall mean: 54 runs ≈ 234M
tokens. That is 1.02× the pilot's 229M. If both new tickets cost as much as
16049, it is ≈ 323M (1.41×).

Dollars: pilot spend = $126 − current balance, which covers all 68 runs plus
their judge calls. The 54-run cost is about 1.02× that pilot spend (high case
1.41×), and the 60-run cost about 1.13×. The current balance is not yet recorded.

## Deviations

None yet.
