# Recovery screen (reference mockup): notes

This is a reference mockup only. Nothing is under `knack/`, and nothing is committed. It reuses `../argue/argue.css` (tokens, Plex faces, the 16:9 rem frame, the bar, the paper note, the code frame and the verify row) and adds `recovery.css`.

- **Page:** `mockups/recovery/index.html`. Append `?t=<ms>` to freeze a frame.
- **Data:** `scenes.js` → `miss` (root, `edit_note`, `edit_file`, `edit_after`, `run1_log`, `run2_log`, `bar2_log`, `tier`, `cases`) plus `spark` / `spark_open` (to name the model and host) and nothing else. `block.js` is not loaded, because this is a different root and a different run, with no shared receipt.
- **Capture:** `PLAYWRIGHT=<playwright/index.mjs> node mockups/recovery/capture.mjs` → `mockups/shots/recovery/`: `recovery-1080p.png`, `recovery-720p.png`, `recovery-720p-reduced.png`, `recovery-390-fullpage.png`, four `beat-720p-*.png`, `arrival-720p-4s.webm` and `report.json`.
- **SOURCES.md** maps every value on the page to its fixture path.

## Word choice: "recovery", not "self-repair"

The fixture holds the rule id (`fastapi-16062`, the same before and after), a candidate filename (`candidate-20261031T171504Z-43479c.yml`) and the install path. It holds no version id for the old rule, so by the brief's test it is "recovery". The word appears in the `<title>`; the page itself says what happened, step by step.

## Where I departed from the brief, and why

| Asked | Built | Rubric reason |
|---|---|---|
| Step 4, "denied on retry" | **"Denied when replayed"**, with the `cases` gate line verbatim. Under it: "Installed after 2 attempts. A proof run, not a live retry. Live, the tier is **warn** and the decision Inferred." | **Depth / truth:** the only evidence of the denial is the proof harness replaying the recorded case. No live retry and no hook deny receipt exist. The root is Inferred and the tier is warn, so live this rule warns and does not block (CLAUDE.md: Inferred never blocks). Saying "denied on retry" would claim a block that cannot happen. |
| Before/after "of the rule" | Before/after of the rule's **behaviour** on this edit, one sentence each, from the log and the edit note. | The rule's text is not in any fixture (see the gaps). The installed YAML has a one-line `message:` that would do; it needs freezing first. |
| "Who did the work, exactly as the log shows" | Muse Spark `muse-spark-1.3` at api.meta.ai recompiled the rule. "The fresh cross-model gate's model not recorded." | **Tooling:** the log names one model. The gate's name says "cross-model", but the log doesn't say which model ran it, so the page doesn't claim one. It doesn't claim "no model" either. Spark Open is not shown. |
| Headline | Kept verbatim: "One edit slipped past a rule. The rule learned." | Hallmark warns at 9 words (it wants ≤ 7). It's your copy, and it fits on one line at 720p and 1080p. |
| A paper element | The decision's quote (tiangolo, #16062) is the one paper surface, labelled **Inferred**. | **Impact:** the product line says Knack "shows the human's words". Without the quote, a muted judge sees a tool fixing itself, not a person's decision being kept. The rejected phrase "an even larger bump" carries the gold underline, as on the block page. |
| Verify row: receipt, command, rule and decision | "Receipt not recorded"; `cat data/rules/fastapi/16062.yml` + Copy (it ran on 2026-11-01 and printed the rule); "Rule fastapi-16062 · decision inferred, not seeded · tier warn". | **Depth:** a command that works. The case file (`cat data/registry/cases/…/must-fail-77322b4d226e.json`) also works, but two commands broke the 720p frame; the rule file is the stronger check of "the rule learned". |
| No red | No red on the page. | Red means "Blocked", and nothing was blocked live. |

## Other changes, with the rubric reason

- **The code board shows one line, line 18, `_CALLABLE_CACHE_SIZE = 8192`, without a gold gutter.** Gold means quote-to-code link; this rule matched nothing, so nothing is gold in the code. (**Depth**.) An earlier build also showed line 143 and named lines 173 and 203. I cut them for height; the constant alone shows "8192 through a name".
- **The edit's provenance is on the page:** "Rebuilt, not the agent's bytes: …", verbatim from `edit_note`. (**Depth**: the judge must not think these are the agent's own bytes.)
- **The two failed earlier runs are named by the gate that failed them.** (**Depth**: it shows the gates refused a weaker rule twice before installing.)
- **The gate results are verbatim log text**, including "held-out same: 2/3 violations caught (old rule 2)". The new rule catches no more held-out violations than the old one; its gain is the recorded case. The page doesn't hide that.
- **Step 5 is a dashed outline**, the same device and words pattern as the held screen's "No recorded answer". It sits outside the track, so the fill visibly stops where the data stops.
- **The type floor is 16 px** (DESIGN.md's step at or above the brief's 15 px floor).
- **The colours are DESIGN.md's tokens, not the brief's text greys** (see REVIEW.md). Every node is measured and passes AA.

