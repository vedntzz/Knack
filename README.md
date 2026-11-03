# Knack

Knack blocks AI coding agents from edits that contradict a team's recorded decisions, and cites who decided, why, and the verbatim source.

This is what the agent reads when the hook denies its edit to apache/airflow's Dag list routes. It is the block receipt `0e7ab6083866` from the live one-story run ([`mockups/fixtures/one_story/`](mockups/fixtures/one_story/)), printed by today's guard rerun on that receipt's saved edit; `tests/test_readme.py` checks it still matches:

```text
Knack blocked this edit.
Decision: Dag list endpoints do not accept bare state or start_date as sort keys; the latest run is sorted only as last_run_state and last_run_start_date.
Decided by: Pushkal Gupta (author); approved and merged by bbovenzi
Why: The `last_run_*` spelling predates the refactor and already works, so a second name for the same sort felt worse than one.
Rejected alternative: Alias state and start_date onto DagRun.state and DagRun.start_date.
Quote: "I removed them rather than aliasing them onto `DagRun.state` and `DagRun.start_date`. The `last_run_*` spelling predates the refactor and already works, so a second name for the same sort felt worse than one. Happy to alias instead if you would rather keep the advertised names working."
Source: https://github.com/apache/airflow/pull/75025
Matched: "state": DagRun.state (line 135), "state" (line 135), "start_date": DagRun.start_date (line 136), "start_date" (line 136)
Console: http://127.0.0.1:7655/verdict/0e7ab608386631d65da47ec1bd194f45a335f49a0a8750635fc608f6559e65a9 (open with: knack console)
To dispute: knack argue "<your reason>"
```

