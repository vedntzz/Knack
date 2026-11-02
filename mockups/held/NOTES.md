# Held screen (reference mockup): notes

This is a reference mockup only. Nothing is under `knack/`, and nothing is committed. It reuses `../argue/argue.css` (the block page's tokens, Plex faces, 16:9 rem frame, bar and verify row) and adds `held.css`.

- **Page:** `mockups/held/index.html?outcome=escalate`. Append `&t=<ms>` to freeze a frame.
- **Data:** `mockups/fixtures/scenes.js` (`escalate`, `spark`, `root`, `readme.resolve`, `receipts_verify`) and `mockups/fixtures/block.js` (the blocked lines, the full quote, the person, the block receipt). `spark_open` is loaded, but no fixture shows that it took part in this ruling, so it is not shown (see below).
- **The allow and retire lines** are UI copy paraphrasing README.md ("allow lets that exact edit through, and retire drops the decision's rule"). They are not fixture values: the brief asks for them, and `K.readme` holds only the command. To make them data, freeze README's sentence into `readme.resolve_does`.
- **SOURCES.md** lists every value with its fixture path.
- **Capture:** `PLAYWRIGHT=<playwright/index.mjs> node mockups/held/capture.mjs` (wraps `mockups/tools/capture_page.mjs held outcome=escalate 0,400,900,1400``. It writes `mockups/shots/held/`:
  - `held-1080p.png` and `held-720p.png`;
  - `beat-720p-*.png`;
  - `held-720p-reduced.png`;
  - `held-390-fullpage.png`;
  - `arrival-720p-4s.webm`;
  - `report.json`.

## Where I departed from the brief, and why

| Asked | Built | Rubric reason |
|---|---|---|
| One command `knack resolve <receipt> allow\|retire --reason "…"` with Copy | One well showing the command exactly as the README writes it, with the full receipt. Under it, two buttons, "Copy allow" and "Copy retire", each with its one line. | **Depth:** in a shell, `\|` is a pipe, so copying the literal form would not run. Each button copies a runnable command. **Demo:** one well instead of two (session 1 had two, 10 lines of hash). |
| "Answered by" exactly as the escalate trace shows | Only Muse Spark (`muse-spark-1.3`) at api.meta.ai, plus "The block itself ran no model: ast-grep, 18.7 ms." An earlier build added "Muse Spark Open (Baseten) ruling not recorded", and I removed it. | **Tooling:** the trace has one model. README.md says a case is held only when Spark and Spark Open both escalate; this ruling's record names only Spark. See the gaps. |
| The ruling as a dark card | Dark card: "Muse Spark escalated, citing sentence 1 of 3 in #75025:", then its reply verbatim. The cited sentence is not repeated in a slip as it is on argue; it is set in full ink inside the note above. | **Demo:** five boards must fit at 720p, and the sentence is not read twice. |
| The thread as on argue | The same boards, but the note and replies span the full column instead of hanging under the code. | It is one board longer than argue, and full width saves a line in the note and in each reply. |
| No seal was specified | No seal. | "Held for a person." already says it; a seal reading "Held" would be read twice. |

## Other changes, with the rubric reason

- **The secondary line sits on the headline's baseline,** in 20 px `--muted`. (**Impact**: what happened and why in one line; it also saves 24 px of height.)
- **The dashed outline is the only line on the page.** It is 2 px dashed `--muted`, with "No recorded answer" in 16 px `--muted`. (**Demo**: the empty place where an answer would be, shown, not explained.) DESIGN.md bans hairline rules; this is a 2 px state marker the brief asked for, not a divider.
- **The action is paper, because a person must act on it.** Its heading is "A person decides." at 28 px/600, as the fix card is on the block page.
- **The section's accessible label is "The block, the decision, the objection and the ruling",** not "in order", because the boards come from two receipts.

## Motion

| Beat | Move | Easing and duration | Why |
|---|---|---|---|
| 400 ms | The dashed outline draws once, as a solid pen stroke travelling round it and revealing the dashes. | linear, 900 ms | A constant-speed pen stroke, as the block page's thread. It is the only move: nothing arrives, because nothing new has happened. |

- Under reduced motion it is drawn at once.
- Without script, the CSS dashed border shows.
- The SVG is sized from the border the browser laid out, and lines up within 0.06 px at 1280, 1920 and 390. An earlier build was 1–1.5 px off; the critique caught it.

## Critique (impeccable, dual-agent: A design review, B detector)

**B, detector:**
- File scan: one `cramped-padding` warning on `.unanswered`. It was a false positive (the static scan has no layout), but the box now has 4 px of vertical padding anyway.
- URL scans: 0 findings at 1280 and 1920.
- At 390, one advisory, `straggler`: "#75025:" sits alone on the ruling's caption line. I left it; it is phone-only.
- Fonts: all five faces loaded. Colours: 0 off-token.
- Hand checks: no `transition: all`; the only animation is `stroke-dashoffset`.
- Fixed: the outline was misaligned (see Motion).

**A, design review, fixed:**
- **P0:** the copied command was not runnable. Split into allow and retire.
- **P1:** the aria label claimed "in order". Changed.
- **Answered by** listed a model the trace doesn't hold. Removed.

**A, not changed, with reasons:**
- **The secondary line and the ruling's "A person will decide."** One is the headline copy you specified, and the other is the ruling's verbatim reply.
- **The three-sentence quote.** Kept as on argue: `block.js` records all three sentences verbatim from the PR, and the working-tree root now holds all three. A's objection is that the frozen `scenes.json` root records one sentence, so "1 of 3" counts against `block.js`.
- **Lowercase "decision confirmed".** It matches `page.py`; change both or neither.
- **Undo for `retire`.** README.md does not say, so the page doesn't claim it either way.
- **The path row on the code board.** Kept for parity with argue and the block page.

## Measured (final frame)

- 67 visible text nodes at 720p, 1080p and 390: all pass AA. The lowest is `--muted` on `--raised`, 6.21:1.
- 0 overflow at 720p and 1080p, and 0 horizontal overflow at 390.
- 0 console errors and 0 non-loopback requests.

## Gaps (honest)

- **Two receipts, labelled, not merged.** The blocked lines are the block fixture's, receipt `80b311c1`. The escalation is on receipt `1983f52b` (Oct 31 2026, 18:18:46 UTC), a sandbox run whose own deny matched lines 28–29 of `knack-sandbox/routes/public/dags.py`. The code board says "Blocked, receipt 80b311c1"; the bar, both commands and the verify row carry `1983f52b`. Fix it at the source by arguing the 75025 block with the customer-contract objection, then re-running `freeze.py`.
- **Muse Spark Open.** Per README.md, a case is held only when both Spark and Spark Open escalate. The escalate fixture records one model, `muse-spark-1.3`. Either the ruling record should carry both models, or this case isn't held under that rule. The page shows only what is recorded.
- **The agent's name** is not recorded, so the card reads "Agent name not recorded".
- **"37 receipts, chain intact"** is the frozen output of `knack receipts verify` on the default path, not this receipt alone.

## Session 2 changes (this brief)

| Change | Why |
|---|---|
| Every 14 px role (bar, code, captions, copy buttons, verify row, inline code) raised to 16 px at 720p, 24 px at 1080p. | The brief sets a 15 px floor. DESIGN.md's next step is 16, so it stays on the DESIGN.md scale. |
| The code board's path row removed; "Blocked, receipt 80b311c1" now sits right-aligned on line 135. On the phone it returns to its own row. | It saved 32 px, which paid for the larger type at 720p. The bar already names the file. |
| Rail 24 → 22 rem. | The thread needed the width. |
| The resolve command: one well and two copy buttons (see the table above). | **Demo**: one action. |
| `--reason "…"`, "Oct 19 2026" and "18.7 ms" no longer wrap. | Numbers with units never wrap. |
| A `prefers-reduced-motion` block for the press scale on the buttons. | Hallmark lint FAIL 27, and it was real: the buttons' transform had no fallback. |
| `<meta name="description">`. | Hallmark lint WARN F23. |
| `capture.mjs` and `SOURCES.md` in the folder. | Brief layout. |
| A regression found and fixed: the 22 rem column override beat argue.css's phone rule, so at 390 px the thread was squeezed to near-zero width (5,495 px tall). It is now scoped. | Caught by the measured page height, not the detector. |

**Not followed, and why**
- **Text colours.** The brief gives #F5F6F7 / #B4B8BF / #868B94. DESIGN.md gives `--text` #E6E7EA and `--muted` #9A9EA6, and DESIGN.md wins on style, so I kept its tokens. Every node still passes AA.
- **Type scale.** The brief's scale is 16, 18, 20, 24, 30, 40, 48. I kept DESIGN.md's 16, 20, 28, 40, again because DESIGN.md wins.
- **The Hallmark stamp.** Hallmark FAIL 20 (no stamp) is left as it is. Your rule is lint only, never write a stamp.

**Impeccable verdict (session 2):** the detector found 0 findings on the rendered page at 1280×720, 1920×1080 and 390×844. The detector is live: a control file with Inter, 10 px text and 1.3:1 contrast was flagged. The design review's open items from session 1 still stand ("decision confirmed" in lowercase, the 3-sentence count), and none of them is new.

**Measured (session 2 final):** 66 text nodes at each size, 0 failing AA. The lowest is 6.21:1 (`--muted` on `--raised`). The smallest text is 16 px at 720p. 0 overflow at 720p and 1080p, 0 horizontal overflow at 390. 0 console errors and 0 outside requests.
