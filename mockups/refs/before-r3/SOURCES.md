# Where every visible value comes from (round 3)

`fixtures/freeze.py` copies each field from its source into `fixtures/scenes.json` and `fixtures/scenes.js`. No value is typed by hand. To refreeze, run `.venv/bin/python mockups/fixtures/freeze.py`.

On load, `final.html` checks itself. Every bound element carries `data-src="<field>"`. Each verbatim value must appear in that field, and a value that doesn't logs `truth: not in fixture` as a console error. The last capture checked 59 bindings in each of the six stills, with 0 missing and 0 console errors.

## Block

| Shown | Field | Source |
|---|---|---|
| 18.7 ms verdict, 212 ms PreToolUse round trip | `block.verdict_ms`, `block.round_trip_ms` | `bench/demo_block.log`, lines "guard verdict:" and "hook round trip:". The file is gitignored on this branch; it is read with `git show b8c3032:bench/demo_block.log` |
| ast-grep | `block.scan` | same log: "(ast-grep scan, from the deny receipt)" |
| 0 model calls in this hook | `block.no_model` | same log, first line: "No model, no network." |
| Quote, with the underlined phrase | `root.quote` | `data/roots/airflow/75025.json`, identical to the deny reason's `Quote:` line in the log |
| Pushkal Gupta, approved by bbovenzi | `root.decided_by` | `data/roots/airflow/75025.json` "decided_by", split at "(author)" and "merged by" |
| apache/airflow #75025 | `root.source_url` | same root |
| merged Oct 19 2026, the postmark date, the left header's date | `root.merged_at` | same root, 2026-10-19T21:36:02Z, shown as a UTC date |
| Postmark start date (Nov 01 2026) | `day.date` | `mockups/fixtures/day.json` |
| Left column: `public 132`, `ui 139` | `rejected_base` | base side of `scripts/fixtures/75025/{base,head}` for `routes/public/dags.py` and `routes/ui/dags.py`, the fixture `scripts/demo_block.sh` copies into its clone. These are the lines #75025 removed |
| Right column: `public 135`, `public 136` | `block.attempted` | line numbers and text from the log's `Matched:` line. The code is from `tests/guard/fixtures/replay/run_neutral_3.diff`, numbered on the new side of the hunk |
| Root airflow-75025-1, Confirmed, not seeded | `root.id`, `root.status`, `root.seeded` | same root |
| Gap: confirmed_by is not recorded | `root` (no `confirmed_by` key); `day.seats[0].confirmed_by` is null | same root, and `day.json` |
| Gates, ticked | `grid.gates`, `grid.cells` | `bench/PROOF-GRID.md`: the header row (the grid `scripts/reproduce.sh` regenerates and diffs) and the #75025 row, all PASS |
| 0 FP on Airflow current tree and previous release | `grid.cells` "0 FP tree" and "0 FP release" | grid row; the previous release is 3.3.2 (`proof.old_release`, from `data/registry/airflow.json`) |
| Receipt 80b311c17a39 | `block.receipt` | the log's `Console: …/verdict/<hash>` line |

## Day

| Shown | Field | Source |
|---|---|---|
| apache/airflow, main, Nov 1 2026 | `day.repo`, `day.branch`, `day.date` | `mockups/fixtures/day.json`, a frozen `knack day --json` |
| Seats (Pushkal Gupta #75025, stegololz #75774) | `day.seats` | same file, which reads the registry's Confirmed roots (`knack/day/seats.py`). Filled means today's receipt cites the root; empty means it is in the record only |
| Last receipt line | `day.events[1]` | same file: kind, time, root, decider and hash |
| Verify command | `readme.verify` | `README.md`, the code block under "From the clone": `bash scripts/reproduce.sh` |

## Argue and held

| Shown | Field | Source |
|---|---|---|
| Objection, ruling text, kind, time, receipt | `escalate.*`, `hold.*` | `~/.knack/rulings.jsonl`, receipts `1983f52b…` (escalate) and `13f19d15…` (hold) |
| Cited quote | `*.cited_quotes[0]` | same trace; it equals `root.quote`, hence "the record holds no other words on this" |
| Muse Spark (api.meta.ai) | `*.model` and `spark.host` | the trace's `"model": "muse-spark-1.3"`; the host is from `knack/pipeline/spark.py` `URL` |
| Resolve command | `readme.resolve` with the receipt filled in | `README.md`: "`knack resolve <receipt> allow\|retire --reason`". The command exists at tag `freeze-2026-11-01` (`knack/cli.py`, `"resolve"`) |
| 37 receipts, chain intact | `receipts_verify` | the output of `.venv/bin/knack receipts verify` at freeze time |

## Recovery

| Shown | Field | Source |
|---|---|---|
| Lede: repo, tiangolo, Inferred | `miss.root` | `data/roots/fastapi/16062-1.json` |
| tier warn | `miss.tier` | `bench/PROOF-GRID.md`, #16062 row |
| Steps 1, 3 and 4 | `miss.bar2_log` | `bench/misses/16062-none-2.bar2.log`, verbatim lines |
| Step 2 | `miss.run1_log`, `miss.run2_log` | `bench/misses/16062-none-2.run1.log` and `.run2.log` |
| `_CALLABLE_CACHE_SIZE` lines, and the "rebuilt" note | `miss.edit_after`, `miss.edit_note` | `bench/misses/16062-none-2.edit.json` |
| Cases on record | `miss.cases` | the listing of `data/registry/cases/fastapi-16062/` |
| Two gaps | none | see NOTES.md |
