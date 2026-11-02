# Argue screen (reference mockup): notes

This is a reference mockup only. Nothing is under `knack/`, and nothing is committed. It is built to sit next to the block page served at `/verdict/<hash>`, using the same tokens, the three Plex faces (loaded from `knack/console/static/fonts/`, read-only), the 16:9 rem composition, the bar and the verify row.

- **Page:** `mockups/argue/index.html?outcome=hold`. Append `&t=<ms>` to freeze a frame of the arrival.
- **Data:** `mockups/fixtures/scenes.js` (`hold`, `root`, `spark`, `spark_open`, `receipts_verify`) and `mockups/fixtures/block.js` (the blocked lines, the full quote, the person, the block receipt). No other source.
- **Capture:** `PLAYWRIGHT=<playwright/index.mjs> node mockups/tools/capture_page.mjs argue outcome=hold 0,500,1100,1500,2400`. It writes `mockups/shots/argue/`:
  - `argue-1080p.png` and `argue-720p.png`, the final frame;
  - `beat-720p-*.png`, five frozen beats;
  - `argue-720p-reduced.png`;
  - `argue-390-fullpage.png`;
  - `arrival-720p-4s.webm`;
  - `report.json`, the measured contrast, minimum size and overflow.

## What the brief asked for, and where I departed from it

