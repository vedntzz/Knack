# Landing: where every visible value comes from

`K` is `window.KNACK` (`mockups/fixtures/scenes.js`), `B` is `window.BLOCK` (`mockups/fixtures/block.js`) and `R` is `window.README` (`mockups/fixtures/readme.js`, frozen by `freeze_readme.py`). The hero image is `mockups/shots/kn80/verdict-1080p.png`, the block page's 1080p capture, as the brief names it. Audited against `shots/landing/landing-720p-fullpage.png`, `-1080p-fullpage.png` and `-390-fullpage.png`.

**Two receipts, labelled, not merged.** The capture comes from its own demo run: receipt `5e8a44648bd0` and 16.5 ms, both read off the image. Every figure in the text comes from `block.js`: receipt `80b311c17a39` and 18.7 ms. The caption says so.

| On the page | Source | Note |
|---|---|---|
| Headline | the brief's copy | |
| `bash scripts/reproduce.sh` + Copy (hero, Check it) | `K.readme.verify` | Regenerates the proof grid byte for byte (see `scripts/reproduce.sh`, header) |
| The hero picture | `shots/kn80/verdict-1080p.png` | Alt text describes what the image shows |
| Caption: receipt 5e8a44648bd0 | read from the capture's bar | The capture is the source |
| Caption: receipt 80b311c17a39 | `B.proof.receipt`, first 12 | |
| “I removed them rather than aliasing them onto `DagRun.state` and `DagRun.start_date`.” | `K.root.quote` | Complete as the root records it. The PR paragraph has two more sentences; they are on the block page in the hero image. |
| Gold underlines on `DagRun.state`, `DagRun.start_date` | the quote's code spans ∩ `B.attempted.matched` | |
| Pushkal Gupta | `B.person.name` | |
| #75025 and its link | `K.root.source_url` | |
| merged Oct 19 2026 | `K.root.merged_at` | |
| Rule `airflow-75025` | `B.where.rule` | |
| 8 of 8 gates, and the eight names | `B.proof.grid.gates`, `B.proof.grid.cells` | |
| "Stored by knack reprove on Oct 31 2026" | `B.proof.grid.evidence` ("knack reprove 2026-10-31") | |
| Blocked, lines 135–136 and their code | `B.attempted.rows` where `new` ∈ `B.where.lines` | |
| 18.7 ms, ast-grep, "No model, no network." | `B.proof.verdict_ms`, `B.proof.scan`, `B.proof.no_model` | Verbatim |
| 212 ms round trip | `B.proof.round_trip_ms` | |
| Muse Code: host not recorded | none | Gap |
| `PreToolUse` hook on `edit_file` | `B.where.hook`, `B.where.tool` | |
| The agent's name not recorded | none | Gap |
| Muse Spark: api.meta.ai, `muse-spark-1.3` | `K.spark.host`, `K.spark.model` | |
| ruled hold; ruled escalate | `K.hold.model`, `K.escalate.model` equal `K.spark.model` | |
| recompiled fastapi-16062 | `K.miss.bar2_log`: "recompiling with muse-spark-1.3" | |
| extracted fastapi-16062-1 | `K.miss.root.models` contains `muse-spark-1.3`; `K.miss.root.id` | |
| Muse Spark Open: Baseten, inference.baseten.co, `meta-models/muse-spark-open-1026` | `K.spark_open.host`, `K.spark_open.model` | "Baseten" is the brief's name for that host |
| Spark Open run not recorded | none | Gap: no trace in the fixtures shows Spark Open at work |
| Each model's job | the brief's copy | Product description, not data |
| 0 false alarms on Airflow's current tree and release 3.3.2 | `K.proof.fp`, `K.proof.old_release` | |
| 37 receipts, chain intact | `K.receipts_verify`, split at the first comma | |
| `knack receipts verify` + Copy | the command whose output `K.receipts_verify` freezes | As on argue and held |
| Install: the four lines from `git clone https://github.com/vedntzz/Knack.git` to `source .venv/bin/activate`, + Copy | `R.install`: README.md lines 27–30, the `sh` block under “Get it running” | Verbatim; Copy copies all four lines |
| `https://github.com/vedntzz/Knack.git` (bar, footer) | `R.repo`: README.md line 27, the `git clone` URL | Verbatim, `.git` kept |
| Demo video slot | the brief's slot | Nothing recorded |
| fonts IBM Plex, SIL Open Font License | `knack/console/static/fonts/OFL.txt` | Credit line, not data |
