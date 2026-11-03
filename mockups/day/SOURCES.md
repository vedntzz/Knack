# Day: where every visible value comes from

`D` is `window.KNACK.day` and `K` is `window.KNACK`, both from `mockups/fixtures/scenes.js`. `block.js` is not loaded. `day` was made by `knack day --json` in the demo clone with no GitHub token (see `mockups/NOTES-materials.md`). Values below are the regenerated fixture's (commit `19cbec9`, `captured_at` 2026-11-03T05:11:09Z). The shots in `shots/day/` (`day-720p.png`, `-1080p.png`, `-390-fullpage.png` and the focused-cell frame) were taken on Nov 1 from the earlier fixture and still show its values (2 decisions, receipt `4be4607b`).

| On the page | Fixture path | Note |
|---|---|---|
| apache/airflow (bar, headline) | `D.repo` | |
| main | `D.branch` | |
| 84a074639ff5, Nov 3 2026, 05:10:49 UTC (bar) | the last `D.events[]` with `type = receipt`: `receipt_hash`, first 12, and `time` in UTC | |
| "remembers 5 decisions" | `D.seats.length` | Seats are the registry's 5 Confirmed airflow roots: airflow-75025-1, airflow-75271-1, airflow-75271-2, airflow-75774-1, airflow-75774-2 (`knack/day/seats.py`). A seat is a root, so #75271 and #75774 count twice |
| "Last block today, 05:10:49 UTC." | the last receipt event with `kind = block`, `time`; "today" because its UTC date equals `D.date` | |
| "5 confirmed decisions in 52 weeks" | `D.seats.length`; 52 weeks is the graph's span, a layout choice | |
| "1 block today" | the count of block receipt events in `D.events` | `knack day` lists only today's receipts |
| "Earlier blocks not recorded" | none | Gap: the day feed holds today's receipts only |
| "Resolved by a person not recorded" | none (no `resolve` receipt in `D.events`) | Gap |
| The 52 weeks + today grid | from `D.date` (2026-11-03) back to Sunday 2025-11-02 | Layout |
| Shaded cells, Oct 19 2026 (1) and Oct 28 2026 (4: #75271 twice, #75774 twice) | `D.seats[].merged_at`, UTC date | Shade = count that day, 3+ for Oct 28 |
| Red dot, Nov 3 2026 | the block receipt's `time`, UTC date | |
| Month labels | computed from the dates above | Every other month, plus the year on January |
| Tooltip "Oct 19 2026 · 1 decision · #75025 · Pushkal Gupta (author); approved and merged by bbovenzi" | `seat.merged_at`, the count, `seat.pr`, `seat.decided_by` | Empty days read "no decisions recorded" |
| "Dag list endpoints do not accept bare state …" | `K.root.decision`, shown because `K.root.id` equals `seat.root_id` (airflow-75025-1) | |
| "Decision text not recorded" (#75271, #75774) | none: `scenes.js` holds no root for airflow-75271-1/-2 or airflow-75774-1/-2 | Gap |
| Pushkal Gupta (author); approved and merged by bbovenzi / dabla / stegololz | `seat.decided_by` | |
| #75025, #75271, #75774, and their links | `seat.pr`; link `https://github.com/` + `D.repo` + `/pull/` + `seat.pr` | The URL is built, not stored |
| merged Oct 19 2026 (#75025) / Oct 28 2026 (#75271, #75774) | `seat.merged_at` | |
| "8 of 8 gates · tier block" (#75025 only) | `K.grid.cells` (8 PASS), `K.grid.tier` | `K.grid` is the 75025 row |
| "Proof not recorded" (#75271, #75774) | none | Gap |
| "Today, Nov 3 2026" | `D.date` | |
| 05:10:48 UTC, Commit be49ca2f "base" · knack demo | `D.events[0]`: `time` (00:10:48 −05:00, shown in UTC), `sha`, `message`, `author` | |
| 05:10:49 UTC, Blocked an edit against airflow-75025-1 | `D.events[1]`: `time`, `kind`, `root_id` | |
| "Pull requests not recorded: GITHUB_TOKEN is not set" | `D.pulls_error` | Verbatim |
| Last receipt 84a07463 and its Copy | the last receipt event's `receipt_hash` | Copy takes the full hash |
| `knack receipts verify` → "37 receipts, chain intact" | `K.receipts_verify` | |
| "airflow-75025-1, confirmed" | `K.root.id`, `K.root.status`, `K.root.seeded` = false | |

Fixed copy: "Confirmed decisions", "Verify it", the key ("1, 2, 3+ decisions", "a block").
