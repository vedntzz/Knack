# Landing: where every visible value comes from

`README` is `README.md` at the line given. `SPIKE` is `spikes/one_story_live.md`. `ONE` is `mockups/fixtures/one_story/`, the frozen output of the live run on 2026-11-02, 14:44:38Z to 14:45:07Z. `REPAIR` is `spikes/self_repair_live.md`, and `SR` is `mockups/fixtures/self_repair/`, the frozen output of the live model-assisted repair of airflow-75025 on 2026-11-02, 19:57:19Z to 21:10:07Z. Nothing on the page is loaded from these at runtime: each value is written into `index.html`, and `tests/test_site.py` checks it against its source.

## The page

| On the page | Source | Checked by |
|---|---|---|
| Headline “Your AI agent never read the PR where you said no. Knack did.” | the brief's copy | `test_the_hero_is_the_headline_alone_then_the_block_capture` |
| The picture, `block-0e7ab6083866-1080p.png` | The block page for receipt `0e7ab6083866`, captured at 1920×1080 with reduced motion (the final frame) from the README's console command (README 43) by `mockups/tools/capture_block.mjs` | `test_the_capture_is_the_one_story_block_page_at_1080p` |
| Caption: receipt `0e7ab6083866`, `knack console`, Nov 2 2026 | README 5; `ONE/latency.json` `.block.receipt`; the capture's own bar | |
| The picture on a phone, `block-0e7ab6083866-390.png` | The same page from the same command, in the console's own phone layout: 390×844 at 2x, reduced motion | `test_a_phone_gets_the_block_page_as_served_at_390` |
| Caption: its 8/8 checks, including zero matches outside the PR’s changed files in the scanned snapshots (Airflow’s default branch and release 3.3.2), are the #75025 row of `bench/PROOF-GRID.md`; `bash scripts/reproduce.sh` regenerates it byte for byte | `bench/PROOF-GRID.md` line 14 (8 gates PASS, including “0 FP tree” and “0 FP release”); `data/registry/airflow.json` #75025 `.proof.false_positives` = 0 (default branch, outside the PR's files) and `.proof.old_release` = 3.3.2 with 0; README 168 (“regenerates the grid… fails if it differs from the committed file by a byte”) | `test_the_caption_sources_the_captures_own_figures` |
| Alt text | What the capture shows, read off it | `test_the_capture_has_alt_text` |
| `<title>` and meta description: “Knack blocks AI coding agents from edits that contradict…” | README 3, verbatim | |
| Section: “Three promises, and the run behind each”; each record is committed, from a run with the real Meta models, and says what it does not prove | The three records below: SPIKE 3 (Spark and Spark Open, live); `spikes/self_improving.md` 121 (real Spark and Spark Open); REPAIR 3 (real Spark and Spark Open made every model call) | `test_each_promise_links_the_run_that_shows_it`, `test_each_proof_says_what_it_does_not_prove` |
| **Promise 1**, “It stops the edit, and cites who said no.” Its times 14:44:38, 14:44:47, 14:44:56, 14:45:07, 14:45:07 (UTC, Nov 2 2026) | `ONE/receipts.jsonl` `.time` (the block 14:44:38.375, the uphold 14:45:07.067, the corrected edit's allows from 14:45:07.254) and `ONE/rulings.jsonl` `.time` (hold 14:44:47.121, escalate 14:44:56.725), to the second | `test_every_time_in_the_story_is_a_time_the_run_recorded` |
| “Blocked”, the edit put back two sort keys #75025 removed, receipt `0e7ab6083866` | SPIKE 9; the block page; `ONE/latency.json` `.block.receipt` | |
| The first objection, verbatim, and “Spark held, citing #75025’s two sentences verbatim” | `ONE/rulings.jsonl` `.objection` on the hold; SPIKE 10 | |
| The second objection, paraphrased (“the REST API is public, so removing sort values may need a deprecation cycle”); Spark escalated, Spark Open asked separately agreed, held for a person | `ONE/rulings.jsonl` `.objection` on the escalate, shortened; SPIKE 11 | |
| “Upheld by Vedant Srivastava” and the reason on paper, verbatim | SPIKE 12; `ONE/story.json` step `resolve` | `test_the_uphold_on_paper_is_the_persons_reason_verbatim` |
| “The corrected edit, lines 135–136 deleted, was allowed.” | SPIKE 13 | |
| Rail: 171 ms hook round trip, of which 17.3 ms is rule evaluation, no model and no network; Pushkal Gupta’s words; Spark holds only by quoting a confirmed decision verbatim; both models escalated and a person decided | SPIKE 20; README 73; README 75; SPIKE 11–12 | |
| “One run on one laptop. Recorded edit replay; real hook, real model calls: the edits were inserted into a captured Muse Code hook payload, and the rulings were live.” | SPIKE 3, 5, 37 | |
| **Promise 2**, “It learns each new decision from a local merge.” dabla’s quote on paper, apache/airflow #75271 | `data/roots/airflow/75271-1.json` `.quote` and `.decided_by`, verbatim (backticks set as code) | `test_every_quote_on_paper_is_its_roots_quote_verbatim` |
| The log, from `$ git merge --ff-only pr-75271` to `[5/5] install` | `spikes/self_improving.md` 142–159, each line verbatim; the fast-forward diffstat lines and the `exit 0`/hook lines around them are left out | `test_every_log_line_shown_is_verbatim_in_its_run` |
| Rail: post-merge hook installed by `knack watch`; Spark extracted, Spark Open wrote code to break and follow it; proven and installed; “No one typed anything between the merge and the install.” | `spikes/self_improving.md` 167, 245–254 (`writers.json`: compiler Spark, variants and held-out Spark Open) | |
| “Decision, Confirmed: …” for #75271 | `data/roots/airflow/75271-1.json` `.status` and `.decision`, verbatim | `test_each_learned_rule_states_its_roots_decision_and_label` |
| “Decided in #75271 by @dabla · confirmed in Knack by @vedntzz after reading the full thread.” | `data/roots/airflow/75271-1.json` `.decided_by` (dabla) and `.confirmed_by` (Vedant Srivastava, @vedntzz). “After reading the full thread” is the confirmer’s statement; no committed record shows it (`confirmed_at` is empty) | |
| “Its two roots were Inferred when the rule installed, so it only advised. @vedntzz has since run `knack confirm` on both, so it now blocks.” | `spikes/self_improving.md` 297 (written Inferred); `data/roots/airflow/75271-1.json` and `75271-2.json` `.status` `Confirmed`, `.confirmed_by` Vedant Srivastava, `.rule_sha` = sha256 of `data/rules/airflow/75271.yml`; CLAUDE.md (only Confirmed roots block) | `test_each_proof_says_what_it_does_not_prove` |
| **Promise 3**, “When it misses, a person starts a model-assisted repair, and every gate re-proves it.” “Decision, Confirmed: …” | `data/roots/airflow/75025.json` `.status` and `.decision`, verbatim | `test_each_learned_rule_states_its_roots_decision_and_label` |
| “Decided in #75025 by Pushkal Gupta (author; approved and merged by @bbovenzi) · confirmed in Knack by @vedntzz after reading the full thread. The quote reads as a preference, and @vedntzz confirmed it as policy for this demonstration.” | `data/roots/airflow/75025.json` `.decided_by` and `.confirmed_by`; the quote ends “Happy to alias instead if you would rather keep the advertised names working.” “After reading the full thread” is the confirmer’s statement, not a committed record | |
| Its times 19:57:20, 19:57:20, 20:01:46, 21:09:27, 21:10:07 (UTC, Nov 2 2026) | `SR/receipts.jsonl` `.time` (the evasion's allow 19:57:20.350, the false alarm's deny 19:57:20.588, the evasion's deny 21:10:07.154); `SR/corrections.jsonl` `.at` (the second confirm, 21:09:27); the passing candidate's own stamp, `SR/rule/candidate-20261102T200146Z-c9845e.yml`. To the second | `test_every_time_in_the_repair_is_a_time_the_run_recorded` |
| The first confirm's time: “not recorded” | The rolled-back confirm left no correction line (`SR/SOURCES.md`; REPAIR 77). REPAIR 106 says it ended at about 20:02Z; an approximate time is not shown as a recorded one | `test_every_time_in_the_repair_is_a_time_the_run_recorded` |
| The evasion v1 allowed, `dict(state=DagRun.state, start_date=DagRun.start_date)`, receipt `b27a4e112756` | REPAIR 11, 39; `SR/receipts.jsonl` (`allow` on `public/dags.py`); `SR/edits/miss.after.py` | `test_each_repair_receipt_shown_is_the_runs` |
| The false alarm, receipt `f679bf658d9f`; `compliant_3.py` “a file Spark Open wrote to follow the decision” | REPAIR 12, 40; `SR/receipts.jsonl` (`deny` on `public/dag_sort_keys.py`) | `test_each_repair_receipt_shown_is_the_runs` |
| `compliant_3.py` on paper, eight lines, and its caption | `SR/cases/must-pass-6633cbc47011.json` `.after`, verbatim; `.source` is the deny receipt. Paper because a person had to act on it (DESIGN: “a person wrote or must act on this”); the caption names who wrote it, Spark Open (REPAIR 12) | `test_the_false_alarm_on_paper_is_compliant_3_verbatim` |
| “A person ran `knack false-block` on that receipt”; “Its second attempt”; “kept 6 matcher branches, dropped 1 and added 5; the one dropped is the branch that flagged `compliant_3.py`” | REPAIR 42 (2 attempts), 19, 21, 23–29, 110; the counts are `rule.any` in `SR/rule/v1.yml` (7) and `SR/rule/v2.yml` (11), compared branch by branch | `test_the_repair_counts_are_the_rule_diff` |
| The false-block log | `SR/traces/steps/04_04_knack_false_block.txt`, lines 4–10, verbatim (the gate lines, including the fresh cross-model line's sandbox path as it ran). The `recorded must-pass case` line, the `candidate rule:` line and the `installed …` line are left out: the prose says both edits became cases and the rule was installed | `test_every_log_line_shown_is_verbatim_in_its_run` |
| The first confirm: `knack confirm airflow-75025-1` by Vedant Srivastava; the gate re-read #75025 and #75774 with Spark; #75774’s re-read lost a rejected alternative; rolled back | REPAIR 5, 43, 102; `SR/models.jsonl` (two `SparkApi` calls on `05_knack_confirm`) | |
| Its log, including `exit 1, wall 30141.8 ms` | `SR/traces/steps/05_05_knack_confirm.txt`, lines 3–5 and 7, verbatim | `test_every_log_line_shown_is_verbatim_in_its_run` |
| “The same command, retried once with the gate, passed. The root is pinned to rule `865e1a983ffe`.” | REPAIR 5, 44, 86; `SR/corrections.jsonl` `.after.rule_sha` = `SR/rule/root_after.json` `.rule_sha` | `test_the_pin_shown_is_the_second_confirms` |
| Its log, including `exit 0, wall 39593.5 ms` | `SR/traces/steps/10_05b_knack_confirm_retry.txt`, lines 3–4 and 6, verbatim | `test_every_log_line_shown_is_verbatim_in_its_run` |
| “Blocked”, the same evasion denied, matching on line 89, receipt `66a1c247a7e3`; `compliant_3.py` and the corrected edit allowed | REPAIR 31, 45–47; `SR/traces/steps/11_06_evasion_denied.txt` (`Matched: …`); `SR/receipts.jsonl` | `test_each_repair_receipt_shown_is_the_runs` |
| Rail: the two mistakes; the gates the repair passed; `compliant_3.py` a permanent must-pass case | REPAIR 11–12; the log's PASS lines; REPAIR 12 (`data/registry/cases/airflow-75025/`) | |
| “Started by a person: a script recorded the missed edit, and Knack’s author ran `knack false-block` and both confirms. Recorded edit replay; real hook, real model calls: the edits were inserted into a captured Muse Code hook payload, and the models were live. The unattended path, from a self-check case to an install, has run only with fake models, in the end-to-end test.” | REPAIR 110 (“It is not unattended. A driver recorded the must-fail case, and a person ran…”); REPAIR 7; REPAIR 3; README 145 (“The unattended path still runs only with fakes. No live unattended repair is in the repo yet.”) | `test_each_proof_says_what_it_does_not_prove` |
| “The run: `spikes/self_repair_live.md`” | REPAIR. No link to `/recovery/airflow-75025`: that console route is not on main yet | `test_each_promise_links_the_run_that_shows_it` |
| “The models are in the proof loop… They are not in the verdict path.” | README 73, verbatim | |
| Muse Spark: `muse-spark-1.3` at api.meta.ai | `ONE/rulings.jsonl` `.models[]` on both rulings; SPIKE 3 | `test_every_model_that_ruled_is_named_with_its_host` |
| Muse Spark's job | README 69 (extract, compile); README 75 (may hold only by citing words verbatim in a Confirmed root) | |
| Held the first objection, citing #75025's two sentences verbatim; escalated the second | SPIKE 10–11; `ONE/rulings.jsonl` `.decision`, `.cited_quotes` | |
| Muse Spark Open: `meta-models/muse-spark-open-1026` at inference.baseten.co | `ONE/rulings.jsonl` `.models[]` on the escalate ruling; SPIKE 3 | `test_every_model_that_ruled_is_named_with_its_host` |
| Muse Spark Open's job | README 71 (same PRs, Corroborated, held-out variants); README 75 (asked only after Spark escalates) | |
| Asked after Spark escalated, escalated too; a person upheld the decision | SPIKE 11–12; the uphold receipt in `ONE/receipts.jsonl` (`.resolution.action` = `uphold`) | |
| Muse Code: the coding agent; your machine, hooks in `~/.config/muse/settings.json`; `write_file` and `edit_file` | README 206 (“a real coding agent (Muse Code 1.4.14…)”); README 99; README 107 (the matcher); “Knack also uses UserPromptSubmit and PostToolBatch, which fires after an agent’s tool batch (including a local merge), not on a GitHub merge event”: README 137 | |
| Recorded as `muse-spark-1.3-contributor`, from the hook payload's `model` field | SPIKE 5; `ONE/rulings.jsonl` `.agent` | `test_the_agent_is_named_as_the_rulings_record_it` |
| “live run”, links to the spike on GitHub | SPIKE | |
| “One run on one laptop: this is not a distribution.” | SPIKE 37 (“Three runs on one laptop… This is not a distribution.”), narrowed to the one run whose output is in the repo | |
| **17.3 ms** for rule evaluation on the block, the ast-grep scan, inside the hook’s round trip | SPIKE 20; `ONE/latency.json` `.block.guard_ms` = 17.321375002211425, rounded | `test_the_guard_figure_is_what_its_command_prints_rounded` |
| `jq .block.guard_ms mockups/fixtures/one_story/latency.json` + Copy, prints `17.321375002211425` | README 230 | `test_every_copied_command_is_written_in_the_readme` |
| **171 ms** for the hook's round trip: `sh -c`, Python start and the deny | SPIKE 18, 21; `ONE/latency.json` `.wall_ms.block` = 171.4, rounded | `test_the_round_trip_figure_is_what_its_command_prints_rounded` |
| `jq .wall_ms.block mockups/fixtures/one_story/latency.json` + Copy, prints `171.4` | README 230 | |
| **8 receipts**, chain intact; the verdicts on both edits and the uphold, each linked to the one before | SPIKE 14; `ONE/receipts.jsonl` (7 guard verdicts and 1 uphold, each `.prev` is the previous `.hash`); “Tamper-evident for edits and middle deletions, not truncation”: README 274, `spikes/final_audit.md` LATER 4 | `test_the_receipts_figure_is_what_its_command_prints` (runs it) |
| `knack receipts verify --path mockups/fixtures/one_story/receipts.jsonl` + Copy, prints `8 receipts, chain intact` | README 230 | |
| Install: `git clone https://github.com/vedntzz/Knack.git` to `bash scripts/reproduce.sh`, five lines, + Copy | README 29–33, verbatim; Copy copies all five lines | `test_install_is_the_readmes_setup_block_with_copy` |
| Needs git, uv, jq and Python 3.11; `PROOF: PASS`; about 70–80 s once installed | README 26; README 36 | |
| `KNACK_CONSOLE_RECEIPTS=$PWD/mockups/fixtures/one_story/receipts.jsonl KNACK_REGISTRY=$PWD/data/registry/airflow.json knack console` + Copy | README 43, verbatim | `test_the_console_command_is_the_readmes_with_copy` |
| Reads no `~/.knack`, needs no API keys, binds to loopback only | README 40 | |
| The block, the argument Spark held, the one a person upheld, the repo's memory (four loopback links) | README 48–51 | `test_every_console_link_in_the_readme_is_on_the_page` |
| `github.com/vedntzz/Knack` (bar, Run it, footer) | README 29, the clone URL without `.git` | `test_the_repo_link_is_the_readmes_clone_url` |
| Demo video, 16:9, not recorded yet | the brief's slot; nothing recorded | `test_the_demo_slot_is_labelled` |
| MIT License | `LICENSE` | |
| IBM Plex, SIL Open Font License | `fonts/OFL.txt`, a byte copy of `knack/console/static/fonts/OFL.txt` | `test_tokens_and_fonts_are_the_consoles_byte_for_byte` |

## Assets

- `tokens.css` and `fonts/` are byte copies of `knack/console/static/tokens.css` and `knack/console/static/fonts/`; the test fails if they drift.
- Nothing is fetched from another host at runtime. The fonts are self-hosted. The only outside URLs are anchors: github.com, and the loopback console a visitor starts themselves.

## Left out, and why

- **Today's ranges (16.3–18.4 ms, 163–256 ms):** SPIKE 22–23 quotes them, but the two earlier runs' outputs are not in the repo, so no command prints them.
- **A repair loop that ran unattended with real models:** none is in the repo (README 145), so the third promise shows the person-started live repair and says so.
- **The hand-started #16062 repair** (`bench/misses/16062-none-2.bar2.log`): replaced by the live airflow-75025 repair, which shows a miss and a false alarm fixed in one recompile, every gate line, and the person's confirm.
- **Held-out same, 2/3 before and after** (REPAIR 112): its PASS line is in the log as printed (“old rule 2”); the rail claims only that the repair caught as much, not more.
- **The console route `/recovery/airflow-75025`:** not on main, so the third promise does not link it.
- **The corrected edit's 17.0 ms and 198 ms:** true and checkable, left out so the block is the one story the numbers tell.
