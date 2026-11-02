# Day: where every visible value comes from

`D` is `window.KNACK.day` and `K` is `window.KNACK`, both from `mockups/fixtures/scenes.js`. `block.js` is not loaded. `day` was made by `knack day --json` in the demo clone with no GitHub token (see `mockups/NOTES-materials.md`). Audited against `shots/day/day-720p.png`, `-1080p.png`, `-390-fullpage.png` and the focused-cell frame.

| On the page | Fixture path | Note |
|---|---|---|
| apache/airflow (bar, headline) | `D.repo` | |
| main | `D.branch` | |
| 4be4607b2218, Nov 1 2026, 21:34:52 UTC (bar) | the last `D.events[]` with `type = receipt`: `receipt_hash`, first 12, and `time` in UTC | |
| "remembers 2 decisions" | `D.seats.length` | Seats are the registry's Confirmed roots (`knack/day/seats.py`) |
| "Last block today, 21:34:52 UTC." | the last receipt event with `kind = block`, `time`; "today" because its UTC date equals `D.date` | |
| "2 confirmed decisions in 52 weeks" | `D.seats.length`; 52 weeks is the graph's span, a layout choice | |
| "1 block today" | the count of block receipt events in `D.events` | `knack day` lists only today's receipts |
| "Earlier blocks not recorded" | none | Gap: the day feed holds today's receipts only |
| "Resolved by a person not recorded" | none (no `resolve` receipt in `D.events`) | Gap |
| The 52 weeks + today grid | from `D.date` (2026-11-01) back to Sunday 2025-11-02 | Layout |
| Shaded cells, Oct 19 and Oct 28 2026 | `D.seats[].merged_at`, UTC date | Shade = count that day |
| Red dot, Nov 1 2026 | the block receipt's `time`, UTC date | |
| Month labels | computed from the dates above | Every other month, plus the year on January |
| Tooltip "Oct 19 2026 · 1 decision · #75025 · Pushkal Gupta (author); approved and merged by bbovenzi" | `seat.merged_at`, the count, `seat.pr`, `seat.decided_by` | Empty days read "no decisions recorded" |
| "Dag list endpoints do not accept bare state …" | `K.root.decision`, shown because `K.root.id` equals `seat.root_id` (airflow-75025-1) | |
| "Decision text not recorded" (#75774) | none: `scenes.js` holds no root for airflow-75774-1 | Gap |
| Pushkal Gupta (author); approved and merged by bbovenzi / stegololz | `seat.decided_by` | |
| #75025, #75774, and their links | `seat.pr`; link `https://github.com/` + `D.repo` + `/pull/` + `seat.pr` | The URL is built, not stored |
| merged Oct 19 2026 / Oct 28 2026 | `seat.merged_at` | |
| "8 of 8 gates · tier block" (#75025 only) | `K.grid.cells` (8 PASS), `K.grid.tier` | `K.grid` is the 75025 row |
| "Proof not recorded" (#75774) | none | Gap |
| "Today, Nov 1 2026" | `D.date` | |
| 21:34:51 UTC, Commit a2548563 "base" · knack demo | `D.events[0]`: `time` (16:34:51 −05:00, shown in UTC), `sha`, `message`, `author` | |
| 21:34:52 UTC, Blocked an edit against airflow-75025-1 | `D.events[1]`: `time`, `kind`, `root_id` | |
| "Pull requests not recorded: GITHUB_TOKEN is not set" | `D.pulls_error` | Verbatim |
| Last receipt 4be4607b and its Copy | the last receipt event's `receipt_hash` | Copy takes the full hash |
| `knack receipts verify` → "37 receipts, chain intact" | `K.receipts_verify` | |
| "airflow-75025-1, confirmed" | `K.root.id`, `K.root.status`, `K.root.seeded` = false | |

Fixed copy: "Confirmed decisions", "Verify it", the key ("1, 2, 3+ decisions", "a block").
