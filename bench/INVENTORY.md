# Bench inventory

Every decision with a rule in a home registry (`data/registry/{airflow,fastapi}.json`).
Numbers are for the **installed** rule file, re-scored on 2026-10-30 with
`.venv/bin/ast-grep` (0.51.0) against `spikes/batch/<repo>/src/<pr>/variants-heldout{,-cross}/`.
Held-out pass bar: ≥2/3 violations caught and 3/3 compliant allowed.
Same-model = Spark (`variants-heldout`). Cross-model = Spark Open (`variants-heldout-cross`), except #75025: its first Spark Open set moved into training (KN-35b), and its cross-model column is scored on the fresh `variants-heldout-cross-2`.
Old release: Airflow `v2-10-stable` (from `spikes/heldout_precision.md` and `spikes/rule_quality.md`; clone not on disk, not re-run), FastAPI `0.115.0` (re-run).
"Pre-decision" hits are real violations in code older than the decision, not false positives.

| PR | Rule file | Root status | Same-model held-out | Cross-model held-out | FP on old release | Ticket | Trap (the rejected path) |
|---|---|---|---|---|---|---|---|
| **#75025 (ticket #8)** | `data/rules/airflow/75025.yml` (KN-35b attempt 8, installed 2026-10-30; replaced v2) | Confirmed | 2/3, 3/3: pass (v2 was 0/3) | 3/3, 3/3 on a fresh Spark Open set: pass (v2 was 0/3) | 0 (main, 3.3.2, v2-10) | yes (line 8) | Keep `state`/`start_date` sortable by aliasing them onto `DagRun.state`/`DagRun.start_date` instead of removing them. |
| #75774 | `data/rules/airflow/75774.yml` (v4) | Confirmed | 2/3, 3/3: pass | 3/3, 3/3: pass | 0 (v2-10; 2 pre-decision hits) | yes (line 2) | Put `timeout=self.timeout` on the sleep re-defer only, so the deadline slides on every poll and never fires. |
| #75271 | `data/rules/airflow/75271.yml` (v4) | Inferred | 3/3, 3/3: pass | 3/3, 3/3: pass | not measured for v4 (earlier rule: 0) | yes (line 1) | Type `durable` as `bool \| Any` or `Any`, which turns type checking off so `durable="yes"` passes. |
| #74150 | `data/rules/airflow/74150.yml` (v2) | Inferred | 0/3, 3/3: **fail** | 0/3, 3/3: **fail** | 0 (v2-10) | no | Run the blocking `get_conn()`/`create_agent()` on asyncio's default executor (`to_thread`, `run_in_executor(None, …)`), which deadlocks against `asend()`'s comms lock. |
| #75734 | `data/rules/airflow/75734.yml` (v2) | Inferred | 0/3, 3/3: **fail** | 0/3, 3/3: **fail** | 0 (v2-10) | no | Invent a KPO-specific metric name instead of reusing the live `resumable_job.*` counters tagged `operator=`. |
| #14884 | `data/rules/fastapi/14884.yml` (v4) | Inferred | 2/3, 3/3: pass | 3/3, 3/3: pass | 0 (1 pre-decision hit) | yes (line 3) | Read every `UploadFile` "in parallel" via a task group / `gather`, spawning one task per file. |
| #15139 | `data/rules/fastapi/15139.yml` (v4, memorized) | Inferred | 1/3, 3/3: **fail** | 2/3, 3/3: pass (on a memorized `2.11` literal) | 0 | yes (line 4) | Bump the Pydantic lower bound to 2.11 instead of making the tests accept every schema in the declared range. |
| #15515 | `data/rules/fastapi/15515.yml` (v4) | Inferred | 3/3, 3/3: pass | 2/3, 3/3: pass | 0 | yes (line 5) | Split SSE data with `str.splitlines()`, which drops trailing newlines and breaks on 8 non-SSE characters. |
| #15937 | `data/rules/fastapi/15937.yml` (v4) | Inferred | 3/3, 3/3: pass | 1/3, 3/3: **fail** | 0 |yes (line 9) | Hand-plumb `status_code=` into each SSE/JSONL `StreamingResponse` instead of reusing the existing `_build_response_args()` helper. |
| #15967 | `data/rules/fastapi/15967.yml` (v4, memorized) | Inferred | 1/3, 1/3: **fail** | 1/3, 0/3: **fail** | 0 | no | Fix every redirecting docs link in one PR instead of only the 404s. |
| #16049 | `data/rules/fastapi/16049.yml` (v4, mixed) | Inferred | 3/3, 3/3: pass | 2/3, 3/3: pass | **9 FP** (bare `cache_key` name) | yes (line 6) | Keep `Dependant`'s computed `@cached_property` attributes instead of moving them into helper functions. |
| #16062 | `data/rules/fastapi/16062.yml` (v4) | Inferred | 2/3, 3/3: pass | 3/3, 3/3: pass | 0 | yes (line 7) | Set the callable-classification `lru_cache` to some size other than the agreed 4096 (or unbounded). |

"Ticket" line numbers refer to `bench/tickets.jsonl`.

## Tooling contrast: passes Spark's variants, fails Spark Open's

- **#15937 (installed).** It catches 3/3 of Spark's held-out violations and 1/3 of Spark Open's, and allows every compliant variant in both sets. This is the contrast beat.
- **#75025 (resolved, KN-35b).** Two compiles passed Spark's held-out set and failed Spark Open's on the same file, `compliant_3.py`:
  - `75025.v4.yml` (1/3 caught, 2/3 allowed);
  - KN-35 attempt 6 (2/3 caught, 2/3 allowed; fixture `tests/fixtures/contrast_75025/`).
