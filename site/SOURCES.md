# Landing: where every visible value comes from

`README` is `README.md` at the line given. `SPIKE` is `spikes/one_story_live.md`. `ONE` is `mockups/fixtures/one_story/`, the frozen output of the live run on 2026-11-02, 14:44:38Z to 14:45:07Z. Nothing on the page is loaded from these at runtime: each value is written into `index.html`, and `tests/test_site.py` checks it against its source.

## The page

| On the page | Source | Checked by |
|---|---|---|
| Headline “Your AI agent never read the PR where you said no. Knack did.” | the brief's copy | `test_the_hero_is_the_headline_alone_then_the_block_capture` |
| The picture, `block-0e7ab6083866-1080p.png` | The block page for receipt `0e7ab6083866`, captured at 1920×1080 with reduced motion (the final frame) from the README's console command (README 43) by `mockups/tools/capture_block.mjs` | `test_the_capture_is_the_one_story_block_page_at_1080p` |
| Caption: receipt `0e7ab6083866`, `knack console`, Nov 2 2026 | README 5; `ONE/latency.json` `.block.receipt`; the capture's own bar | |
| The picture on a phone, `block-0e7ab6083866-390.png` | The same page from the same command, in the console's own phone layout: 390×844 at 2x, reduced motion | `test_a_phone_gets_the_block_page_as_served_at_390` |
| Caption: its 8/8 checks and 0 false alarms (0 matches on Airflow’s default branch and on release 3.3.2) are the #75025 row of `bench/PROOF-GRID.md`; `bash scripts/reproduce.sh` regenerates it byte for byte | `bench/PROOF-GRID.md` line 14 (8 gates PASS, including “0 FP tree” and “0 FP release”); `data/registry/airflow.json` #75025 `.proof.false_positives` = 0 (default branch, outside the PR's files) and `.proof.old_release` = 3.3.2 with 0; README 168 (“regenerates the grid… fails if it differs from the committed file by a byte”) | `test_the_caption_sources_the_captures_own_figures` |
| Alt text | What the capture shows, read off it | `test_the_capture_has_alt_text` |
| “Knack blocks AI coding agents from edits that contradict…” | README 3, verbatim | |
| Step 1, Spark reads the pull requests | README 69 | |
| Step 2, Spark Open tries to break the rule; “at least 2 of 3 violating variants and allows all 3 compliant ones” | README 71 (variants, Spark never sees them); README 73 (the bar, verbatim) | |
| Step 3, plain code stops the edit; “no model and no network”; only a confirmed decision blocks; who decided, why, and the verbatim quote | README 73; README 89; README 3 | |
| “The models are in the proof loop… They are not in the verdict path.” | README 73, verbatim | |
| Muse Spark: `muse-spark-1.3`, api.meta.ai | `ONE/rulings.jsonl` `.models[]` on both rulings; SPIKE 3 | `test_every_model_that_ruled_is_named_with_its_host` |
| Muse Spark's job | README 69 (extract, compile); README 75 (may hold only by citing words verbatim in a Confirmed root) | |
| Held the first objection, citing #75025's two sentences verbatim; escalated the second | SPIKE 10–11; `ONE/rulings.jsonl` `.decision`, `.cited_quotes` | |
| Muse Spark Open: `meta-models/muse-spark-open-1026`, inference.baseten.co | `ONE/rulings.jsonl` `.models[]` on the escalate ruling; SPIKE 3 | `test_every_model_that_ruled_is_named_with_its_host` |
| Muse Spark Open's job | README 71 (same PRs, Corroborated, held-out variants); README 75 (asked only after Spark escalates) | |
| Asked after Spark escalated, escalated too; a person upheld the decision | SPIKE 11–12; the uphold receipt in `ONE/receipts.jsonl` (`.resolution.action` = `uphold`) | |
| Muse Code: the coding agent; your machine, hooks in `~/.config/muse/settings.json`; `write_file` and `edit_file` | README 206 (“a real coding agent (Muse Code 1.4.14…)”); README 99; README 107 (the matcher) | |
| Recorded as `muse-spark-1.3-contributor`, from the hook payload's `model` field | SPIKE 5; `ONE/rulings.jsonl` `.agent` | `test_the_agent_is_named_as_the_rulings_record_it` |
| “live run”, links to the spike on GitHub | SPIKE | |
| “One run on one laptop: this is not a distribution.” | SPIKE 37 (“Three runs on one laptop… This is not a distribution.”), narrowed to the one run whose output is in the repo | |
| **17.3 ms** for the guard to decide the block, the ast-grep scan | SPIKE 20; `ONE/latency.json` `.block.guard_ms` = 17.321375002211425, rounded | `test_the_guard_figure_is_what_its_command_prints_rounded` |
| `jq .block.guard_ms mockups/fixtures/one_story/latency.json` + Copy, prints `17.321375002211425` | README 230 | `test_every_copied_command_is_written_in_the_readme` |
| **171 ms** for the hook's round trip: `sh -c`, Python start and the deny | SPIKE 18, 21; `ONE/latency.json` `.wall_ms.block` = 171.4, rounded | `test_the_round_trip_figure_is_what_its_command_prints_rounded` |
| `jq .wall_ms.block mockups/fixtures/one_story/latency.json` + Copy, prints `171.4` | README 230 | |
| **8 receipts**, chain intact; the verdicts on both edits and the uphold, each linked to the one before | SPIKE 14; `ONE/receipts.jsonl` (7 guard verdicts and 1 uphold, each `.prev` is the previous `.hash`) | `test_the_receipts_figure_is_what_its_command_prints` (runs it) |
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
- **The corrected edit's 17.0 ms and 198 ms:** true and checkable, left out so the block is the one story the numbers tell.