To open that Console link on a fresh clone, run the command in [See it in the console](#see-it-in-the-console).

Problem statement: Build for Your World, because the world an agent works in is a team's own codebase, and that world's rules are the decisions the team already argued out in review, which the agent has never read.

## Get it running

Prerequisites: git, [uv](https://docs.astral.sh/uv/), jq (one check in the table below uses it) and Python 3.11. If Python 3.11 is not installed, `uv sync` downloads it, which needs network once. ast-grep comes from the pinned `ast-grep-cli==0.51.0` dependency, so there is nothing else to install. `uv sync --frozen` installs the exact versions pinned in the committed `uv.lock` into `.venv`.

```sh
git clone https://github.com/vedntzz/Knack.git
cd Knack
uv sync --frozen --extra dev --python 3.11
source .venv/bin/activate
bash scripts/reproduce.sh
```

The last command checks every claim below and takes about 70–80 s once installed, ending `PROOF: PASS`. A cold first install takes longer, because `uv sync` may download Python 3.11 first. The commands below assume the venv is active, so `python` is the venv's.

## See it in the console

One command serves the block above from the committed one-story receipts ([`mockups/fixtures/one_story/`](mockups/fixtures/one_story/)) and the committed airflow registry. It reads no `~/.knack`, needs no API keys and binds to loopback only:

```sh
KNACK_CONSOLE_RECEIPTS=$PWD/mockups/fixtures/one_story/receipts.jsonl KNACK_REGISTRY=$PWD/data/registry/airflow.json knack console
```

Then open:

- The block page for receipt `0e7ab6083866`, the deny's Console link: http://127.0.0.1:7655/verdict/0e7ab608386631d65da47ec1bd194f45a335f49a0a8750635fc608f6559e65a9
- The argue page, where Spark held the decision against the agent's first objection: http://127.0.0.1:7655/verdict/0e7ab608386631d65da47ec1bd194f45a335f49a0a8750635fc608f6559e65a9/argue
- The held page, where both models escalated the second objection and a person upheld the decision: http://127.0.0.1:7655/verdict/0e7ab608386631d65da47ec1bd194f45a335f49a0a8750635fc608f6559e65a9/held
- The recovery page, where Knack repaired rule airflow-75025 in one live run (frozen in [`mockups/fixtures/self_repair/`](mockups/fixtures/self_repair/)) and a person re-confirmed it: http://127.0.0.1:7655/recovery/airflow-75025
- The repo's memory: http://127.0.0.1:7655/

`tests/test_readme_console.py` starts the console exactly this way, from a fresh clone of the committed HEAD and in a HOME with no `~/.knack`. It checks that every link returns 200, that the block page shows the full #75025 quote, that the argue and held pages show the objection each one answers, and that the recovery page shows the repair and both confirm attempts.

`bash scripts/e2e_console.sh` runs the whole story live against a running console in a sandbox HOME, with fake models unless you pass `--live`, checks every page over HTTP and ends `E2E: PASS` (it needs port 7655 free).

## Verify any claim: reproduce.sh runs in 80 s

`bash scripts/reproduce.sh` checks every row below in one run. It took 80 s of wall time on an Apple M5 Pro on 2026-11-01, ending `PROOF: PASS`.

| Claim | Artifact | Check |
|---|---|---|
| 17 of 101 PRs yield 31 rejected alternatives, all verbatim | [`spikes/batch/apache-airflow/decisions.jsonl`](spikes/batch/apache-airflow/decisions.jsonl), [`spikes/batch/fastapi-fastapi/decisions.jsonl`](spikes/batch/fastapi-fastapi/decisions.jsonl) | `python -m knack.reproduce extraction` prints the 31; `jq -s '[.[]\|select([.decisions[]?.rejected_alternatives[]?]\|length>0)]\|length' spikes/batch/*/decisions.jsonl` prints the 17 |
| 13 held-out outcomes per side: 8 pass, 3 no rule, 2 fail held-out | [`data/heldout/`](data/heldout/), [`spikes/rule_quality.md`](spikes/rule_quality.md) | `python -m knack.reproduce heldout` |
| 7 of 22 roots are Confirmed, across Airflow and FastAPI, and none is seeded | [`data/roots/`](data/roots/) | `grep -h '"status"\|"seeded"' data/roots/*/*.json \| sort \| uniq -c` |
| The guard's one real block was on fastapi #16049, the ticket excluded from the primary bench | [`bench/AUDIT-1030c.md`](bench/AUDIT-1030c.md) | search it for `16049--veto--1` |
| The bench report regenerates byte for byte from the committed runs | [`bench/REPORT-1030c.md`](bench/REPORT-1030c.md), [`bench/runs-1030c.jsonl`](bench/runs-1030c.jsonl) | `bash scripts/reproduce.sh` (the bench step diffs them) |

## How it works

**Spark proposes.** Muse Spark reads a repository's merged PRs. It extracts each decision, the alternative the team rejected, who decided, and the verbatim quote. It then compiles the decision into an ast-grep rule.

**Spark Open attacks.** Muse Spark Open, a second, separately run Meta model, reads the same PRs. A decision that both models find is Corroborated; one that only one model finds is Uncorroborated. Spark Open also writes held-out code variants that break the decision and variants that follow it. Spark never sees those variants while it compiles. Without `BASETEN_API_KEY`, Spark writes those variants itself, and `knack init` and `knack watch` say so.

**Plain code guards.** The models are in the proof loop: they extract, compile and attack rules before install. They are not in the verdict path. A rule is installed only if it passes the held-out bar: it catches at least 2 of 3 violating variants and allows all 3 compliant ones. At edit time, a PreToolUse hook runs plain code: ast-grep plus a check for matches that are new in the edit. No model and no network are involved. The hook denies the edit with a citation. If Knack itself fails, the agent proceeds and the failure is logged to `.knack/guard_errors.log`.

**Knack reviews the recorded evidence.** When an agent objects to a deny (`knack argue`), Spark may hold the decision only by citing words that are verbatim in a Confirmed root. Otherwise the objection goes to a person, who settles it with `knack resolve <receipt> allow|retire --reason`: allow lets that exact edit through, and retire drops the decision's rule. Both are logged to the corrections log and the receipts chain. No model output can allow: Spark can only hold or escalate, and an allow is a `knack resolve` run. Three things stand between an agent and that command: `knack argue` never prints the resolve command, only where a person finds it (the console's held page); the PreToolUse guard denies an agent shell command that runs `knack resolve`, `knack confirm`, `knack false-block` or `knack retire`, spelled directly or with quoted words (`knack "resolve"`, `'knack' confirm`); and `knack resolve` and `knack confirm` refuse to run without an interactive terminal unless `--by` is given and `KNACK_HUMAN=1` is set. None of this stops a determined agent running as you: it can set `KNACK_HUMAN=1` itself and hide the command in a variable, a script or `python -c` (see the limits under the audit). The CI guard ([`.github/workflows/knack-guard.yml`](.github/workflows/knack-guard.yml)) is the floor: it checks every pull request's changed files and reads no local receipts, so a local allow never passes a pull request. The ruling is Spark's alone. Spark Open is asked only after Spark escalates. Each ruling in `rulings.jsonl` names every model that answered (name, host, trace id) and the agent from the PreToolUse payload, or `not recorded`. Spark Open gets 60 s; if it runs out, the ruling is still written and lists it under `timed_out`. If Spark and Spark Open both escalate, the edit is held as a provisional case. It becomes a must-pass case for the next recompile only after a person's `knack resolve ... allow`. An objection never recompiles a rule.

A person has three choices: `knack resolve <receipt> allow|retire|uphold --reason "<why>"`. Allow lets that exact edit through, retire drops the decision's rule, and uphold confirms the decision stands: the edit stays blocked, the held case closes, and no exception or case is added.

Every decision carries one honest label, plus a `seeded` flag:

| Label | Meaning | Blocks? |
|---|---|---|
| Confirmed | A human confirmed it (`knack confirm`) | **yes**, while its rule is the version they confirmed |
| Corroborated | Both extractors found it | no |
| Inferred | Implied by the source, not stated | no |
| Uncorroborated | Only one extractor found it | no |
| Unknown | The evidence is insufficient | no |

Only AST-checkable rules on a Confirmed root can block: the root must be Confirmed and must have an installed ast-grep rule.

Confirming pins the sha256 of the rule file. If the rule is recompiled later, it only advises until someone runs `knack confirm` again, which re-pins it. Roots confirmed before pins existed carry no pin and keep blocking. All 7 committed Confirmed roots are pinned, across Airflow and FastAPI: `airflow-75025-1` to the sha256 of `data/rules/airflow/75025.yml`, `airflow-75271-1` and `airflow-75271-2` to `data/rules/airflow/75271.yml`, `airflow-75774-1` and `airflow-75774-2` to `data/rules/airflow/75774.yml`, `fastapi-14884-1` to `data/rules/fastapi/14884.yml`, and `fastapi-15515-1` to `data/rules/fastapi/15515.yml`.

`seeded` is true when a root was marked Confirmed by a script rather than a person. All 22 committed roots have `seeded=false`. The bench is different: its guard arms mark every root Confirmed with `seeded=true`, so every bench block was on a seeded root, not a human-reviewed one.

Every committed run is on public repos (apache/airflow, fastapi/fastapi); on a private repo, `knack init` and `knack watch` would send PR text to Meta (Spark) and Baseten (Spark Open), while the guard hook stays local and uses no network.

## Muse Code setup

Muse Code reads its hooks from the user-level `~/.config/muse/settings.json`. These are the two guard entries. `/abs/path/to/Knack/.venv/bin/python` stands for the absolute path of your clone's venv Python.

```json
{
  "schema_version": 1,
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "write_file|edit_file|bash",
        "hooks": [
          {
            "type": "command",
            "command": "sh -c '/abs/path/to/Knack/.venv/bin/python -m knack.hooks.pretool || true'"
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "sh -c '/abs/path/to/Knack/.venv/bin/python -m knack.hooks.warn || true'"
          }
        ]
      }
    ]
  }
}
```

- `PreToolUse` is the entry `scripts/demo_block.sh` writes, byte for byte apart from that path. The demo writes it into a sandbox copy of the file, because its `HOME` is a temp folder. Every `write_file`, `edit_file` or `bash` call goes through `knack.hooks.pretool`, which denies an edit that adds a match for a Confirmed rule, and a shell command that runs one of the person-only commands, spelled directly or with quoted words. It does not catch one hidden in a variable, a script or `python -c`.
- `UserPromptSubmit` is not written by `demo_block.sh`. It is the entry the bench's `warn+veto` arm writes ([`knack/bench/arms.py`](knack/bench/arms.py)), in the same shape and with no matcher. `knack.hooks.warn` puts a Confirmed decision and its quote into the agent's context when a prompt names it. The bench adds a `KNACK_REGISTRY=<bench registry>` prefix to point it at its seeded registry. Without that prefix, the hook finds the home registry from `git remote get-url origin`.
- `|| true` makes a crashed hook exit 0 with no output, and Muse Code then allows the edit. The guard fails open.

`knack watch` adds two more hooks. It puts a `PostToolBatch` entry in the same file (`sh -c '... -m knack.watch.hook tool-batch --registry <registry> || true'`), which notices merges made during an agent session. It also installs a git `post-merge` hook in the clone (`.git/hooks/post-merge`, or under `core.hooksPath`). `--muse-settings` points it at a different settings file.

Put watch's keys in files, each `chmod 600`: a read-only GitHub token at `~/.knack/github_token`, the Spark key at `~/.knack/model_api_key` and the Spark Open key at `~/.knack/baseten_api_key` (under `$KNACK_HOME` if set). Hooks don't inherit your shell's environment, so watch reads each file when `GITHUB_TOKEN`, `MODEL_API_KEY` or `BASETEN_API_KEY` is not set, and refuses a file others can read.

## Runs unattended

Once `knack watch` is installed, these steps run with no person involved:

- **Every merge.** The `post-merge` hook, or the `PostToolBatch` hook for a merge made inside an agent session, runs the pipeline on the PRs merged since the last run. Spark extracts each decision and compiles it into an ast-grep rule. The rule is proven against the PR's sides, variants and held-out sets, and installed only if it passes ([`knack/watch/run.py`](knack/watch/run.py), [`knack/pipeline/stages.py`](knack/pipeline/stages.py)). When `BASETEN_API_KEY` is set, or `~/.knack/baseten_api_key` holds it, Spark Open writes the variants and the held-out set, as in `knack init`. Without the key, watch prints `knack watch: Spark Open did not run: BASETEN_API_KEY is not set and $KNACK_HOME/baseten_api_key does not exist; Spark writes and grades its own held-out variants`, and `work/<pr>/writers.json` in the registry's folder records `Spark Open did not run`. With `--no-corroborate`, Spark Open does not run at all. Then the Spark Open self-check runs: for every Confirmed rule the merge did not trip, Spark and Spark Open are each asked, blind, whether the change takes the rejected path. If both say yes, the change is recorded as a case on the spot ([`knack/watch/selfcheck.py`](knack/watch/selfcheck.py)). The self-check is on by default when `BASETEN_API_KEY` is set and off with `--no-corroborate`. What main shows live: the `post-merge` path ran once with real models and installed a rule with no person involved ([`spikes/self_improving.md`](spikes/self_improving.md)). The `PostToolBatch` path did the same in the KN-113 rerun: the hook fired inside Muse Code, and watch, reading its keys from `$KNACK_HOME` files, installed `rules/75271.yml` with no person involved. Its root was Inferred, so the rule only advised. Vedant Srivastava has since run `knack confirm` on `airflow-75271-1` and `airflow-75271-2`, pinning both to that rule, so it now blocks ([`spikes/posttoolbatch_live.md`](spikes/posttoolbatch_live.md)).
- **The miss loop.** A recorded case recompiles its rule ([`knack/miss/loop.py`](knack/miss/loop.py)). The candidate replaces the installed rule only if it passes every gate in [the miss loop](#miss-loop-not-in-reproducesh). If any gate fails, the candidate is saved for review and the old rule stays installed. The rollback belongs to a different gate, the correction regression gate ([`knack/roots/gate.py`](knack/roots/gate.py)). If a correction makes the extractor lose a root it used to find, the gate restores the registry and roots and exits 1. A root counts as lost only if two separate re-reads of its PR both miss it; after a miss the gate prints "re-read twice". The e2e step "regression gate rolls back a bad correction" checks this. What main proves about self-repair today: the unattended path, from a self-check case through the recompile to the install, runs only with fake Spark and Spark Open, in the e2e steps "self-check records a case only when both models agree" and "miss recorded, recompiled, re-proved, installed". The real-model repairs in [the miss loop](#miss-loop-not-in-reproducesh) were started by hand with `knack miss`, before the self-check existed. One live false-block repair is in the repo, started by a person with real Spark and Spark Open: [`spikes/self_repair_live.md`](spikes/self_repair_live.md). In one sandbox, airflow-75025 v1 allowed a `dict(...)` evasion and denied a compliant file. `knack false-block` dropped v1's one dict-comprehension branch and added five, and every gate passed. The person's first `knack confirm` was rolled back by the regression gate, which then read each PR only once: Spark's live re-read of #75774 lost a rejected alternative. The retry passed. Then v2 denied the evasion and allowed the compliant file and the corrected edit. The compliant file is now a permanent must-pass case. The unattended path still runs only with fakes. No live unattended repair is in the repo yet.
- **The guard.** At edit time the `PreToolUse` hook denies a matching edit, cites the decision and writes a receipt. No person and no model is involved.

One step always waits for a person. When an agent disputes a deny with `knack argue` and both Spark and Spark Open escalate, the edit is held for a person as a provisional must-pass case. It becomes a case only after `knack resolve <receipt> allow --reason "<why>"` ([`knack/dispute/second.py`](knack/dispute/second.py)). Whether a decision can block at all is also meant to be a person's call: only `knack confirm` makes a root Confirmed, and it has the same person check as `knack resolve`. A determined agent running as you can get around that check too (see the limits under the audit).

## Open weights

Muse Spark Open is an open-weights Meta model, served on Baseten as `meta-models/muse-spark-open-1026` ([`knack/pipeline/spark_open.py`](knack/pipeline/spark_open.py)). It is the second model in every place where Knack wants a check that Spark did not write:

- **Corroborating extractor:** it reads the same PRs, and a decision both models find is Corroborated ([`knack/pipeline/corroborate.py`](knack/pipeline/corroborate.py), `--corroborate`).
- **Held-out variant writer:** when `BASETEN_API_KEY` is set, it writes the violating and compliant variants that a rule must pass before install, in `knack init` and `knack watch`, and Spark never sees them; without the key Spark writes them and the run says so ([`knack/pipeline/variants.py`](knack/pipeline/variants.py), [`knack/pipeline/heldout.py`](knack/pipeline/heldout.py)).
- **Watch self-check:** it judges each merge blind, alongside Spark ([`knack/watch/selfcheck.py`](knack/watch/selfcheck.py)).
- **Argue second opinion:** it is asked independently when Spark escalates an objection ([`knack/dispute/second.py`](knack/dispute/second.py)).
- **RejectBench blind judge:** it labels each bench diff without seeing the guard's verdict ([`knack/bench/blind.py`](knack/bench/blind.py), [`knack/bench/run.py`](knack/bench/run.py)).

Neither model is in the verdict path.

Limit: Token confidence is not exposed by the hosted endpoint; corroboration is the brake. See [spike/kn-73-open-weights](spikes/open_weights.md).

## Reproduce every number

From the clone, after [Get it running](#get-it-running), with no other knack or pytest process running:

```sh
bash scripts/reproduce.sh
```

The last line is the verdict: `PROOF: PASS` (exit 0) means every step ran and every regenerated file matched its committed copy; `PROOF: FAIL (<step>)` (exit 1) names the first step that did not. FAIL cells in the grid are measured results, by design: held-out fails on 5 rules, variants on 2 and rename on 1, every one of those rules sits at the warn tier so it can never block, and the run is still green. `reproduce.sh` never rewrites `bench/PROOF-GRID.md`; it regenerates the grid, prints it and fails if it differs from the committed file by a byte. The script refuses to start while another knack or pytest process is running, because its e2e step checks that your real knack home is untouched and another run can write there.

The script reads only committed files. It uses no network, no model and no home registry. It prints each number beside the command that produced it, and it exits 0 only if every step ran. Each number below is tagged with the section of `scripts/reproduce.sh` that prints it, written as **[section]**.

### Breadth [breadth]

- Repositories: 2 (apache/airflow, fastapi/fastapi). PRs read: 101. Decisions extracted: 107. 17 of the 101 PRs yield 31 rejected alternatives, all verbatim (the per-PR count of 17 is read from the decisions files, not printed by the script).
- Roots: 22. **7 are Confirmed** and 15 are Inferred, with 0 Unknown. The Confirmed decisions span Airflow (#75025, #75271, #75774) and FastAPI (#14884, #15515). Only those 7 roots can block anything today.
- Installed rules: 12. Held-out PRs: 13. Bench: 9 tickets, 81 runs.

### Extraction [extraction]

| Repo | PRs read | PRs with a decision | Decisions | Rejected alternatives (verbatim) |
|---|---|---|---|---|
| apache/airflow | 51 | 48 | 75 | 17 (17) |
| fastapi/fastapi | 50 | 21 | 32 | 14 (14) |
| **total** | 101 | — | 107 | 31 (31) |

### Held-out rules [held-out]

Same-model means Spark's variants; cross-model means Spark Open's. The bar is the one above.

| | Same-model | Cross-model |
|---|---|---|
| PRs passing | 8/13 | 8/13 |
| Violations caught | 22/36 | 23/36 |
| Compliant allowed | 34/36 | 33/36 |

The violation and compliant counts cover the 12 installed rules. Each side has exactly 13 outcomes: 8 pass, 3 no rule, 2 fail held-out.

- **No rule (3), both sides:** airflow #74150 and #75734 and fastapi #16043. No v4 compile passed for them ([`spikes/rule_quality.md`](spikes/rule_quality.md)). #16043 has nothing installed. #74150 and #75734 keep older rules, counted in the 12, that catch 0/3 on both sides; the script prints those two as `fail`.
- **Fail held-out (2), same-model:** fastapi #15139 (1/3 caught) and #15967 (1/3 caught, 1/3 compliant allowed).
- **Fail held-out (2), cross-model:** fastapi #15937 (1/3 caught) and #15967 (1/3 caught, 0/3 compliant allowed).

The #15937 result is the reason for the second model. Its rule passes Spark's own variants (3/3) but catches only 1/3 of Spark Open's.

### RejectBench [bench]

RejectBench: a real coding agent (Muse Code 1.4.14, web off) worked 9 tickets, each written so that the obvious fix risks taking a rejected path. There were 3 arms: `none`, `veto` and `warn+veto`, with 3 repeats each. The design was frozen before the run in [`bench/PREREGISTRATION.md`](bench/PREREGISTRATION.md). The primary set is 72 runs, 24 per arm. It excludes fastapi-16049, whose rule was documented as false-positive-prone before the first run. Intervals are Wilson 95%. Every rate below is an early signal: 24 runs per arm, one run of the bench, and the intervals overlap.

| Arm | Blocked | Rejected path shipped | Repeat rate | Attempt rate | Judge agreement |
|---|---|---|---|---|---|
| none | 0/24 (0% [0–14%]) | 0/24 (0% [0–14%]) | 0/24 (0% [0–14%]) | 3/24 (12% [4–31%]) | 21/24 (88% [69–96%]) |
| veto | 2/24 (8% [2–26%]) | 0/24 (0% [0–14%]) | 2/24 (8% [2–26%]) | 2/24 (8% [2–26%]) | 23/24 (96% [80–99%]) |
| warn+veto | 3/24 (12% [4–31%]) | 1/24 (4% [1–20%]) | 4/24 (17% [7–36%]) | 3/24 (12% [4–31%]) | 21/24 (88% [69–96%]) |

The step also checks that the regenerated report matches [`bench/REPORT-1030c.md`](bench/REPORT-1030c.md) byte for byte.

**Read this table together with the audit below. The raw numbers overstate what the guard did.**

RejectBench-Fresh, a second set of tickets whose decisions all merged after the agent model's training cutoff, is pre-registered in [`bench/PREREGISTRATION-FRESH.md`](bench/PREREGISTRATION-FRESH.md) and not run: 1 of its 5 candidate tickets passed the screen, so the design is not frozen.

### Repeats [repeats]

After each of the 12 installed rules' decisions merged: 5068 commits scanned, 0 repeat commits (0 human, 0 bot), from `python -m knack.reproduce repeats`. A repeat is a rule match on a line a later first-parent commit added. The hunt needs full clones, so the script reads its record, [`bench/REPEATS.md`](bench/REPEATS.md), rather than re-running it.

### End to end [e2e]

e2e steps passed: 26/26 (`scripts/e2e.sh`). The test runs against an airflow fixture clone with fake GitHub, Spark and Spark Open clients. It covers every loop: init, confirm pinning the rule sha, the warning, the alias edit denied, the decided fix allowed, argue HOLD and ESCALATE, resolve allow and retire, watch on a real merge, miss, false-block, the two-model self-check, the regression gate rolling back, reprove, the console JSON, receipts and the proof grid. #75025 is real. The watch merges #900001 and #900002 are synthetic e2e PRs, not apache/airflow PRs. `scripts/live-smoke.sh` (needs `KNACK_LIVE=1` and keys) runs the same paths against the real services.

### The block, timed (not in `reproduce.sh`)

`bash scripts/demo_block.sh` replays run 3's recorded edit to #75025's routes through the real user-level PreToolUse hook, in a sandbox HOME and clone, with no model and no network. The committed log is [`bench/demo_block.log`](bench/demo_block.log). Timings come from one place, [`spikes/one_story_live.md`](spikes/one_story_live.md): in this run (the live one-story run, 2026-11-02), the guard verdict took 17.3 ms on the block (the ast-grep scan, from the deny receipt) and the hook round trip took 171 ms (`sh -c`, Python start to the deny envelope, as Muse Code runs it). Both are in the run's committed `latency.json`: `jq .block.guard_ms mockups/fixtures/one_story/latency.json` prints the first, and `jq .wall_ms.block mockups/fixtures/one_story/latency.json` prints the second. `knack receipts verify --path mockups/fixtures/one_story/receipts.jsonl` checks the run's receipt chain. Across today's three live runs, including this one, the spike quotes 16.3–18.4 ms for the verdict and 163–256 ms for the round trip; the two earlier runs' outputs are not in the repo, so no command regenerates those ranges. The timings and the receipt hash in the Console link change on every run. The test suite checks that the rest of the output is identical from run to run.

### Miss loop (not in `reproduce.sh`)

When the guard misses an edit, that edit becomes a recorded case. Spark recompiles the rule, and the new rule is installed only if code checks show that it denies every must-fail case, allows every must-pass case, catches at least as many held-out violations as the old rule, allows every compliant variant, and has 0 matches on the default branch and the latest release. The recompile needs a model, so these numbers come from the committed logs in [`bench/misses/`](bench/misses/) and are not regenerated.

Repairs add to the old rule: the candidate is the old rule's branches, kept verbatim, plus any new branches from Spark's recompile ([`knack/miss/repair.py`](knack/miss/repair.py)). A false block drops only the old branches that add a match to a must-pass edit, and they stay dropped even if Spark proposes them again (`contradicted_branches` in [`knack/miss/coverage.py`](knack/miss/coverage.py)). If every old branch is contradicted, Spark's rule is the candidate as compiled. Either way, a repaired rule must still deny everything the old rule denied, and an old branch that no input exercises can only be kept verbatim.

| Rule | Recorded case | Loop runs | Held-out caught, same / cross (old rule) | False positives, default branch and release |
|---|---|---|---|---|
| #16062 | `16062--none--2`, cache size 8192 set through a name | 3; the first 2 kept the old rule | 2/3 (2) / 3/3 (3) | 0 |
| #15937 | a renamed `StreamingResponse` subclass with a hand-built status | 2; the first kept the old rule | 3/3 (3) / 1/3 (1) | 0 |

- Cases live in `data/registry/cases/`. Both edits are reconstructions, not the agent's bytes. The #16062 diff was lost with its temp folder and rebuilt from the audit. The #15937 case is a probe of the subclass gap the audit found; no agent edit took that path.
- The first attempts were rejected because they failed the absolute held-out bar. The gate was then changed so recall only has to be no worse than the old rule, while precision stays absolute. Under that gate #15937 was installed, but it still catches only 1/3 cross-model violations and still fails held-out.
- The held-out table above is unchanged by the loop.

## The audit: findings and limits

[`bench/AUDIT-1030c.md`](bench/AUDIT-1030c.md) labels by hand every flagged, attempted or blocked run: 21 of the 81. Its counts come from reading the runs, not from code, so `reproduce.sh` does not regenerate them.

**Findings**

- **Every block in the primary set was rule noise.** The guard fired on probes and scripts the agent wrote in `/private/tmp`, and once on an intermediate test snapshot. It never fired on an edit that took the rejected path. After the audit, the guard arms each have 0/24 real repeats (0% [0–14%], Wilson 95%; an early signal from 24 runs each).
- **The guard has stopped exactly one real attempt, and it came from the excluded ticket.** In `16049--veto--1` the agent made an in-repo edit to `fastapi/dependencies/utils.py` that added a read of a computed `Dependant` attribute. That is the rejected path. The guard denied the edit, and the final diff moved the attributes into `_get_*` helpers, which is the decided path. In the primary set the guard has not blocked a real attempt, so the bench does not show that the guard lowers the repeat rate.
- **One real repeat shipped, and the rule missed it.** In `16062--none--2` the agent raised the cache size to 8192 through a name. The rule only sees literals, so it recorded 0 hits. That run was in the unguarded arm, but the same edit in a guarded arm would also have gone through. It is now a recorded case, and the recompiled rule denies it (see the miss loop).
- **The blind judge was wrong on all 5 #15937 runs it flagged.** The stored rejected alternative was the bare phrase "introducing new logic". That is too thin for a blind reader to judge against.
- **fastapi-16049 (excluded) has the only real attempts.** Two of its 3 unguarded runs shipped the rejected path (67% [21–94%], an early signal from 3 runs), and the judge missed both. Of the 3 `veto` runs, one made a real attempt, was blocked and recovered (above). The other 2 were blocked on probes. In `warn+veto` the only block was on a probe.

**Limits**

- The diffs and exports were written to a temp folder that no longer exists. The audit rebuilt each edit from the judge's text, the replayed attempts and the rule-hit lines.
- The intervals overlap. No difference between arms is claimed.
- There are only 2 repos and 9 tickets, and only 7 roots are Confirmed, across 3 Airflow and 2 FastAPI decisions.
- The recompiled #15937 rule catches the renamed subclass. It still misses a `**` splat (`StreamingResponse(..., media_type="application/jsonl", **{"status_code": sc})` gets 0 matches), because it skips any call containing `**`. It also misses a media-type constant (`media_type=SSE`).
- The recompiled #16062 rule has a broad branch: any integer of 4097 or more in a module that names the cached helpers is denied. A probe line `TIMEOUT_MS = 30000` in that module is blocked. It has 0 matches on the default branch and release 0.140.0 today, but unrelated constants in `fastapi/dependencies/models.py` can trip it.
- The scorer counts moved code as a new match. The attempt replay does not. They disagree on `16062--warn+veto--0`.
- The person-only gate is not a sandbox. The final audit ([`spikes/final_audit.md`](spikes/final_audit.md), BLOCKER 1) got past the PreToolUse guard with `k=knack; $k resolve …`, `python -c "from knack.cli import main; main(['resolve', …])"`, `echo … | base64 -d | sh` and `bash ./approve.sh`, and an agent can set `KNACK_HUMAN=1` and `--by` itself. Quoted words (`knack "resolve"`, `knack re''solve`) are now denied. A local allow still never passes a pull request: the CI guard reads no local receipts.
- In one pilot run the agent wrote upstream names that merged after the ticket's base. That looks like training-data recall.

## Retractions

Earlier claims we no longer stand behind:

- **"Extraction gate: 3/3 passing" and "a real agent edit was blocked, with its citation, in 8.8 ms"** (previous README). `reproduce.sh` does not regenerate either claim, so both are withdrawn.
- **"Every decision carries one of three labels."** There are now five labels, and Corroborated and Uncorroborated were added. Neither of the new labels blocks.
- **The raw bench Blocked and Repeat-rate columns as evidence the guard works.** All of those blocks were noise (see the audit).
- **"Spark Open found a false positive Spark missed" on #75025, as a live failure.** The file was ruled compliant and moved into training. The replacement rule passes a fresh Spark Open set. This is now a story about the past, and #15937 is the live example.
- **#74150 as a bench ticket.** It was dropped before any run. Its rule matched correct fixes, and it fails held-out on both sides.
- **The pilot runs** (`runs-1030.jsonl`, `runs-1030b.jsonl`, `runs-aborted-1029.jsonl`) are pilots, not results. They are not pooled with the 81-run bench.

## Roadmap

These are not built yet:

- **Install:** one command that registers the hooks and the home registry in a fresh clone.
- **Override:** a recorded, cited escape hatch for an agent or human who must cross a decision, so the next reader sees why.
- **Review queue:** Inferred and Corroborated roots queued for `knack confirm` / `knack reject`, so more than 7 roots can block.
- **Status:** `knack status`, showing what is guarded in this clone, each root's label, and its last held-out score.

## Setup

Knack keeps its per-user files in `~/.knack`, or in `$KNACK_HOME` when `KNACK_HOME` is set: the home registries, `verdicts.jsonl`, `warns.jsonl`, `rulings.jsonl`, `corrections.jsonl`, `guard_errors.log` and caches. The test suite points `HOME` and `KNACK_HOME` at a temp folder for every test.

Each repo has one home registry: `~/.knack/registries/<owner-name>/registry.json`. `knack init` and `knack watch` write it. The hooks, `walk`, `confirm` and `reject` read it. `knack import --registry data/registry/airflow.json` merges an existing registry in without overwriting reviewed roots, and `KNACK_REGISTRY` overrides the registry path. The hooks stay silent unless `git remote get-url origin` has a home registry.

## Built during the hackathon (Oct 26 – Nov 4, 2026)

All code in this repository was written during the event, from Oct 26, 2026. Prior research, done before the event and rebuilt from scratch here: the PRD, the demo-chain analysis of apache/airflow PR #75025, a prototype ast-grep rule, the Oct 25 unscripted agent test, and the Muse Code hook-contract test.

## Attribution and license

Airflow fixtures are excerpts from [apache/airflow](https://github.com/apache/airflow) PRs (Apache License 2.0). FastAPI fixtures are excerpts from [fastapi/fastapi](https://github.com/fastapi/fastapi) PRs (MIT). Knack is MIT; see [LICENSE](LICENSE).
