# Review: held, recovery (session 1), day and landing (session 2)

These are reference mockups only. Nothing under `knack/` changed, and nothing is committed. Each page has `index.html`, `capture.mjs`, `NOTES.md` and `SOURCES.md`. The shots are in `mockups/shots/<page>/`, at 1080p, 720p, 720p reduced motion and 390 full page, plus the beats, a 4 s arrival video and `report.json`.

## Rules applied across both pages

| Brief says | DESIGN.md says | Followed | Why |
|---|---|---|---|
| Text #F5F6F7 / #B4B8BF / #868B94 | `--text` #E6E7EA, `--muted` #9A9EA6 | DESIGN.md | "DESIGN.md wins on any style question." All nodes pass AA, measured. |
| Scale 16, 18, 20, 24, 30, 40, 48; minimum 15 px | 12, 14, 16, 20, 28, 40; minimum 12 | DESIGN.md's sizes from 16 up | It meets both: nothing under 15, and every size is on DESIGN.md's ramp. |
| Hallmark: lint only, never write a stamp | – | No stamp | Hallmark's FAIL 20 stays open on both pages, on purpose. |

## Held (`mockups/held/?outcome=escalate`)

**Rubric changes, made this session (session 1 had built the page):**
- **Demo:** the resolve command is one well, shown exactly as the README writes it (`allow|retire`), with "Copy allow" and "Copy retire". Each copies a runnable line with the full receipt, because `|` is a pipe in a shell. Session 1 had two wells.
- **Brief floor:** every 14 px role is now 16 px. To pay for it at 720p, the code board's path row is gone; the bar names the file, and the block receipt rides on line 135.
- **Numbers never wrap:** "Oct 19 2026", "18.7 ms" and `--reason "…"` no longer break.
- **Fixed:** a reduced-motion fallback for the press scale, and a meta description (Hallmark).
- **Fixed a regression I introduced:** a desktop column override broke the 390 px layout, which went 5,495 px tall. It is now scoped.

**Impeccable's verdict:** the detector found 0 findings at 1280×720, 1920×1080 and 390×844. The design review's open items from session 1 stand, all minor: lowercase "decision confirmed" (matches `page.py`), and "1 of 3" counted against `block.js`'s three sentences.

**Measured:** 66 text nodes, 0 failing AA (lowest 6.21:1). Min 16 px at 720p. 0 overflow. 0 console errors, 0 outside requests.

**Data gaps for the build phase:**
1. **Two receipts, labelled, not merged.** The block is `80b311c1`; the escalation is `1983f52b`, from a sandbox run. Argue the 75025 block and re-freeze.
2. **Spark Open.** README says a case is held only when Spark and Spark Open both escalate, but the escalate fixture records one model. Record both, or this isn't "held" by the README's own rule.
3. **The agent's name** is not recorded.
4. **The allow/retire lines** are UI copy paraphrasing README.md, not fixture values. Freeze them.
5. **"37 receipts, chain intact"** is a whole-chain result, not this receipt's alone.

## Recovery (`mockups/recovery/`)

**Rubric changes:**
- **Truth over the brief's word:** step 4 is "Denied when replayed", not "denied on retry". The only denial is the proof harness's `cases` gate. The page also says "A proof run, not a live retry. Live, the tier is warn and the decision Inferred." The root is Inferred and the tier is warn, so live it warns, not blocks. No red anywhere.
- **"Recovery", not "self-repair":** the fixture has no old-rule version id.
- **Impact:** the decision's quote (tiangolo, #16062, labelled Inferred) is the page's one paper surface, with "an even larger bump" underlined in gold. It wasn't asked for, but without it the page shows a tool fixing itself, not a person's decision kept.
- **Tooling:** "Recompiled by Muse Spark `muse-spark-1.3` at api.meta.ai", as the log names it. "The fresh cross-model gate's model not recorded". The page doesn't claim the gate ran a model, and doesn't claim it didn't.
- **Depth:**
  - The gate lines are verbatim, including the uncomfortable one: held-out same catches 2/3, the same as the old rule.
  - Two earlier runs that kept the old rule are named by the gate that failed them.
  - The verify command `cat data/rules/fastapi/16062.yml` was run and works.
- **Before/after** is the rule's behaviour on this edit, not its text, because the rule text isn't in the fixtures.
- **Motion:** the track fills top to bottom once, in 1.4 s with a strong ease-in-out. It stops at step 4; step 5 is a dashed "not recorded" outline, as on held.

**Impeccable's verdict:**
- The detector found 0 findings at 1280×720 and 1920×1080.
- At 390×844 it raised two advisories (an unbalanced heading and a one-word caption line). Both are fixed, and it now finds 0.
- In the design review, the proof line (seven sub-checks) is the densest text. It's kept verbatim on purpose.

**Measured:** 75 text nodes, 0 failing AA (lowest 6.85:1). Min 16 px at 720p. 0 overflow. 0 console errors, 0 outside requests.

**Data gaps for the build phase:**
1. **No receipt** for the miss, recompile or install.
2. **No branch.**
3. **No old/new rule version ids.** These are needed for "self-repair".
4. **The rule text isn't frozen.** `data/rules/fastapi/16062.yml` has a usable one-line `message:`; freeze the old and new ones.
5. **No live retry.** At tier warn on an Inferred root, a live retry would warn, not deny.
6. **No corrected edit passing.** A must-pass case for 16062 would supply it.
7. **The fresh cross-model gate's model** is not named in the log.
8. **The edit is rebuilt,** not the agent's bytes. The page says so.
9. **The slipping run was in the unguarded arm** (README.md line 139). This isn't in the fixture; freeze it.

## Not done, and why