| Asked | Built | Rubric reason |
|---|---|---|
| Ruling as a paper note | A dark `--raised` card in the tool's voice ("Muse Spark ruled hold, citing sentence 1 of 3 in #75025:"). Only the cited human sentence sits inside it, on a paper slip. | DESIGN.md: "nothing the tool says is ever paper." **Impact:** two dark replies against paper reads as machine against person in about 3 s. Paper still means only the human's words and the fix. |
| "The record holds no other words on this." | **Not shown.** It is false: the PR paragraph in `block.js` has three sentences, and the third is "Happy to alias instead if you would rather keep the advertised names working." The ruling line instead says which sentence it cited, counted from the fixtures ("sentence 1 of 3"). | **Depth:** a judge who has just seen the block page would catch it. A hold that hid the "happy to alias" sentence would look like the model hid counter-evidence. Showing all three sentences and naming the one cited is the honest version. |
| Objection card labelled "Muse Code, the agent" | Bound from `hold.agent` if a fixture records it. None does (the rulings log has only `session_id: "live-smoke"`), so it reads "The agent objected · Agent name not recorded". | **Depth:** never invent. Freezing the agent into the ruling or receipt makes "Muse Code" appear with no code change. **Tooling:** this costs the Muse Code mention until it is recorded. |
| The full quote | All three sentences at 20 px Plex Serif. The cited sentence is `--ink` and the other two are `--ink-muted`. | **Demo:** the block page is the peak at 28 px, and at 28 px three sentences don't fit at 720p. Shading by ink shows which sentence the ruling used without a second colour. |
| "Status Argued in ink" | "Argued" on `--raised` with `--text`, the same seal shape the block page uses for Allowed and Guard error. | Ink (#0A0A0B) needs paper behind it, and paper means a person. Red stays reserved for "Blocked". |
| Ruling text | Shown only when it differs from the cited quote. Here `hold.reply` equals the cited sentence word for word, so it appears once. | **Demo:** nothing read twice. |
| One action (the fix) | The paper fix card: "Delete lines 135–136." and "Lines 137–138 already use the right names.", both derived from the block fixture's rows and the root's `last_run_*` names. No `knack argue` command, since the agent has already argued. | **Demo:** one action. |
| "Answered by" with exactly the models the trace shows | Muse Spark, `muse-spark-1.3`, at api.meta.ai: the ruling's `model`, matched to `spark.model` and `spark.host`. Spark Open is not in this trace, so it is not shown. Under it: "The block itself ran no model: ast-grep, 18.7 ms." | **Tooling:** the model is named plainly where it worked, and no model is claimed on the block path. |

## Other changes, with the rubric reason

- **"Hold" at 40 px/600 opens the rail, then one line of consequence:** "Lines 135–136 stay blocked. #75025 offered that alias and merged without it." (**Impact**: the outcome and its consequence in 5 s.) The second sentence is shown only when the objection asks for an alias and the root's `rejected_alternative` is an alias.
- **The blocked lines are collapsed to the two matched rows with their gold gutter and gold tokens,** and the note's `DagRun.*` spans keep the gold underline. (**Depth**: the quote-to-code link stays checkable, and gold still means only that.)
- **No subline under the h1.** The outcome card carries the consequence. (**Demo**: one message.)
- **The PR is shown as "#75025",** as on the block page.
- **"Offered, not taken" is dropped from the note.** The full quote now says it in the human's own words. (**Demo**: nothing read twice.)
- **Motion** (one move per beat, then still; nothing loops; under reduced motion nothing moves):

| Beat (ms) | Move | Easing and duration | Why |
|---|---|---|---|
| 160 | The objection slides in from the left, 0.75 rem | `cubic-bezier(0.23,1,0.32,1)`, 420 ms | It enters from the agent's side, the code. A reply, not an impact. |
| 760 | The ruling rises 0.75 rem | same, 420 ms | Matches the block page's note arrival. |
| 1360 | "Hold", its reason and "Answered by" rise together, 0.75 rem | same, 320 ms | **No stamp**: a stamp means Blocked. One block, so the frozen frame never shows a reason without its word (an earlier build did at 1.1 s; fixed). |
| 2000 | The fix card rises | same, 420 ms | The last frame you remember is what to do. |

## Critique (impeccable, dual-agent: A design review, B detector)

**B, detector:**
- File scan: 0 findings.
- URL scans at 1280×720, 1920×1080 and 390×844: 0 findings. The detector was checked on a deliberately bad file and flagged it, so the empty results are real.
- Fonts: all five faces loaded.
- Colours: 0 off-token.
- Size: the smallest text is 12.25 px at 720p.
- One finding: at 390 px the code lines were cut off with an ellipsis instead of scrolling. Fixed.

**A, design review, fixed:**
1. **P0:** the false "no other words" line. Removed, and all three sentences are shown.
2. **P0/P1:** "Muse Code" was hardcoded. It is now bound, with a gap when missing.
3. **P1:** the note showed one sentence, not the full quote. Fixed.
4. **P1:** the tool's speech was on paper. The ruling is now dark, with a paper slip for the quote.
5. **Minor:** "Answered by" moved in its own beat (two moves). It is now part of the outcome beat.
6. **Minor:** "Hold" rose 6 px, which is invisible at half scale. It now rises 12 px.
7. **Minor:** some fields were not guarded with `has()`. Guarded.
8. **Minor:** "PR #75025" did not match the block page's "#75025". Fixed.

**A, not changed:**
- **Lowercase "decision confirmed".** It matches `page.py`; change both or neither.
- **About 110 px of empty rail under the fix at 720p.** That is Ma.

## Measured (after the fixes, final frame)

- 65 visible text nodes at 720p, 1080p and 390: all pass AA. The lowest is `--muted` on `--raised` (the reply label), 6.21:1.
- 0 overflow at 720p and 1080p, and 0 horizontal overflow at 390.
- 0 console errors and 0 non-loopback requests.

## Gaps (honest)

- **Two receipts.** The blocked lines come from the block fixture, receipt `80b311c1`. The hold ruling in the fixtures is on receipt `13f19d15`, a live-smoke run whose own receipt matched lines 28–29 of a sandbox file. No ruling exists on `80b311c1`. The page says so by labelling the code board "Blocked, receipt 80b311c1" while the bar and verify row show `13f19d15`. Fix it at the source by running `knack argue` against the 75025 block, then re-running `freeze.py`, so one receipt carries both.
- **The agent's name** is not recorded anywhere in the fixtures (see above).
- **`data/roots/airflow/75025.json`** in the working tree now holds the full three-sentence quote, while the frozen `scenes.json` root has one sentence. This page takes the three sentences from `block.js`, which records them verbatim; I checked them against `refs/github-75025.json`.
- **`knack receipts verify` → "37 receipts, chain intact"** is the frozen output from `freeze.py`'s run against the default receipts path, not this receipt alone.
