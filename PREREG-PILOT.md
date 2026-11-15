# Pilot pre-registration: KN-215a repeat rate

Written 2026-11-14, before any agent run of this design. Anything changed after the
hash below is listed under "Deviations", with the date and the reason.

## Frozen inputs

- `bench/pilot/candidates.jsonl` sha256 `391cb5c6513d3731b75014541cc80400cf839fc30255daeaff9e4d76334fff98`
- 18 tickets.

| # | Ticket | PR | Base | Files | Ticket sha256 (first 16) | Rule sha256 (first 16) | Accepted check sha256 (first 16) |
|---|---|---|---|---|---|---|---|
| 1 | `airflow-63355` | [apache/airflow#63355](https://github.com/apache/airflow/pull/63355) | `f6bd8b48d2` | 2 | `29559825609b8088` | `f6113e2328c37952` | `7d63bcf67e6e9c85` |
| 2 | `airflow-61281` | [apache/airflow#61281](https://github.com/apache/airflow/pull/61281) | `a7b79ca1cf` | 2 | `055678681db21b49` | `94bf338d7e6d0784` | `9bc66a9a70b38baa` |
| 3 | `airflow-61372` | [apache/airflow#61372](https://github.com/apache/airflow/pull/61372) | `43b51932f9` | 1 | `fa332382f4bf82ff` | `ff59184baa22c513` | `22c97cd0bfd67369` |
| 4 | `fastapi-13920` | [fastapi/fastapi#13920](https://github.com/fastapi/fastapi/pull/13920) | `0dd42b746e` | 1 | `35178deff054a8ef` | `ec4eac2a7013bc0a` | `18c84b278d6ee930` |
| 5 | `fastapi-15588` | [fastapi/fastapi#15588](https://github.com/fastapi/fastapi/pull/15588) | `cb83b83dcf` | 1 | `8b943471fc9c3335` | `ce4c4d6ab7522bf4` | `719bd8b829325fdd` |
| 6 | `fastapi-9425` | [fastapi/fastapi#9425](https://github.com/fastapi/fastapi/pull/9425) | `0bdc3ca373` | 1 | `3e273ee799649b22` | `282b58056b9bffbb` | `b8cf08071d343268` |
| 7 | `fastapi-13786` | [fastapi/fastapi#13786](https://github.com/fastapi/fastapi/pull/13786) | `e2354a0a06` | 4 | `933712d41e56667b` | `69ac7b5b91a94513` | `9cd3e91d5389b6c2` |
| 8 | `ha-160756` | [home-assistant/core#160756](https://github.com/home-assistant/core/pull/160756) | `ddfa6f83c3` | 1 | `e4b2adc099c91630` | `ee47afc600950c9a` | `006b2c26218f43d0` |
| 9 | `ha-167721` | [home-assistant/core#167721](https://github.com/home-assistant/core/pull/167721) | `fb90237ae3` | 1 | `017da288177f7c6e` | `edc67871b7c12641` | `a131d6027bf7a31b` |
| 10 | `ha-142296` | [home-assistant/core#142296](https://github.com/home-assistant/core/pull/142296) | `67c0af4c57` | 1 | `44ab5550f7005647` | `5209f9399e7ce910` | `6cd68831423b83c6` |
| 11 | `ha-144836` | [home-assistant/core#144836](https://github.com/home-assistant/core/pull/144836) | `906b3901fb` | 3 | `ab556c72a565bb24` | `a68730a0397a495a` | `b0a39fd2cee96c10` |
| 12 | `ha-139299` | [home-assistant/core#139299](https://github.com/home-assistant/core/pull/139299) | `fe396cdf4b` | 2 | `dff121f6a7522f53` | `e3539ccb12f79cae` | `f725bd57eccb4dbb` |
| 13 | `pydantic-12740` | [pydantic/pydantic#12740](https://github.com/pydantic/pydantic/pull/12740) | `c42224acb3` | 1 | `39de594b5a3d7d7d` | `16ed082a850f7469` | `849f35d279828aff` |
| 14 | `pydantic-11251` | [pydantic/pydantic#11251](https://github.com/pydantic/pydantic/pull/11251) | `db061c2c52` | 1 | `5c738bab0b1e2636` | `e26e0c5ce3cf9e56` | `68af5bf2601da8c6` |
| 15 | `pytest-14391` | [pytest-dev/pytest#14391](https://github.com/pytest-dev/pytest/pull/14391) | `a38b20d790` | 1 | `4b28f3c609cb39b2` | `a21db5d302f9553e` | `55be847432d44d63` |
| 16 | `pytest-14989` | [pytest-dev/pytest#14989](https://github.com/pytest-dev/pytest/pull/14989) | `a453d653f9` | 1 | `5cf76b7d6fdafb3b` | `a13fc95a128df085` | `af635f8e4611c03c` |
| 17 | `pytest-14540` | [pytest-dev/pytest#14540](https://github.com/pytest-dev/pytest/pull/14540) | `b8d5cb25a2` | 2 | `3ef41cf9b663c7c9` | `bbb0d9aabc5be46c` | `67cdcace360435a8` |
| 18 | `pytest-14670` | [pytest-dev/pytest#14670](https://github.com/pytest-dev/pytest/pull/14670) | `e84e063e7d` | 1 | `dc31904668254fca` | `b0abb47f98ea747b` | `ff0114a3e514b47d` |

Rules: `bench/pilot/rules/<id>.yml` (the rejected pattern) and `<id>.accepted.yml`
(the accepted-fix check), ast-grep 0.51.0. Code: `bench/pilot/{arm,score,run,proof}.py`.
Agent: Claude Code 2.1.325. Judge: `meta-models/muse-spark-open-1026`.

## Question

Do plain coding agents repeat a team's rejected decision when given only the
symptom? Audit E6: the unguarded arm took the rejected path 0/24 times on the
1030c tickets. Those tickets were not picked for naivety: in the prior covariate,
a model shown only the ticket guessed the rejected path in 6 of 18 tries. This
pilot picks decisions where the rejected path is the obvious fix, and asks only
whether agents take it. No Knack arm.

## Method

Backtracking from history (Greptile's benchmark method): start each sandbox at the
first parent of a merged PR, give the agent a symptom-only ticket, and score whether
its final diff re-enacts the approach a reviewer rejected in that PR's thread.

## Arm (one arm, no Knack)

- Agent: Claude Code `claude -p`, version 2.1.325, model **`claude-opus-5-5`** (fixed; the
  account's Claude Code default). Exact command, from `bench/pilot/arm.py`:

  ```
  claude -p --model claude-opus-5-5 --restricted --strict-mcp-config --disable-slash-commands \
    --disallowedTools WebFetch WebSearch --output-format json --no-session-persistence \
    --permission-mode acceptEdits --max-budget-usd 5.0
  ```

- Web off: `--disallowedTools WebFetch WebSearch`, and `--restricted` drops WebFetch too.
- No Knack: `--restricted` ignores user, project and local settings files, so no
  hooks (Knack or other) and no user plugins load. `--strict-mcp-config` loads no
  MCP servers. The env passed to the agent drops `GITHUB_TOKEN`, `BASETEN_API_KEY`,
  `MODEL_API_KEY` and every `KNACK*` variable.
- No CLAUDE.md: the sandbox holds only the PR's files at base; there is no
  `~/.claude/CLAUDE.md`. Auto-memory is keyed by sandbox path, which is new each run.
- Deviation from "plain", stated up front: `--restricted` also removes Bash. Without it,
  a headless run with edits auto-accepted could run arbitrary commands on the
  operator's machine. The sandbox holds only the touched files, so tests could not run
  anyway. Tools seen at init (smoke check, Haiku, 2026-11-14): Task, Edit, Glob, Grep,
  NotebookEdit, Read, Write and harness tools; no Bash, WebFetch, WebSearch or MCP.
- Prompt: the ticket text verbatim, a blank line, then
  `Fix this in the code in the current directory.` Nothing else.
- Sandbox: a fresh git repo holding only `files` at `base_sha`, one commit
  ("Initial import", identity Developer), under `/tmp/knack-pilot-work`, outside
  the Knack repo. The files come from `bench/pilot/fixtures/<id>/base/`, the exact
  tree each rule was proven on (`FixtureBase`), so runs need no network. File tools
  are confined to the sandbox by `--restricted`; the agent cannot see the rules,
  fixtures or this file.
- Limits: 1800 s wall clock, $5.00 budget per run (`--max-budget-usd`).

## Scoring

Per run:

1. **Rule hit**: the candidate's rejected-pattern rule (`bench/pilot/rules/<id>.yml`,
   ast-grep 0.51.0) has at least one match in the final tree that the base did not
   have. The final tree is every changed or new `.py` file. The comparison is by
   matched text, the same `new_matches` the guard and the 1030c bench use.
2. **Blind judge**: Spark Open (`meta-models/muse-spark-open-1026`, a non-Anthropic
   model) sees the ticket, the rejected approach in one sentence, and the final diff.
   It never sees the rule or the rule's verdict. Prompt: `knack.bench.blind.PROMPT`,
   unchanged. An empty diff is "no" without asking.
3. **Repeat** = rule hit AND judge says yes. Disagreements are listed by hand, not
   re-labelled.

## Design and threshold

- 18 tickets × 3 runs = **54 runs**. One arm. Sequential.
- **Primary metric**: repeat rate = repeats / scored runs, pooled over all tickets,
  with a Wilson 95% interval.
- **Decision rule, fixed now**: GO (build on repeat-prevention) if the pooled point
  estimate is **≥ 30%** and at least **10 tickets** have at least one scored run.
  Otherwise **PIVOT to the audit**. Coded in `bench/pilot/score.py::pilot_verdict`.
- Reported, not gating: per-ticket repeats (x/3), the number of tickets with at least
  one repeat, rule-hit rate alone, judge-alone rate, rule/judge disagreements, cost.
- GO at 54 runs needs **≥ 17 repeats** (17/54 = 31.5%; 16/54 = 29.6% is PIVOT).
- Power, stated before the fact (Wilson 95%, 54 runs): 0/54 is 0–6.6%; 5/54 is
  4.0–19.9%; 17/54 is 20.7–44.7%; 27/54 is 37.1–62.9%. The pilot separates "rare"
  from "common", nothing finer. If fewer than 54 runs are scored (bench errors), the
  same rule applies to the scored runs.

## Exclusions

- A run with a bench `error` (sandbox or judge failure, unreadable agent output) is
  excluded from the metric and listed. It is not re-run or replaced.
- A run that hits the timeout or budget cap is scored on the diff it left.
- A judge `null` (no readable answer) counts as not a repeat, and is listed.
- No ticket text, rule or candidate changes after this file's hash. Any change is a
  dated deviation.
- The dry run (one ticket, one run) is a plumbing check. It is not pooled with the
  results and its ticket is not edited afterwards.

## Candidates

Mined 2026-11-14 from merged PRs, 2025-01 to 2026-11, in five repos: apache/airflow and
fastapi/fastapi (as asked) plus three new ones, home-assistant/core, pydantic/pydantic
and pytest-dev/pytest, picked because their reviewers often reject approaches in PR
threads. Recorded triage counts: airflow 113 small merged PRs (316 flagged), home-assistant 201; the other three miners did not record a count (UNKNOWN). 21 candidates were found. Already-used
decisions (the 1030c set) are excluded.

Inclusion bar: (1) merged; (2) a reviewer rejected an approach in the thread (quote in
`candidates.jsonl`); (3) the rejected approach is the naive fix. The strongest evidence
of naivety, and the evidence for 16 of 18, is that the PR author's own first commit did
it. The other two are a reporter's proposal (pytest-14391, also the author's first commit)
and competing PRs (fastapi-15588, fastapi-13786); (4) it can be expressed as an ast-grep
pattern in `.py`; (5) the fix touches few files; (6) a symptom-only ticket can be written.

Dropped before freezing: airflow#63518 (the rejected path is a `pyproject.toml`
dependency, invisible to a `.py` rule); pytest#15202 (a feature request, with no symptom
to report); airflow#70740 (lint-driven, with no runtime symptom, so the ticket would have
to hint at the fix).

| Ticket | Rejected path (what a repeat looks like) | Why it is naive | Flag |
|---|---|---|---|
| airflow-63355 | Catch the 409 `invalid_state` error around `SUPERVISOR_COMMS.send` in the task runner and ignore it | The traceback points at the runner; the author's first commit did it | |
| airflow-61281 | Swap the event loop (`set_event_loop_policy` / `uvloop.install` / `loop=`) when PYTHONASYNCIODEBUG is set | Textbook fix for "uvloop crashes in debug mode"; the author's first commits; a maintainer showed it still segfaults | |
| airflow-61372 | Fetch each deadline's alert one at a time inside the loop | Straightforward ORM code; the author's first commit | weak: rejected for performance; the result is the same |
| fastapi-13920 | Hand-rolled `isinstance(x, TypeAliasType)` unwrap | The first thing anyone writes; the author's commit (predecessor PR #11140) | |
| fastapi-15588 | Strip CR/LF from SSE `event`/`id` with `.replace` | Classic injection first fix; competing PR #15187 | weak: base already has the validator pattern the accepted fix extends |
| fastapi-9425 | Compare the annotation to the string `"None"` | Obvious one-liner under postponed annotations; the author's commit | rejection is a maintainer rewrite, not a review comment |
| fastapi-13786 | Inline `raise HTTPException(401…)` in each security `__call__` | One-line swap; competing PR #13326 was rejected | weak: same runtime response, differs only in structure; 4 files |
| ha-160756 | Sleep-and-retry loop inside the coordinator update | Textbook transient-error retry; the author's first commit | |
| ha-167721 | `_LOGGER.*` before `raise BackupAgentError` (log-and-raise) | First move for "the error is not visible"; the author's first commit | |
| ha-142296 | `set_alpn_protocols` on the shared cached SSL context | Mutate what you have; the author's first commit | |
| ha-144836 | Create a task / force a state refresh after each action | Obvious UI catch-up; the author's first commit | |
| ha-139299 | `loop.run_in_executor` / `asyncio.to_thread` for blocking construction | Generic asyncio answer; the author's first commit | HA-savvy agents may know `async_add_executor_job` |
| pydantic-12740 | Inspect `ModuleNotFoundError.name` and keep the masking re-raise | The obvious special case; the author's first commits | |
| pydantic-11251 | Assign `__doc__` onto the wrapper by hand | The shortest fix for a lost docstring; the author's first commit | the ticket pulls toward it by nature |
| pytest-14391 | `raise AssertionError(...) from exc_val` | The reporter proposed it; the author's first commit | |
| pytest-14989 | Treat a pyc with a mismatched `co_filename` as stale (`return None`) | Throw away the stale cache; the author's first commit | |
| pytest-14540 | Keep the dedup set, keyed by a tuple | Widen the key; the author's first (force-pushed) head | |
| pytest-14670 | Dedup by `id(report)` instead of nodeid | A key unique per object; the author's first commit | |

Per ticket, the full record (ticket text verbatim, the reviewer quote and URL, accepted
fix, leak terms) is the line in `bench/pilot/candidates.jsonl`. Each rejected tree is the
base with the author's (or competing PR's) real naive hunk applied, in
`bench/pilot/fixtures/<id>/rejected/`. pytest-14670 was re-applied by hand because base
had moved.

### Proof (run 2026-11-14, before any agent run)

`uv run python -m bench.pilot.proof` exits 0. Every ticket prints `PROVEN`: the
rejected rule adds ≥1 match when the rejected hunk is applied to base (base-flag), adds
0 at the merged head (head-allow), and the accepted-fix check adds ≥1 at head. Each
rule was also checked against one hand-written rephrasing of the rejected approach,
and every rephrasing was caught. Regression: `tests/bench/pilot/test_pilot_frozen_set.py`.

### Leak check

Each ticket has 4–8 `leak_terms` (identifiers and words of either approach), and none
appears in its ticket (`leaked_terms`, enforced by test). Edited by hand for neutrality
before hashing: ha-142296 (cut "without changing how any other integration makes its TLS
connections"), ha-167721 ("includes the actual B2 error text" became "it is possible to see
what B2 actually returned", so both logging and the message fix satisfy it), ha-160756
(cut the accepted default "about 10 seconds"), airflow-61281 (cut "nothing in the logs
explaining why"). No model was asked to guess fixes from these tickets.

## Cost

- Agent: measured per run from `claude -p` JSON (`total_cost_usd`, tokens). Hard cap
  $5.00 per run (`--max-budget-usd`), so the agent's worst case is 54 × $5 = **$270**.
- Expected per-run cost: **UNKNOWN** at hashing time. It is measured by the dry run
  below and recorded there.
- Judge (Spark Open via Baseten): one call per run with a non-empty diff, cost
  **UNKNOWN** (not reported by the client). The 1030c judge spend was not separated
  from that pilot's total either.
- Wall time: **UNKNOWN** until the dry run.

## Pre-launch dry run

One ticket, one run, end to end, after this file was hashed. It checks the plumbing
only. Its record goes to `bench/pilot/runs-dryrun.jsonl`, never to the results file,
and is not pooled. Result: see the section appended below, dated.

## Launch (Monday; not run here)

```
export BASETEN_API_KEY=$(cat ~/.knack/baseten_api_key)
uv run python -m bench.pilot.run --repeats 3 --out bench/pilot/runs-pilot.jsonl
```

The runner refuses to start (exit 2) unless `bench/pilot/candidates.jsonl` matches the
sha256 above.

## Dry run result (2026-11-15 04:16 UTC)

Ticket `pytest-14391`, run 0, `claude-opus-5-5`. Record: `bench/pilot/runs-dryrun.jsonl`.
Diff: `bench/pilot/artifacts/pytest-14391.run0.diff`. Not pooled.

| Step | Result |
|---|---|
| Hash gate | passed |
| Sandbox from fixture base | 1 file, 1 commit |
| Agent | exit ok, 12 turns, 28.8 s, **$0.1446**, 2,880 output tokens, 120,151 cache-read tokens, 7,866 cache-write tokens |
| Rule | **2 new hits**: `raise AssertionError(self._fail_reason) from exc_val` in `RaisesExc.__exit__`, and the same chaining (`raise Failed(...) from exc_val`) added to `RaisesGroup.__exit__` |
| Blind judge | **failed**: HTTP 400, "Model version wpgy40e is deactivated". Recorded as `blind: null`, so the run is not a repeat, as the exclusion rules say. No crash. |

The judge is the only step that did not work. Whether the judge would have said yes is
UNKNOWN; this run is not counted as a repeat anywhere.

Cost projection: if every run costs what this one did, 54 × $0.1446 ≈ **$7.81**. This
ticket is one of the smallest (one file). The 4-file and ~2,000-line Airflow sandboxes
will cost more, by an UNKNOWN factor. Bounds: at least about $8; at most $270
(the cap). Judge cost is still UNKNOWN.

## Deviations

- 2026-11-15, after hashing, plumbing only: `bench/pilot/run.py` gained `judge_ready`.
  The runner now exits 3 before any agent run if the blind judge does not answer a
  one-line probe, because a dead judge would score every run "not a repeat". Tickets,
  rules, scoring and threshold are unchanged, and the candidates hash still matches.
- **Open, decided before launch:** the Spark Open deployment on Baseten is deactivated.
  Either it is reactivated (no deviation), or the judge is replaced. A replacement is a
  dated deviation that names the new model, and it must be a different model from the
  agent.
