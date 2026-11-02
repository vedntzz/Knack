# KN-99 loop audit

Each autonomous loop was run once on `main` at `8853548`, on 2026-11-01 (UTC 2026-11-02 04:23–04:44). During the audit `main` moved to `822fa47`. That commit only adds `confirmed_by` and `rule_sha` to `data/roots/airflow/75025.json`, and the pinned sha (`ecf207d0…`) is the one the rule file already has, so no path below behaves differently.

Two kinds of run:

- **Fakes:** `scripts/e2e.sh`, copied unchanged to a scratch dir except that every step prints its output and the temp dir is kept. GitHub, Spark and Spark Open are the `scripts/e2e_fakes.py` fakes, and every other line is the real CLI. 26/26 steps PASS. The "both models escalate" branch is not in e2e, so it was run once more. That run used the same fakes, except that Spark Open escalates every argue.
- **Live:** run once each, with no retries, in a temp `HOME`/`KNACK_HOME` and a sandbox clone whose origin is apache/airflow. The real `~/.knack` was not touched. Keys present: `GITHUB_TOKEN`, `MODEL_API_KEY`, `BASETEN_API_KEY`. The registry is a temp copy of the committed `data/`.

Outputs are verbatim but trimmed. Temp-dir prefixes are shortened to `$W`, and `…` marks a cut. "Models" lists only what a trace file records: `rulings.jsonl` `model`, `self_checks.jsonl` `answers[].model`, a root's `models`, the miss fresh set's `authors.json`, and the pipeline's own log lines.

## Summary