## Motion

| Beat | Move | Easing and duration | Why |
|---|---|---|---|
| 300 ms | The timeline track fills top to bottom once (`scaleY` 0→1 on a 4 px bar, origin top), from step 1 to the end of step 4. | `cubic-bezier(0.77, 0, 0.175, 1)`, 1,400 ms | It is on-screen movement, so a strong ease-in-out (Emil). It is explanatory, not UI feedback, so it runs longer than 300 ms: about 350 ms a step, slow enough to read as "one, then the next" at half scale, and done before a 5 s look ends. It never reaches step 5, because nothing is recorded there. |

- Only `transform` is animated. Nothing loops.
- Under `prefers-reduced-motion`, the track is drawn full, with no movement (`recovery-720p-reduced.png`).
- Without script, each step has its own bar in `--muted` (the CSS fallback), so the final frame shows with no JS.
- The copy button's press scale (160 ms) is dropped under reduced motion; the colour change stays.

## Critique

**Impeccable detector** (rendered page, `--json`):
- 1280×720: 0 findings.
- 1920×1080: 0.
- 390×844: two advisories, both fixed. One was the step 1 heading unbalanced on two lines (now `text-wrap: balance`). The other was "Inferred" alone on the last caption line (now bound to the PR link with a no-break span). After the fixes: 0.
- The detector was proven live in this session on a control file (Inter, 10 px, 1.3:1), which it flagged three times.

**Design review (Impeccable's critique questions, done by me against the screenshots):**
1. Is the message clear in 5 s, muted, at 720p? The headline on one line, then the paper quote, then four bold step titles down a filled bar. **Yes.**
2. Is there one primary action? The only control is the verify Copy. There's nothing for a person to do, which is honest for this event. **Yes.**
3. What's the weakest part? The proof line is long (seven sub-checks in one sentence), the densest text on the page. I left it verbatim, because paraphrasing the gate log would lose Depth. I stopped hyphenated names from breaking.
4. Hierarchy: the squint test leaves the headline, the paper note and the four step titles. **Pass.**

**Hallmark lint** (lint only):
- FAIL 20, no stamp: left alone, per your rule.
- WARN 41, `.blocked` sets no text colour: fixed.
- WARN 58, the h1 is 9 words: kept, because it's your copy.

**Measured (final):**
- 75 text nodes at each size, 0 failing AA. The lowest is 6.85:1 (`--muted` on `--panel`).
- The smallest text is 16 px at 720p.
- 0 overflow at 720p and 1080p, and 0 horizontal overflow at 390.
- 0 console errors and 0 outside requests.

**Regressions caught while building:**
- The first build overflowed 720p by 170 px. Fixed by cuts (listed above) and widening the rail to 26 rem.
- The first-sentence regex stopped at "diff.patch", which rendered the gap "Where the edit came from not recorded" in place of a real sentence.
- The no-wrap spans inherited the muted colour of "passed".

## Gaps (honest; for the build phase)

- **No receipt** for the miss, the recompile or the install in the fixture. Freeze the receipt hash if the miss loop writes one.
- **No branch.**
- **Rule version ids:** the old rule has none. Freeze the old and new rule SHA (the proof grid pins SHAs on confirm) to earn the word "self-repair".
- **The rule text:** not in `scenes.js`. `data/rules/fastapi/16062.yml` has `message: Dependency callable classification lru_cache maxsize must be 4096; 1024 is too small for large apps and larger bumps are deferred.` Freeze the old and new `message:` lines to give a true before/after of the rule itself.
- **A live retry:** none recorded. The denial is a proof-harness replay. And live the tier is warn on an Inferred root, so it would warn, not block.
- **A corrected edit passing:** not recorded. A must-pass case for this rule would supply it.
- **The fresh cross-model gate's model:** not named in the log. If it is Spark Open, the gate's log line should say so.
- **The miss's context:** README.md line 139 says the slipping run was in the unguarded arm (the rule recorded 0 hits after the fact). It's not in the fixture; freeze it so the page can say it.
- **The edit is rebuilt,** not the agent's bytes (shown on the page).
