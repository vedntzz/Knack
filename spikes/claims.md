# Claims audit

Every factual claim a judge can read in `README.md`, `docs/card.md`, `site/index.html` and the console's fixed copy (`knack/console/templates`, plus the figure labels in `knack/console/pages/verdict.py`, which the templates render), with the command that reproduces it.

Run on `chore/claims-audit` at `9bf4802` (= `origin/main`), 2026-11-02, Apple M5 Pro, venv active, no other knack or pytest process running. `R` = `bash scripts/reproduce.sh` (70.3 s wall, `PROOF: PASS`); `R[x]` = its section `x`. Rebased on `6f81205` (KN-113, PR #112) the same day: README line numbers from 136 on moved down 2, and the PostToolBatch rows were rechecked against the merged spike.

Status is the claim as it read on main before this branch. FAIL means the output differs, the claim is unscoped, or no command exists; the Fix column says what wording changed.

## Numbers

| Claim | Where | Command | Output | Status | Fix |
|---|---|---|---|---|---|
| reproduce.sh takes about 70–80 s once installed, ends `PROOF: PASS` | README 36, 55–57; site Run it | `time bash scripts/reproduce.sh` | `PROOF: PASS`, real 70.31 s | PASS | |
| 2 repos, 101 PRs read, 107 decisions | README 176; card 19; site — | `python -m knack.reproduce breadth` | `repos: 2`, `PRs read: 101`, `decisions extracted: 107` | PASS | |
| 17 of 101 PRs yield 31 rejected alternatives, all verbatim | README 61, 176; card 20 | `python -m knack.reproduce extraction`; `jq -s '[.[]\|select([.decisions[]?.rejected_alternatives[]?]\|length>0)]\|length' spikes/batch/*/decisions.jsonl` | `total rejected alternatives: 31 (31 verbatim)`; `17` | PASS | |
| Per-repo extraction: airflow 51/48/75/17, fastapi 50/21/32/14 | README 182–186 | `R[extraction]` | same | PASS | |
| 22 roots: 7 Confirmed, 15 Inferred, 0 Unknown; all `seeded=false`; Confirmed decisions span Airflow and FastAPI | README 63, 93, 177 | `python -m knack.reproduce breadth`; `grep -h '"status"\|"seeded"' data/roots/*/*.json \| sort \| uniq -c` | `22 (7 Confirmed, 0 Corroborated, 15 Inferred, 0 Uncorroborated, 0 Unknown)`; `22 seeded: false`, `7 Confirmed`, `15 Inferred` | PASS | |
| Only those 7 roots can block | README 177, 265 | `R[proof grid]`, Tier column | `block` on airflow #75025, #75271, #75774 and fastapi #14884, #15515 only | PASS | |
| 12 installed rules, 13 held-out PRs, 9 tickets, 81 runs | README 178 | `python -m knack.reproduce breadth` | `12`, `13`, `9`, `81` | PASS | |
| 13 held-out outcomes per side: 8 pass, 3 no rule, 2 fail | README 62, 198; card 21 | `python -m knack.reproduce heldout` | same-model 8/13 pass; fails #74150, #75734, #16043 (no rule) + #15139, #15967; cross-model 8/13; fails #74150, #75734, #16043 + #15937, #15967 | PASS | |
| Held-out caught/allowed 22/36, 34/36 same; 23/36, 33/36 cross | README 194–196 | `python -m knack.reproduce heldout` | same | PASS | |
| #15937 passes Spark's variants 3/3, catches 1/3 of Spark Open's | README 204 | `python -m knack.reproduce heldout` | `fastapi #15937 same-model 3/3 … cross-model 1/3` | PASS | |
| Grid: held-out fails on 5 rules, variants on 2, rename on 1, all warn tier | README 170 | `python -m knack.reproduce grid` | `held-out: 7 PASS, 5 FAIL`, `variants: 10 PASS, 2 FAIL`, `rename: 11 PASS, 1 FAIL`; every FAIL row is `warn` | PASS | |
| Grid regenerates byte for byte | README 65, 170; site caption | `R[proof grid]` | `proof grid matches bench/PROOF-GRID.md: yes` | PASS | |
| RejectBench table: Blocked, Repeat, Attempt, Judge per arm with Wilson intervals | README 208–214 | `knack bench report --runs bench/runs-1030c.jsonl --exclude-ticket fastapi-16049` | matches every cell; report matches `bench/REPORT-1030c.md`: yes | PASS (numbers) / FAIL (no early-signal mark; "Rejected path shipped" had no intervals) | added "early signal" sentence; added intervals 0% [0–14%], 0% [0–14%], 4% [1–20%] from the report |
| Primary set 72 runs, 24 per arm, excludes fastapi-16049 | README 208 | same report | `72 runs (excluding fastapi-16049)`, Runs = 24 per arm | PASS | |
| Muse Code 1.4.14, web off, design frozen in PREREGISTRATION | README 208 | `grep -n '1.4.14\|Web off' bench/PREREGISTRATION.md` | lines 24, 101 | PASS | |
| Guard arms each have 0/24 real repeats after the audit | README 255 | `grep -n 'real repeat\|real attempt' bench/AUDIT-1030c.md` (hand labels) | audit labels | FAIL (rate with no interval or early-signal mark) | added (0% [0–14%], Wilson 95%; early signal from 24 runs each) |
| fastapi-16049: 2 of 3 unguarded runs shipped the rejected path | README 259 | excluded-ticket table of the bench report | `none … 2 (67% [21–94%])` | FAIL (rate with no interval) | added 67% [21–94%], early signal from 3 runs |
| 21 of 81 runs hand-labelled | README 251 | `sed -n 5p bench/AUDIT-1030c.md` | `That is 21 of 81 runs.` | PASS | |
| Guard's one real block: `16049--veto--1` | README 64, 256 | `grep -n '16049--veto--1' bench/AUDIT-1030c.md` | found | PASS | |
| Blind judge wrong on all 5 #15937 runs it flagged | README 258 | `R[bench]`, Flagged runs | 5 #15937 rows, each `judge said yes; diff scored correct`; audit labels them correct | PASS | |
| RejectBench-Fresh not run: 1 of 5 candidates passed the screen | README 220 | `sed -n 6,7p bench/PREREGISTRATION-FRESH.md` | `The planned set was 5 tickets. 1 passed the screen` | PASS | |
| 12 rules hunted, 5068 commits, 0 repeats (0 human, 0 bot) | README 224 | `python -m knack.reproduce repeats` | same (reads `bench/REPEATS.md`) | PASS | |
| e2e 26/26 | README 228 | `bash scripts/e2e.sh` | 26 PASS lines | PASS | |
| Block verdict 17.3 ms (this run) | README 232; card 9; site figure, alt; console "17.3 ms to decide" | `jq .block.guard_ms mockups/fixtures/one_story/latency.json` | `17.321375002211425` | PASS | |
| Hook round trip 171 ms (this run) | README 232; card 9; site figure | `jq .wall_ms.block mockups/fixtures/one_story/latency.json` | `171.4` | PASS | |
| Across today's three live runs: 16.3–18.4 ms and 163–256 ms | README 232; card 9 | none: `spikes/one_story_live.md` 31–34 hand-quotes the two earlier runs; their outputs are not committed (site/SOURCES.md already leaves these out for that reason) | — | FAIL (no command) | softened: "the spike quotes …; the two earlier runs' outputs are not in the repo, so no command regenerates those ranges" (kept, because `tests/test_readme.py` and `tests/test_card.py` require both ranges) |
| 8 receipts, chain intact | site figure | `knack receipts verify --path mockups/fixtures/one_story/receipts.jsonl` | `8 receipts, chain intact` | PASS | |
| #75025: 8/8 checks | site caption; console "8/8 checks passed" | `R[proof grid]`, #75025 row; `pytest tests/console/test_verdict_page.py` | 8 PASS cells | PASS | |
| #75025: "0 false alarms" | site caption; console "0 false alarms on Airflow's code and release 3.3.2" | `jq -r '.rules[]\|select(.rule\|test("75025.yml$"))\|.proof.false_positives, .proof.old_release.ref, .proof.old_release.false_positives' data/registry/airflow.json` | `0`, `3.3.2`, `0` (`false_positives` = matches on the default branch outside the PR's files) | FAIL (unscoped: site said "0 false alarms"; console said "Airflow's code") | site: "(0 matches on Airflow's default branch and on release 3.3.2)"; console: "false alarms on Airflow's default branch and release 3.3.2" |
| Miss loop "False positives 0" | README 240–243 | `grep -h 'FP on' bench/misses/*bar2.log` | `0 FP on the default branch and release 0.140.0` / `0.140.12` | FAIL (unscoped header) | header: "False positives, default branch and release" |
| Miss loop: #16062 3 runs, first 2 kept; #15937 2 runs, first kept; held-out 2/3 (2) / 3/3 (3) and 3/3 (3) / 1/3 (1) | README 242–243 | `grep -h '^PASS held-out\|^FAIL held-out\|^installed\|^kept' bench/misses/*.log` | run1, run2 `kept the old fastapi-16062`; bar2 `installed`; #15937 `.log` kept, `.bar2.log` installed; held-out lines match | PASS | |
| #16062 rule: 0 matches on default branch and release 0.140.0 | README 267 | same log | `0 FP on the default branch and release 0.140.0` | PASS | |
| Pinned confirm: "Roots confirmed before pins existed, including the 2 committed ones, carry no pin" | README 91 | `jq -r '.id, .rule_sha' data/roots/airflow/75025.json data/roots/airflow/75774-1.json`; `shasum -a 256 data/rules/airflow/75025.yml` | `airflow-75025-1` has `rule_sha ecf207d0…`, equal to the rule file's sha256; `airflow-75774-1` has none | FAIL (wrong) | now: `airflow-75025-1` is pinned to the sha256 of its rule file; `airflow-75774-1` and `airflow-75774-2` are pinned to `1eba3b19…`, the sha256 of `data/rules/airflow/75774.yml`; `airflow-75271-1` and `airflow-75271-2` to `a7949850…` (`data/rules/airflow/75271.yml`); `fastapi-14884-1` to `babfafe9…` (`data/rules/fastapi/14884.yml`); `fastapi-15515-1` to `3f9de28f…` (`data/rules/fastapi/15515.yml`) |
| Spark Open gets 60 s on argue | README 75 | `grep -n SECOND_OPINION_TIMEOUT_SECONDS knack/pipeline/clients.py` | `SECOND_OPINION_TIMEOUT_SECONDS: float = 60` | PASS | |
| Held-out bar: ≥2 of 3 violations, all 3 compliant | README 73; site step 2 | `pytest -q tests/pipeline -k heldout` and `R[held-out]` pass/fail column | 2/3 caught + 3/3 allowed scores `pass`; 1/3 or <3/3 allowed scores `fail` | PASS | |
| All code written from Oct 26, 2026 | README 299 | `git log --reverse --format='%ad %s' --date=iso \| head -1` | `2026-10-26 16:00:32 -0400 Initial commit` | PASS | |
| Prior research done before the event (PRD, demo-chain analysis, prototype rule, Oct 25 test, hook-contract test) | README 299 | none | — | NO CMD, kept | a hackathon disclosure, not a result; removing it would hide prior work. Flagged for Vedant |

## Models, hosts and roles

| Claim | Where | Command | Output | Status | Fix |
|---|---|---|---|---|---|
| Muse Spark is `muse-spark-1.3` at api.meta.ai | site Models; spike | `grep -n 'MODEL\|URL' knack/pipeline/spark.py`; `jq -c '[.models[]]' mockups/fixtures/one_story/rulings.jsonl` | `muse-spark-1.3`, `https://api.meta.ai/v1/responses`; both rulings name it with host `api.meta.ai` | PASS | |
| Muse Spark Open is `meta-models/muse-spark-open-1026` on Baseten (inference.baseten.co) | README 150; site Models | `grep -n 'MODEL\|URL' knack/pipeline/spark_open.py`; same jq | `meta-models/muse-spark-open-1026`, `https://inference.baseten.co/…`; on the escalate ruling only | PASS | |
| Agent recorded as `muse-spark-1.3-contributor` from the payload's `model` | site Models | `jq -r .agent mockups/fixtures/one_story/rulings.jsonl` | `muse-spark-1.3-contributor` ×2 | PASS | |
| Spark held the first objection citing #75025's two sentences verbatim; escalated the second; Spark Open escalated too; a person upheld | site Models; README 49–50 | `jq -c '{decision, cited_quotes}' mockups/fixtures/one_story/rulings.jsonl`; `jq -c '.resolution // empty' mockups/fixtures/one_story/receipts.jsonl` | `hold` with the two sentences; `escalate` with both models; `uphold` by Vedant Srivastava | PASS | |
| Spark Open is asked only after Spark escalates | README 75; site | `pytest -q tests/test_readme.py -k provisional` and e2e "argue ESCALATE, second model disagrees: logged only" | pass | PASS | |
| Neither model is in the verdict path / no AI model in the check / no network | README 73, 144, 158; card 7, 15; site steps, Models lead; console "no AI model in the check" | `python -c "import sys, knack.hooks.pretool; print([m for m in sys.modules if m.startswith(('knack.pipeline','knack.dispute','knack.watch','urllib.request','http.client','ssl','httpx'))])"` and `PYTHONPATH=<dir with a sitecustomize.py that makes socket.socket raise> bash scripts/demo_block.sh` | `[]`; with every socket refused the real user-level hook still prints the full #75025 deny, exit 0 | PASS | |
| Fail open: a crashed guard lets the edit through and logs to `.knack/guard_errors.log` | README 73, 132 | `pytest -q tests/hooks/test_fail_open.py tests/hooks/test_pretool.py -k 'crash or import_failure'`; e2e "guard error fails open" | pass; 26/26 | PASS | |
| Prompt-injection safety | — | — | not claimed anywhere in the four surfaces (`grep -rni injection README.md docs site/index.html knack/console/templates` is empty) | N/A | none |

## The three promises

| Promise | Where | Command | Output | Status | Fix |
|---|---|---|---|---|---|
| Reads on its own: every merge runs the pipeline, `post-merge` or `PostToolBatch` | README 138–142 | `bash scripts/e2e.sh` ("watch on a real merge installs a new proven rule", fakes); `spikes/self_improving.md` (post-merge, live once); `spikes/posttoolbatch_live.md` | fakes PASS; post-merge live once: rule installed, no person; PostToolBatch live once: hook fired, watch stopped at `GITHUB_TOKEN is not set` | FAIL (unscoped: PostToolBatch has not run the pipeline live) | added what main shows live for each trigger; after the rebase on `6f81205`, cites the KN-113 rerun (next row) |
| PostToolBatch live (KN-113 rerun): the hook fired inside Muse Code; watch, with its keys only in `$KNACK_HOME` files, installed `rules/75271.yml` with no person involved; its root was Inferred, so the rule only advised until confirmed; `airflow-75271-1` and `airflow-75271-2` are now Confirmed by Vedant Srivastava and pinned to that rule, so it blocks | README 142 | `sed -n '/^## Rerun 2026-11-02 (KN-113)/,$p' spikes/posttoolbatch_live.md` (the committed record of one live run of `spikes/posttoolbatch_live_files.sh`; rerunning needs Muse Code and the three keys) | `hook_run_terminal … "event": "PostToolBatch" … "exit_code": 0`; watch.log `[5/5] install  1 rules proven, 0 discarded`; registry diff adds `rules/75271.yml`, root `airflow-75271-1`; root file `status` `Inferred`, `seeded` `false`; key search `0 files` for each key | PASS | new sentence in the "Every merge" bullet |
| Enforces on its own: the guard denies with a citation | README 144; card; site | `bash scripts/demo_block.sh`; `pytest -q tests/test_readme.py -k deny` | deny printed; README deny matches | PASS | |
| Argues on its own: Spark holds only by citing a Confirmed root verbatim, else a person | README 75, 146 | e2e "argue HOLD", "argue ESCALATE…"; `mockups/fixtures/one_story/rulings.jsonl` (live) | PASS; live hold and escalate | PASS | |
| Self-allow (KN-122): no model output can allow; the guard denies the direct and quoted person-only commands; `knack confirm` has `knack resolve`'s person check; a determined agent running as you can still get around it (variable, script, `python -c`); the CI knack-guard reads no local receipts, so a local allow never passes a PR | README 78, 133, 149, audit limits; card | `pytest -q tests/hooks/test_pretool.py -k person_only tests/roots/test_cli_correct.py -k terminal`; `grep -n receipts .github/workflows/knack-guard.yml .github/scripts/guard_changed.sh` | direct and quoted forms denied; confirm from a pipe without `--by` and `KNACK_HUMAN=1` exits 2; no receipts path in the CI guard | FAIL (wrong: README said only a person can allow and the guard keeps an agent out; `spikes/final_audit.md` BLOCKER 1 got past it) | scoped README 78, 133, 149 and card; added the audit's evasions to the limits |
| Repairs itself: a recorded case recompiles its rule; the self-check records cases with no person | README 142–143 | e2e "self-check records a case only when both models agree", "miss recorded, recompiled, re-proved, installed" (fakes); `bench/misses/*.log` (real models) | fakes PASS; the real-model repairs were run with `knack miss` on 2026-10-31 (commit `8ddf61e`), before the self-check existed (`f60fdf6`) | FAIL (unscoped: no live unattended repair on main) | added "What main proves about self-repair today …" to the miss-loop bullet |

## Console fixed copy

| Copy | Where | Status |
|---|---|---|
| "Waiting for the next block. When the guard stops an edit, it opens here." | `templates/waiting.html` | no factual claim |
| "Confirmed decisions" | `templates/day.html` | heading; e2e "console /verdict and /rulings JSON" |
| "A person decides. A human runs this, with a reason:" | `partials/resolve.html` | matches `knack resolve … --reason` (README 77) |
| "Verify it … Receipt … `knack receipts verify --path …`" | `partials/verify.html` | `tests/console/test_verdict_page.py` |
| "8/8 checks passed", "0 false alarms on …", "17.3 ms to decide, no AI model in the check" | `pages/verdict.py` | see the rows above |

## TODO

- [ ] Recheck the self-repair wording in README "Runs unattended" after `spikes/self_repair_live.md` (branch `spike/kn-97-self-repair-live`) merges: if it shows a live merge → self-check case → recompile → install with no person, replace "No live unattended repair is in the repo yet" with what it proves, and add a row here with its command.
- [ ] `site/block-0e7ab6083866-1080p.png` and `-390.png` still show the old console label "0 false alarms on Airflow's code and release 3.3.2". Recapture with `mockups/tools/capture_block.mjs`. The console's own test baselines were re-shot on this branch.
