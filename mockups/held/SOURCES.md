# Held: where every visible value comes from

`K` is `window.KNACK` from `mockups/fixtures/scenes.js`; `B` is `window.BLOCK` from `mockups/fixtures/block.js`. Nothing else is read. Audited against `shots/held/held-720p.png` and the 390 px page, final build.

| On the page | Fixture path | Note |
|---|---|---|
| apache/airflow | `B.where.repo` | |
| main | `B.where.branch` | |
| routes/public/dags.py | `B.where.file`, last three segments | |
| 1983f52b4751 (bar) | `K.escalate.receipt_hash`, first 12 | The ruling's receipt, not the block's |
| Oct 31 2026, 18:18:46 UTC | `K.escalate.time` | |
| 135, 136 and their code | `B.attempted.rows` where `kind = add` and `new` is in `B.where.lines` | |
| Gold tokens `DagRun.state`, `DagRun.start_date` | `B.attempted.matched[].text`, intersected with the quote's code spans | |
| Blocked, receipt 80b311c1 | `B.proof.receipt`, first 8 | The block's receipt, labelled as such: a different receipt from the ruling's |
| The three quote sentences | `B.quote.sentences` (two) and `B.quote.not_recorded` (one) | Verbatim, complete |
| Sentence 1 in full ink | `K.escalate.cited_quotes[0]` equals `B.quote.sentences[0]` | Matched at runtime |
| Pushkal Gupta | `B.person.name` | |
| merged by bbovenzi | `B.person.approved_by` | |
| Oct 19 2026 | `K.root.merged_at` | |
| #75025 and its link | `K.root.source_url` | |
| “A customer dashboard has pinned …” | `K.escalate.objection` | Verbatim |
| Agent name not recorded | `K.escalate.agent` (absent) | Gap |
| Muse Spark | `K.escalate.model` equals `K.spark.model` | The name "Muse Spark" is the mapping in held.js, as on argue |
| escalated | `K.escalate.decision` = `escalate` | |
| sentence 1 of 3 | index of `K.escalate.cited_quotes[0]` in the three sentences above | Counted, not typed |
| “My recorded decision does not cover …” | `K.escalate.reply` | Verbatim |
| `knack resolve <receipt> allow\|retire --reason "…"` | `K.readme.resolve` with `<receipt>` = `K.escalate.receipt_hash` | `"…"` is the brief's placeholder |
| Copy allow / Copy retire (clipboard) | the same, `allow\|retire` replaced by one verb | |
| "lets this exact edit through." / "drops the decision’s rule." | **UI copy, not a fixture value** | Paraphrase of README.md line 36; see NOTES.md |
| muse-spark-1.3 | `K.escalate.model` | |
| at api.meta.ai | `K.spark.host` | |
| ast-grep, 18.7 ms | `B.proof.scan`, `B.proof.verdict_ms` | |
| Receipt 1983f52b and its Copy | `K.escalate.receipt_hash` | Copy takes the full hash |
| 37 receipts, chain intact | `K.receipts_verify` | |
| Rule airflow-75025 | `B.where.rule` | |
| decision confirmed | `K.root.status`, `K.root.seeded` = false | |

Fixed copy (the brief's words, not data): "Held for a person.", "The record doesn’t cover this. Knack won’t guess.", "No recorded answer", "A person decides.", "A human runs this, with a reason:", "Answered by", "Verify it", "The block itself ran no model".