| Loop | Fakes | Live (once) | Receipt / case ids | Models, per traces |
|---|---|---|---|---|
| [watch: merge → rule](#1-watch-merge--rule) | WORKS | **BROKEN** | live: root `airflow-75025-1` written Inferred; 8 self-checks, no case | live: `muse-spark-1.3` (extract, compile, variants, held-out); `meta-models/muse-spark-open-1026` (self-check only) |
| [guard: deny](#2-guard-deny) | WORKS | WORKS | fakes: deny `c5dd0385edb4`, allow `bc7f792353ef`, guard-error `8ed4be1e64d3`; live: deny `19f0c5ce1aed` | none: no model in the verdict path |
| [warn](#3-warn) | WORKS | WORKS | `warns.jsonl` line (warns carry no hash) | none |
| [argue → hold](#4-argue--hold) | WORKS | **BROKEN** | on deny `c5dd0385edb4` / `19f0c5ce1aed` | fakes: the trace says `muse-spark-1.3`, but the fake answered (see ticket); live: `muse-spark-1.3` |
| [argue → escalate](#5-argue--escalate) | WORKS | WORKS | live: provisional `19f0c5ce1aed….json` | live: `muse-spark-1.3`, `meta-models/muse-spark-open-1026` |
| [resolve: learn receipt](#6-resolve-learn-receipt) | WORKS | WORKS | fakes: allow `18fd1512b7df`, retire `e2d8ef0730b4`, held-then-allow `72c9fe42347a`; live: `0c576d656a5a` → `must-pass-d5c2aa0958d7` | none |
| [miss: recompile → prove → install](#7-miss-loop-recompile--prove--install) | WORKS | WORKS | fakes: cases `c49124503cd1`, `1f492766a409` (kept), `e0d0584e3fbf`, `883dfa0849a0`; live: case `4607a716613c` | fakes: `fake-spark`, `fake-spark-open`; live: `muse-spark-1.3` (recompile), `meta-models/muse-spark-open-1026` (fresh set) |

UNTESTED: watch's `PostToolBatch` trigger, for a merge made inside a Muse Code session. Neither run fired it.

## Proposed fix tickets

- **watch registry file (BROKEN):** `install` writes `run.out / "registry.json"` (`knack/pipeline/stages.py:364`), so `knack watch --registry data/registry/airflow.json` installs into a new sibling `registry.json` and the watched registry never gets the rule. Write back to the registry path the run was given.
- **watch has no cross-model adversary:** `run_merged` (`knack/pipeline/merged.py:20`) never passes `adversary`. So on every merge Spark writes and grades its own held-out set ("no cross-model adversary"), even with `BASETEN_API_KEY` set, contrary to README "Spark never sees those variants". Pass `optional_partner()` as the adversary in watch.
- **argue live escalates a restated rejected alternative (BROKEN):** Spark escalated "Let me alias state and start_date onto DagRun.state…", which is the root's rejected alternative nearly word for word. Record this prompt and reply as a live regression fixture, and tighten the ruling prompt so a restated rejected alternative holds on its verbatim quote.
- **argue trace names a model that did not answer:** `rulings.jsonl` and the argue self-check record the constant `SPARK_MODEL` (`knack/dispute/argue.py:11`, `second.py:83`) and not the client that answered. Under the fakes this logged `muse-spark-1.3` for a fake. Record the answering client's `.model`.
- **learn receipt sorts before its block:** `resolve` stamps whole seconds (`knack/roots/resolve.py:99`) while the guard stamps microseconds, so `knack day` listed the learn `04:26:13+00:00` before the block `04:26:13.551487+00:00` it resolved. Stamp resolve with the same precision.

## 1. watch: merge → rule

**Fakes: WORKS.** `knack watch` installed both hooks. The real `git merge` fired the installed `post-merge` hook, which printed `knack watch: GITHUB_TOKEN is not set` because e2e unsets every key. e2e then runs the same hook entry with fakes (`e2e_fakes.py watch-merged`):

```text
knack watch apache/airflow: 1 merged PR: #900001
[1/5] select   1 PRs read, 1 kept
…
  warning: variants written by fake-spark, the compiler itself; no cross-model adversary
  #900001 proven on attempt 1
  #900001 held-out by fake-spark: 2/3 violations caught, 3/3 compliant allowed (pass)
[5/5] install  1 rules proven, 0 discarded, 1 in registry -> $W/home/.knack/registries/apache-airflow/registry.json
```

**Live: BROKEN.** The commands, in a sandbox clone holding #75025's base files:

```sh
knack watch --registry $W/data/registry/airflow.json --muse-settings $W/muse.json
git checkout -b pr-75025 && cp <75025 head files> && git commit -am "Live audit merge (#75025)" && git checkout main
git merge --ff-only pr-75025
```

The merge alone triggered the run (installed hook: `python -m knack.watch.hook post-merge --registry $W/data/registry/airflow.json || true`):

```text
knack watch apache/airflow: 1 merged PR: #75025
[1/5] select   1 PRs read, 1 kept
[2/5] extract  reading 1 PRs
  #75025: 1 decision, 1 rejected alternative
  1 decisions found, 1 rejected alternatives (1 verbatim), 0 failed
[3/5] roots    1 Inferred roots written (0 Confirmed, 0 Unknown kept)
[4/5] compile  1 PRs with a verbatim rejected alternative
  warning: variants written by muse-spark-1.3, the compiler itself; no cross-model adversary
  #75025 old release: 3.3.2 (last release before merge 2026-10-19)
  #75025 proven on attempt 3
  #75025 held-out by muse-spark-1.3: 2/3 violations caught, 3/3 compliant allowed (pass)
[5/5] install  1 rules proven, 0 discarded, 6 in registry -> $W/data/registry/registry.json
self-check airflow-75025 airflow-core/src/airflow/api_fastapi/core_api/routes/public/dags.py (the change takes the rejected path): muse-spark-1.3 no, meta-models/muse-spark-open-1026 no; logged only
… (8 self-check lines in all, for airflow-75025 and airflow-75774, every one "no, no; logged only")
```

Why BROKEN: the watched file `airflow.json` still lists 5 rules. The new rule went into a new `registry.json` (6 rules, last `rules/75025.yml`), and the root went into `data/registry/roots/`, not the registry's `roots_dir`. A guard reading `airflow.json` never sees either. The home registry is always named `registry.json`, which is why e2e and `live-smoke.sh` (which copies to `$COPY/registry.json`) pass.

Models: the root records `"models": ["muse-spark-1.3"]`. `self_checks.jsonl` records 8 checks, each answered by `muse-spark-1.3` and `meta-models/muse-spark-open-1026`. No trace shows Spark Open writing variants, and the log says it did not.

## 2. guard: deny

**Fakes: WORKS.** The alias edit through `python -m knack.hooks.pretool`:

```text
{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "Knack blocked this edit.\nDecision: Dag list endpoints do not accept bare state or start_date as sort keys\nDecided by: Pushkal-Gupta\n…
```

Receipt `c5dd0385edb4` (deny). The decided fix was allowed silently, receipt `bc7f792353ef`. An Inferred rule that matched stayed silent, receipt `ebfd3ab0c8f6` (allow, matched). An unloadable rule failed open: empty output, receipt `8ed4be1e64d3` with decision `guard-error`, logged to `guard_errors.log`.

**Live: WORKS.** The committed registry was imported, then the bench opener's `public/dags.py` was replayed as a `write_file` event:

```sh
knack import --registry data/registry/airflow.json
<write_file event for tests/guard/fixtures/replay/run3_public_dags.py> | python -m knack.hooks.pretool
```

```text
  rules: 5 added, 5 in registry
  roots: 9 written, 0 reviewed kept
{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "Knack blocked this edit.\nDecision: Dag list endpoints do not accept bare state or start_date as sort keys; the latest run is sorted only as last_run_state and last_run_start_date.\nDeci…
```

Receipt `19f0c5ce1aed5f0429a9e1d2153614ab1de87985184baaffb246955c9c9a4236`. Models: none.

## 3. warn

**Fakes and live: WORKS.** A `UserPromptSubmit` event with the prompt "Let get_dags sort by order_by=state and start_date again", piped to `python -m knack.hooks.warn`:

```text
{"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "knack: Confirmed decision(s) touch this prompt:\n- airflow-75025-1: Dag list endpoints do not accept bare state or start_date as sort keys; the latest run is sorted only as last_run_state and last_run_start_date.\n  Rejected alternative: Alias state and start_date onto DagRun.state and DagRun.start_date.\n  \"I removed them rather than…
```

That is the live output. Each run appended one line to `warns.jsonl` (live: `2026-11-02T04:44:26.224350+00:00`). Models: none.

## 4. argue → hold

Command: `knack argue "The frontend still sends order_by=state. Let me alias state and start_date onto DagRun.state and DagRun.start_date."`

**Fakes: WORKS.**

```text
HOLD
The team removed these sort keys instead of aliasing them.
  "I removed them rather than aliasing them onto `DagRun.state` and `DagRun.start_date`."
```

The fake `spark_ruling` answered, but `rulings.jsonl` records `"model":"muse-spark-1.3"` (see ticket).

**Live: BROKEN** (one run, no retry). Spark escalated:

```text
ESCALATE: held for a person
My decision does not address the case where the frontend still sends order_by=state. A person will decide whether to alias.
To resolve: knack resolve 19f0c5ce1aed5f0429a9e1d2153614ab1de87985184baaffb246955c9c9a4236 allow|retire --reason "<why>"
self-check airflow-75025 airflow-core/src/airflow/api_fastapi/core_api/routes/public/dags.py (the quotes do not answer the objection, so the deny should not hold): muse-spark-1.3 yes, meta-models/muse-spark-open-1026 no; logged only
```

The ruling cites `[]`. The models disagreed, so the check was logged only. An untested hypothesis: the Confirmed root's quotes include "Happy to alias instead if you would rather keep the advertised names working.", which may read to Spark as the alias being offered rather than rejected. `scripts/live-smoke.sh` accepts `^(HOLD|ESCALATE)`, so it would not catch this. Models: `muse-spark-1.3` (`rulings.jsonl`), `meta-models/muse-spark-open-1026` (`self_checks.jsonl`).

## 5. argue → escalate

Command: `knack argue "The public API docs promise order_by=state until its deprecation window ends in 3.2."`

**Fakes: WORKS.** e2e covers the branch where the models disagree:

```text
ESCALATE: held for a person
The quotes say nothing about a deprecation window.
To resolve: knack resolve c5dd0385edb4f4b845f6cd46112e4b4571772c5667cc89a4c3ad4fff71ce0a7c allow|retire --reason "<why>"
self-check … muse-spark-1.3 yes, fake-spark-open no; logged only
```

The branch where both models escalate (scratch fakes, Spark Open escalating) ended `fake-spark-open yes; holding a provisional must-pass case for a person` and wrote `provisional/26457bb4627d….json`.

**Live: WORKS.**

```text
ESCALATE: held for a person
I do not address a public API docs promise to keep order_by=state until its deprecation window ends in 3.2. A person will decide.
  "I removed them rather than aliasing them onto `DagRun.state` and `DagRun.start_date`."
  "Happy to alias instead if you would rather keep the advertised names working."
To resolve: knack resolve 19f0c5ce1aed5f0429a9e1d2153614ab1de87985184baaffb246955c9c9a4236 allow|retire --reason "<why>"
self-check … muse-spark-1.3 yes, meta-models/muse-spark-open-1026 yes; holding a provisional must-pass case for a person
provisional must-pass case $W/home/.knack/registries/apache-airflow/provisional/19f0c5ce1aed5f0429a9e1d2153614ab1de87985184baaffb246955c9c9a4236.json; a case only after: knack resolve 19f0c5ce… allow --reason "<why>"
```

No rule was recompiled. Models: `muse-spark-1.3` (`rulings.jsonl`), plus `muse-spark-1.3` and `meta-models/muse-spark-open-1026` (`self_checks.jsonl`, `case_key` `d5c2aa0958d7`).

## 6. resolve: learn receipt

**Fakes: WORKS.**

```text
c5dd0385edb4: allowed by e2e lead (airflow-75025, airflow-75025-1): frontend migration needs one release
5f47574d36a9: retired by e2e lead (airflow-75025, airflow-75025-1): sort aliases are back by design
```

The resolution receipts are `18fd1512b7df` (allow) and `e2d8ef0730b4` (retire). The exact allowed edit then passed (`c99e5cad2148`), and the retired rule went silent. In the "both escalate" run, `knack day --json` showed the learn receipt `72c9fe42347a`. It was listed before the block it resolved (ticket above).

**Live: WORKS.**

```sh
knack resolve 19f0c5ce1aed5f0429a9e1d2153614ab1de87985184baaffb246955c9c9a4236 allow --reason "frontend migration needs one release" --by "audit lead"
```

```text
19f0c5ce1aed: allowed by audit lead (airflow-75025, airflow-75025-1): frontend migration needs one release
provisional case is now must-pass for airflow-75025: $W/home/.knack/registries/apache-airflow/cases/airflow-75025/must-pass-d5c2aa0958d7.json
```

`knack receipts verify` reported `3 receipts, chain intact`. `knack day --json` gave `block 04:34:30.664040`, `argue 04:35:03`, `argue 04:35:26`, `learn 04:35:48 0c576d656a5a`. Models: none.

## 7. miss loop: recompile → prove → install

**Fakes: WORKS.**

```text
airflow-900001 fails: guard edit … [c49124503cd1] adds no new match; recompiling with fake-spark
PASS cases / PASS proof / PASS held-out same 3/3 (old 2) / PASS held-out cross 3/3 (old 2) / PASS fresh cross-model 3/3 (old 2)
installed airflow-900001 -> $W/…/rules/900001.yml (1 attempt(s))
```

A bad candidate (`1f492766a409`) was rejected with `kept the old airflow-900001: 4 gate(s) failed`, and the rule file stayed byte for byte. False-block (`e0d0584e3fbf`) was recorded as must-pass and installed. The watch self-check (`fake-spark yes, fake-spark-open yes`) recorded `883dfa0849a0` and installed.

**Live: WORKS.** The probe is the `**` splat gap that README Limits lists for #15937: `StreamingResponse(…, media_type="text/event-stream", **{"status_code": …})`, built from `bench/misses/15937-renamed-subclass.edit.json`. It is not an agent edit.

```sh
knack miss $W/splat.edit.json --registry $W/data/registry/fastapi.json --heldout $W/data/heldout/fastapi --work $W/work
```

```text
recorded must-fail case fastapi/routing.py [4607a716613c] for fastapi-15937 -> $W/data/registry/cases/fastapi-15937/must-fail-4607a716613c.json
fastapi-15937 fails: guard edit fastapi/routing.py [4607a716613c] adds no new match; recompiling with muse-spark-1.3
PASS cases: every must-fail edit denied, every must-pass edit allowed
PASS proof: base, guard-edit, head, rename-base, rename-head, variant-compliant, variant-violation hold; 0 FP on the default branch and release 0.140.12
PASS held-out same: 3/3 violations caught (old rule 3), 3/3 compliant allowed
PASS held-out cross: 1/3 violations caught (old rule 1), 3/3 compliant allowed
PASS fresh cross-model: 2/3 violations caught (old rule 2), 3/3 compliant allowed ($W/work/15937/fresh-20261102T043801Z-fd3148)
installed fastapi-15937 -> $W/data/registry/../rules/fastapi/15937.yml (1 attempt(s))
```

The new rule changes `not: has: regex: '[*][*]'` to `'\*\*\s*[A-Za-z_]'`, so a `**{…}` literal is now caught and `**name` is still skipped. Held-out cross is still 1/3. Models: `muse-spark-1.3` (the recompile line), and `meta-models/muse-spark-open-1026` for all 6 files of the fresh set (`authors.json`).