- **Taste's `draw.mjs` / `inspect.mjs` run.** These are app screens inside a locked design system (DESIGN.md plus the argue page). Taste's own rule for an existing system is to keep it and take only critique, so I didn't deal a direction. Its house rules were checked by hand: no eyebrows, no gradients, no shadows, no glass, sentence case, mono only for code and hashes.
- **Taste's 4-picture floor and "eight moving elements"** contradict DESIGN.md (one move per beat, nothing loops), so I didn't apply them.
- **The impeccable `critique` sub-command** wasn't run as a separate agent. The design review above is mine, against the screenshots.

---

# Session 2: day and landing

`mockups/shots/review/contact.png` shows block, argue, held, recovery, day and landing at 1080p on one sheet (3200 × 1375).

## Day (`mockups/day/`)

**Rubric changes:**
- **Impact:** the headline and its secondary line share one baseline. With the regenerated fixture (commit `19cbec9`, Nov 3) they read "apache/airflow remembers 5 decisions. Last block today, 05:10:49 UTC." (at review time, Nov 1: 2 decisions, 21:34:52 UTC).
- **Squint test:** it leaves the headline, two shaded squares at the year's right end (Oct 19 with 1 decision, Oct 28 with 4) and one red dot.
- **DESIGN.md over the brief, two places:**
  - The "person resolved a held edit" mark is a paper dot, not gold, because gold means only the quote-to-code link.
  - The confirmed decisions are dark rows, not paper, because `root.decision` is Knack's restatement, not a person's words.
- **Depth:**
  - The count line names what the feed lacks ("Earlier blocks not recorded") instead of letting an empty past read as "no blocks".
  - The #PR links are built from `day.repo` + `seat.pr`.
- **Keyboard:** one tab stop (today), arrows move a day or a week, and the tooltip follows focus ("date · count · PR · author"). This was checked.
- **Motion:** cells fade in by week, left to right, finishing at 584 ms; opacity only; once.

**Impeccable's verdict:**
- The detector found 0 at 1280 and 1920.
- At 390 it found one straggler, which is fixed, and now finds 0.
- Design review: the year is mostly empty, which is the honest picture of a fixture holding only Confirmed roots and today's receipts.

**Measured:** 61 nodes, 0 failing AA (lowest 6.85:1). Min 16 px. 0 overflow. 0 errors, 0 outside requests.

**Data gaps for the build phase:**
1. **Earlier blocks:** `knack day` returns today's receipts only.
2. **No resolve receipts.**
3. **#75271 and #75774:** no decision text or proof is frozen; only the 75025 root and grid are in `scenes.js`.
4. **The 7 Inferred airflow roots** are not frozen. Whether Inferred roots belong on the graph is a product call.
5. **No PRs** (`GITHUB_TOKEN is not set`).
6. **Unproven chain:** the day receipt `84a07463` (regenerated; `4be4607b` at review time) isn't shown to be in the "37 receipts" chain.

## Landing (`mockups/landing/`)

**Rubric changes:**
- **Impact:**
  - The hero is your headline, one action (`bash scripts/reproduce.sh` + Copy) and the real block page as the picture. The red "Blocked" and the paper quote are legible at 720p.
  - The three steps each carry real material: the person's words on paper, the eight gates by name, and the blocked lines with "No model, no network."
- **Tooling:**
  - A four-row models table (model, where it runs, job, what the traces show).
  - Muse Spark's jobs are each backed by a fixture trace (hold, escalate, recompile, extraction).
  - **Muse Code and Muse Spark Open are listed with your jobs, but "not recorded" where no trace exists.** No fixture names Muse Code, and none shows Spark Open running.
- **Depth:**
  - 8/8 and 0 false alarms → `bash scripts/reproduce.sh`, which regenerates the proof grid byte for byte.
  - 37 receipts → `knack receipts verify`.
- **Two receipts:** the hero capture is its own run (5e8a44648bd0, 16.5 ms); the text figures come from block.js (80b311c17a39, 18.7 ms). The caption keeps them apart.
- **Frame:** the content's edges now match the bar's.
- **"How it works"** became "From a pull request to a stopped edit" (Hallmark eyebrow FAIL).
- **Motion:** only the hero picture rises in, once (600 ms ease-out, IntersectionObserver).

**Impeccable's verdict:**
- The detector found 0 at 1280, 1920 and 390 after fixing a cramped-padding warning and two stragglers.
- Design review: the page reads in 5 s through its picture. Its weakest points are the gaps: no repo link, no install command, no video.

**Measured:** 121 nodes at desktop and 113 at 390, 0 failing AA (lowest 6.41:1, "Blocked" ink on red). Min 16 px. 0 horizontal overflow. 0 errors, 0 outside requests.

**Data gaps for the build phase (most urgent first):**
1. **The repo link and the install command.** Neither is in a fixture. A landing page can't ship without them.
2. **One block run for hero and text.** Re-capture the block page from `80b311c1`, or re-freeze `block.js` from `5e8a4464`.
3. **A trace naming Muse Code as the agent.**
4. **A recorded Spark Open run** (corroboration or attack).
5. **A frozen command for the latency figures.**
6. **The demo video.**

## Across all six pages

- **Five different receipts appear across the six pages:** block 5e8a4464, argue 13f19d15, held 1983f52b (plus the block's 80b311c1), day 84a07463 (regenerated Nov 3; 4be4607b at review time), and block.js 80b311c1. Each page labels its own, and none merges them. One demo run that blocks, argues, escalates and resolves the same edit, frozen once, would let every page tell one story with one receipt.
- **Every page keeps the 16 px floor, DESIGN.md's tokens, red only for "Blocked" and gold only for the quote-to-code link.** Day's person mark is paper.
- **Hallmark FAIL 20 (no stamp) is open on every page, on purpose.**