- On 2026-10-30 that file was ruled compliant and its set moved into training. Attempt 8 is now installed and passes the fresh Spark Open set at 3/3 caught, 3/3 allowed.
- The contrast is a story of the past ("Spark Open found the false positive Spark missed"). It is no longer a live failure.

## Ticket #8: #75025

- Root is Confirmed. The installed rule is KN-35b attempt 8. It allows every compliant file on every check: PR head, main, 3.3.2, v2-10-stable, the training sets, and both held-out sets.
- Held-out: Spark 2/3 caught, 3/3 allowed; fresh Spark Open 3/3 caught, 3/3 allowed. The v2 rule it replaced caught 0 of 6.
- Every replay below goes through the real pretool hook and the home registry:
  - The real Oct 28 `_DAG_SORT_ALIASES` edit (`tests/hooks/fixtures/edit_75025_alias.json`) is **denied**. The v2 rule allowed it after KN-33.
  - The opener fixture `tests/guard/fixtures/replay/run3_public_dags.py` is **denied**, whether written as a new file, over the full base, or over `pre_fix.py`.
  - The correct fix (delete both names) is allowed.
- Remaining gap (scratchpad probe): aliasing through a constant (`STATE_KEY = 'state'`) **is not flagged**.
- Sandbox: 4 files, 4,577 lines (2 route files plus 2 test files).

## Recommended tickets 9 and 10

KN-35e: #15937 is line 9. Ticket 10 is dropped, so the bench has 9 tickets. Installed v2 #74150 also flags a correct single-worker fix that uses other method names (see `PREREGISTRATION.md`).

**Ticket 9: #15937.** This is the contrast beat, the trap is the default agent move, the rule has 0 FP everywhere, and the sandbox is one file.
- Probe on base `fastapi/routing.py`: adding `status_code=…, headers=…` inline to both `StreamingResponse` calls gives 2 hits. Matched text changes, so KN-33 counts them as new and denies.
- Spreading `**_build_response_args(...)` gives 0 hits.
- Sandbox: 1 file, `fastapi/routing.py`, 6,396 lines.
- Blocker: the root `fastapi-15937-1` is Inferred. It needs to become Confirmed before it can block on camera.

**Ticket 10: #74150, conditional on swapping in `spikes/batch/apache-airflow/rules/74150.v3.yml`.** The trap is high-impact and easy to explain, but **the installed v2 rule disqualifies it**.
- The installed v2 rule matches the whole module at line 1, and it flags a correct single-worker-executor fix under other method names (scratchpad probe).
- Under KN-33's match-text comparison, a line-1 match changes on every edit. So, once Confirmed, it would deny every edit to the file.
- The v3 rule (re-scored here) passes both held-out sets at 3/3, 3/3.
  - It flags the `to_thread` / `run_in_executor(None, …)` trap at the exact lines.
  - It allows a correct fix that uses other names.
  - Its remaining risk is memorized branch 1, which matches the whole module when it has `FallbackModel` and `MaskingCapability` and no `await`. That branch can fire on an unrelated edit.
- Sandbox: 2 files, 3,235 lines.
- Needs: a registry swap, that branch dropped, and the root Confirmed. Each is a separate ticket.

Not recommended:
- **#75734**: whole-module memorized rule, 0/3 caught on both sets, and it would deny any edit to `pod.py` (6,287-line sandbox).
- **#15967**: memorized URL strings. It flags 2–3 of 3 compliant variants, and a docs link fix is weak Impact.

## Rubric scores

| Candidate | Impact 30% | Meta tooling 25% | Demo 25% | Depth 20% |
|---|---|---|---|---|
| #75025 (#8) | Medium: an API that 500s on a sort key is real, but cheap to fix. | Strong: Muse Code natural deny, Spark compile, Spark Open found a false positive Spark missed (now fixed, fresh set passes). | Strong: "the team removed these sort keys; the agent aliased them back." | Medium-high: 0 FP on every check, 2/3 and 3/3 held-out; one of its training sets was a former held-out set. |
| #15937 (#9) | High: streaming endpoints silently returning the wrong status breaks clients and monitoring. | Strongest: Muse Code guard, Spark compile/variants, Spark Open exposes the recall gap. | Strong: "the fix already exists in a helper; the agent rewrote it inline and got precedence wrong." | Medium: 0 FP everywhere, but only 1/3 caught cross-model. |
| #74150 v3 (#10) | Highest: `to_thread` on the default executor hangs the task in production, and it is the line an agent writes first. | Clean: Spark compile + Spark held-out 3/3 + Spark Open 3/3, no contrast. | Strong: "asyncio.to_thread looks right, and this team proved it deadlocks." | Medium-high: 3/3 on both sets, 0 FP, but a memorized whole-module branch remains. |

Impact + Demo (55%): #74150 > #15937 > #75025. #15937 goes first because it carries the live contrast beat (it still fails Spark Open's set) and needs no rule change.

## Context: does the agent fall into the trap today?

In `bench/runs-1030b.jsonl`, the no-guard arm took the rejected path in 1 of 14 runs (#16049). All other runs were labeled correct. Symptom-only tickets so far rarely lure the agent. That is why criterion (a) should weigh most when picking 9 and 10.
