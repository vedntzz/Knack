# Day screen (reference mockup): notes

This is a reference mockup only. Nothing is under `knack/`, and nothing is committed. It reuses `../argue/argue.css` (tokens, Plex faces, the 16:9 rem frame, the bar, the copy button and the verify row) and adds `day.css`.

- **Page:** `mockups/day/index.html`. Append `?t=<ms>` to freeze a frame.
- **Data:** `scenes.js` → `day`, `root`, `grid`, `receipts_verify`. SOURCES.md has every value with its path.
- **Capture:** `PLAYWRIGHT=<playwright/index.mjs> node mockups/day/capture.mjs` → `mockups/shots/day/`.

## Where I departed from the brief, and why

| Asked | Built | Reason |
|---|---|---|
| A gold dot for "a person resolved a held edit" | A **paper** dot with an ink ring. None renders, because no resolve is recorded; the key reads "Resolved by a person not recorded". | DESIGN.md: gold means only the quote-to-code link, and "red and gold never share a meaning". A person acting is paper in this system. DESIGN.md wins on style. |
| Confirmed decisions as **paper**-note lines | Dark `--panel` rows, the tool's record: the decision in plain words, author, PR (linked), merge date, gates and tier. | DESIGN.md: "nothing the tool says is ever paper." `root.decision` is Knack's restatement, not the person's words; Plex Serif and paper are reserved for verbatim human words. |
| Shade in "four steps of the grey ladder" | Empty `--panel`, 1 `--muted`, 2 `--text`, 3+ `--paper`. | Tokens only. `--raised` is too close to `--panel` to read as a step at half scale. |
| Hover "date · count · PR · author" | Exactly that, as a dark tooltip. Keyboard: one tab stop (today's cell); arrows move a day (up/down) or a week (left/right); the tooltip follows focus, and each cell's `aria-label` carries the same text. | **Depth / a11y.** 365 tab stops would be a trap; a roving tabindex gives one. |
| "Nothing blocked today." **or** the last block's time | "Last block today, 21:34:52 UTC." | There was a block today, so the time it happened is shown. |
| Today's PRs | "Pull requests not recorded: GITHUB_TOKEN is not set", verbatim from `pulls_error`. | Truth: the feed was made without a token. |
| Rule in the verify row | "airflow-75025-1, confirmed": the root id and its label. | The day fixture has no rule id. Building `airflow-75025` from the PR number would be a guess. |

## Other changes, with the rubric reason

- **Headline plus secondary on one baseline.** (**Impact:** the repo, the count and the last block in one line.)
- **The count line says what is not there:** "Earlier blocks not recorded". The day feed carries only today's receipts, so an empty past would otherwise read as "no blocks". (**Depth**.)
- **Times in UTC throughout.** The commit is recorded at −05:00 and the receipt in UTC; shown together, they are one second apart (21:34:51 and 21:34:52), which is what happened in the demo run. (**Wabi-sabi:** real times with seconds.)
- **Red appears twice,** each time for a block: the dot on Nov 1 and the dot before "Blocked" in today's list.
- **On the phone, the graph scrolls sideways and opens on today,** where the record is.
- **Type floor: 16 px.**

## Motion

| Beat | Move | Easing and duration | Why |
|---|---|---|---|
| 0–584 ms | Cells fade in a week at a time, left to right: each column's delay is week × 7 ms, and each fade is 220 ms of opacity. The last starts at 364 ms and ends at 584 ms. | `cubic-bezier(0.23,1,0.32,1)` | The brief caps it at 600 ms. Reading left to right takes you from a year ago to today, so the eye arrives at the right end, where the decisions and the block are. Opacity only: nothing travels, because the grid is a record, not an event. |

- Under reduced motion there is no fade; the grid is there at once.
- Without script there is no grid, because the grid is built by script. This is a known limit of the mockup; the server-rendered page would ship the cells as HTML.

## Critique

**Impeccable detector** (rendered page):
- 1280×720: 0.
- 1920×1080: 0.
- 390×844: one advisory, a straggler ("block" alone on a line). Fixed with no-break spans; now 0.

**Design review (mine, against the screenshots):**
- **5 s test, muted:** the headline, two light squares at the right end and one red dot read as "two decisions, one block today". **Pass.**
- **Weakness:** the year is mostly empty. That is the honest picture of this fixture, which holds only Confirmed roots and today's receipts. I didn't shorten the span to hide it. The 7 Inferred airflow roots in `data/roots/airflow/` would fill it, but they aren't in `scenes.js` (see the gaps).
- **One action:** the verify Copy. There's no person action on a quiet day. **Pass.**

**Hallmark lint:** FAIL 20 (no stamp) is left as it is, per your rule. WARN 41 is in `argue.css`, not this page.

**Measured:**
- 61 text nodes, 0 failing AA. The lowest is 6.85:1.
- Min 16 px at 720p.
- 0 overflow at 720p and 1080p, and 0 horizontal page overflow at 390 (the graph scrolls inside its own box).
- 0 console errors and 0 outside requests.
- Keyboard checked: Tab lands on today's cell; the arrow keys reached Oct 19, and the tooltip read "Oct 19 2026 · 1 decision · #75025 · Pushkal Gupta (author); approved and merged by bbovenzi".

## Gaps (for the build phase)

- **Earlier blocks:** `knack day` returns today's receipts only. The graph needs a receipts-by-day read for its span.
- **Resolves:** no `resolve` receipt is in the fixture.
- **#75774's decision text and proof:** `scenes.js` holds only the 75025 root and grid.
- **The Inferred roots:** 7 for airflow, in `data/roots/airflow/`, not frozen. Should Inferred roots appear on the graph at all, perhaps outlined? This is a product decision; today the page counts only Confirmed decisions, matching `seats_of`.
- **Pull requests:** need `GITHUB_TOKEN` at freeze time.
- **Two receipts in the project fixtures:** this page's receipt `4be4607b` (a sandbox demo run) is a different receipt from the block page's `80b311c1`. The day page shows only its own.
- **"37 receipts, chain intact"** is the default receipts path's result at freeze time. Nothing in the fixture shows that `4be4607b` is in that chain.
