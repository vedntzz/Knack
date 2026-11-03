# Knack block screen, round 5 (sumi and shu): notes

`final.html` is the block screen only: a 1280×720 app frame that loads `fixtures/block.js` and `fixtures/fonts/`, with no network.
- 1080p is the same frame at device scale 1.5, and 720p is the frame at scale 1.
- Below 1280×720 the frame scales down with a 16 px margin.
- `?open=1` opens the "Show the change in #75025" toggle, for the second frame.
- `?film=1` with `window.__film(ms)` freezes any moment of the arrival.
- Keys: A presses Argue, Esc dismisses; both ignore Cmd, Ctrl and Alt.
- Round 4 (light ground, Sentry-style rail) is kept unchanged in `refs/before-r5/` (final.html, NOTES.md, SOURCES.md, capture_block.mjs).

Kept from round 4:
- the structure: the comment inside the diff, two columns;
- the `bound()` truth guard (92 bindings, 0 missing in the last capture, 0 console errors, 0 non-loopback requests);
- every source, and the freeze's stop rule (`freeze_block.py` was not touched);
- the banned fonts (Plex and JetBrains Mono, no Geist).

The round-4 rule "dark by default is banned" is overridden by this brief's sumi ground.

## Skills and the rule taken from each

| Skill | Rule applied here |
|---|---|
| design-taste-frontend | Surfaces separate by one tone step, never a line or a shadow. Running text is full washi; grey is for secondary notes only |
| ui-ux-pro-max-chat | `color-contrast` / `color-accessible-pairs`: 4.5:1 for normal text, 3:1 for large, checked per pair |
| impeccable-chat | The brief wins. Refinement keeps the structure, data and guards, and changes only what is in scope |
| emil-design-eng | Arrival uses transform and opacity, plus a colour change for the link only; ease-out `cubic-bezier(0.23,1,0.32,1)`; 30–80 ms stagger; never from scale(0) |
| hallmark-chat | Lint only: tokens at `:root`, no tracked capitals, no `transition: all`. No stamp was written to pass F20 |

## Palette and contrast

Every value is a flat hex in `:root`: no gradient, glow, shadow, opacity or colour-mix.

| Token | Hex | Role |
|---|---|---|
| `--sumi` | #1f1e1c | ground; also the deleted row, the comment band, and the kbd keys inside the raised panel |
| `--raised` | #272623 | the one raised step: code, the "To fix it" panel, chips, inline code |
| `--washi` | #eae6dc | all running text |
| `--grey` | #9a958a | secondary text, the only other grey |
| `--shu` | #e35941 | the stop mark and the word "Blocked", once |
| `--kuchiba` | #c9a04a | the link only: the gold edge from rows 135–136 down the comment, the matched tokens, the underline on "aliasing them onto `DagRun.state` and `DagRun.start_date`" |

**Shu was adjusted for lightness only.** The brief's #E04A2F gives 4.12:1 on sumi. I raised its HLS lightness by 0.04 with the same hue and saturation, to #E35941 (4.58:1), so "Blocked" passes AA even as normal text. At 20 px bold it only needed 3:1.

Contrast was measured three ways:
- computed from the hexes;
- in the browser by critique Assessment B (96 visible text nodes, background taken from the first opaque ancestor, closed and open);
- checked against ui-ux-pro-max's `color-contrast` rule (4.5:1 normal, 3:1 large).

| Pair | Ratio | AA |
|---|---|---|
| washi on sumi | 13.37 | pass |
| washi on raised | 12.14 | pass |
| grey on sumi | 5.58 | pass |
| grey on raised | 5.07 | pass (lowest grey on the page) |
| kuchiba on sumi | 6.83 | pass |
| kuchiba on raised | 6.20 | pass (matched tokens) |
| shu #e35941 on sumi | 4.58 | pass (lowest on the page; large text) |

Assessment B's lowest 8 nodes were "Blocked" at 4.58, then grey on raised at 5.07: the path, the line numbers, the struck chips and the toggle caption. Every node passes AA.

## What changed, by the brief

1. **Palette:** as above. Syntax colouring is off. The deleted row steps down to sumi, and nothing else marks the diff.
2. **Headline:** "This edit aliases state and start_date onto DagRun." / "#75025 chose removal over aliasing. Merged by bbovenzi."
   - The black K box is gone; the wordmark "knack" stands alone.
   - The identifiers are set in the text face, because Taste flagged mixed faces in a headline.
3. **The comment** sits inside the diff after line 136, joined to rows 135–136 by the gold edge. In order:
   - the bold lead;
   - chips: `state` and `start_date` struck through, an arrow, `last_run_state` and `last_run_start_date`;
   - the author line: avatar, Pushkal Gupta, "merged by bbovenzi · Oct 19 2026 · #75025";
   - all three sentences verbatim at 14 px body size;
   - "Aliasing was offered; the merged change didn't take it.";
   - the toggle, closed by default.
4. **The right column has three blocks:**
   - "To fix it" is the raised panel with the 22 px instruction. Argue (A) is an unfilled washi button with `knack argue "<your reason>"` beside it. Dismiss (Esc) is grey, beside "the edit is already stopped".
   - "The decision": one sentence.
   - "Why you can trust this": three figures, 8/8, 0 and 212 ms. Each figure has a tooltip with its definition (gate names; current tree plus release 3.3.2; 18.7 ms verdict by ast-grep).
   - The verifier line at the foot holds rule, root (Confirmed, not seeded), PreToolUse deny, the held-out gate, receipt and time. "Root", "seeded", "held-out" and "PreToolUse" appear nowhere else.
   - No dashed gap boxes; the gaps are listed below.

**The brief's test:** the bold line plus the chips say what to do. Assessment A confirmed this independently.

## Impeccable critique (dual-agent, on build 5)

Method: dual-agent. Assessment A (design review) and Assessment B (detector and browser overlay) ran as two isolated sub-agents.

**Assessment B (evidence):**
- CLI `detect --json`: `[]`, exit 0.
- Overlay injection succeeded (Playwright fallback, no Chrome extension). It reported 1 finding, `cramped-padding` on `.row`.
  - This is a false positive. The first column is a 40 px right-aligned line-number cell with 8 px padding, and the detector does not count the column width.
- The live-server's empty `.impeccable/` was removed.

**Assessment A (design): 32/40, Good. Verdict: PASS WITH P2s.**
- Strengths:
  - the bold line and chips pass the brief's test;
  - gold does a real job: the tokens match the underlined phrase;
  - the quiet layer stays quiet.

| Finding | Action |
|---|---|
| P2-b: the filled Argue button outranks the fix | **Fixed.** Argue is unfilled, and "To fix it" is the only filled panel |
| P2-d: with the toggle open, the diff came within 16 px of the footer | **Fixed.** Spacing tightened; the open frame keeps 28 px (closed: 108 px) |
| P3: the trust figures are undefined | **Fixed without changing your copy:** each figure has a tooltip definition from the fixture |
| Minor: no avatar fallback | **Fixed:** the image removes itself on error, and the name stays |
| P2-a: "removal over aliasing" is said five times (headline, lead, caption, offered, decision) | **Fixed on your call:** the caption under the chips is removed |
| P2-c: the chips say rename but the fix says delete, so someone might rename 135–136 and duplicate 137–138 | **Fixed on your call:** the lead ends "…instead, already on lines 137–138", and the fix reads "Lines 137–138 already use the right names." |
| Jordan persona: `edit_file` is a tool name in the top bar and the file header | Not changed; it is the real tool name from the log |

The fixes after build 5 were not re-scored by a fresh Assessment A. Impeccable's verdict stands at **PASS WITH P2s (32/40)**: the two layout P2s are fixed, and the two copy P2s wait on you.

## Impeccable re-score (dual-agent, after the copy changes)

**Method:** dual-agent, with fresh isolated Assessment A and Assessment B.

**Verdict: PASS WITH P2s, 33/40 (Good), up from 32.**
- Assessment B:
  - CLI `[]`, exit 0;
  - the overlay gives the same `cramped-padding` false positive on the diff gutter;
  - all 94 text nodes pass AA (lowest: "Blocked" 4.58, grey on raised 5.07).
- Assessment A credits the corrected fix line: it now agrees with the chips.

Open, not applied (each touches your pinned copy or layout):

| Level | Finding | Critic's fix |
|---|---|---|
| P2 | Restatement is still high: H8 scores 2/4 | Shorten or drop "The decision"; fold "Aliasing was offered" into the attribution |
| P2 | The h1 competes with the bold lead; the headline credits bbovenzi and the comment credits Pushkal Gupta | One-line h1; move "Merged by bbovenzi" into the author row |
| P2 | "212 ms" is labelled "no AI model"; "0 false alarms" has no denominator | "212 ms / plain code, no model"; "0 / of N Airflow edits checked" |
| P3 | The 720p small text: verifier line 11.5 px, labels 12–13 px | Verifier line 12 px, labels 13 px |
| P3 | "the edit is already stopped" beside Dismiss could read as "dismissing lets it through" | "close; the edit stays blocked" |

Persona flags: Alex has no key or copy action for the primary fix. Jordan sees two names and the rename-looking chips.

**Clip re-filmed after the copy change.** `block-arrival-5s.mp4` (150 frames, 30 fps) matches the current copy; its last frame differs from the still by 8 anti-aliased pixels.

## Other gates

- **Taste `inspect.mjs --app`: 0 FAIL, 2 WARN.** Both warnings are defended:
  - `palette-cream` is washi #eae6dc, pinned by the brief;
  - `ragged-row`: the rail is a stack of three blocks, not a card paired with the diff, and stretching the diff produced a `panel-void` instead.
  - Round 1 failed `edge-text` at 390 px because the scaled frame had no margin; fixed with the 16 px scaled margin.
- **Taste `lint.mjs --app`: 0 FAIL, 7 WARN.** All are monospace on code, paths, the receipt and kbd keys, which the app rules allow.
- **Hallmark `sloplint`: 1 FAIL, 2 WARN.**
  - F20 (no Hallmark stamp) stays failed: the brief forbids writing one to pass.
  - The two WARN 3 "side stripes" are the gold connecting mark the brief asks for, plus its invisible spacer on plain rows.
  - The off-scale padding REFLEX (97 px) was fixed to 100 px, which also aligns the comment with the code column.
  - Floor 10 (no middle-dot meta) conflicts with the brief's author line "merged by bbovenzi · Oct 19 2026 · #75025", which keeps its dots. The linter did not flag it.
  - The render tier was not run.

## Motion (emil-design-eng), after the critique

| What | Start | Duration | Easing |
|---|---|---|---|
| The agent's 6 rows rise 4 px and fade in | 300 ms, 30 ms stagger | 220 ms each | `cubic-bezier(0.23,1,0.32,1)` |
| The comment's 7 parts, lead first | about 0.75 s, 60 ms stagger | 220 ms | same |
| The link: the gold edge and tokens go from base to kuchiba, then the underline | about 1.43 s | 240 ms | `ease` (a colour change) |
| The rail's three blocks | about 1.83 s, 80 ms stagger | 220 ms | ease-out |

- The frame is still from about 2.2 s, and the 5 s clip holds the end state.
- "Blocked", the seal and the headline never move: the stop is the hook's result, not a performance.
- The toggle's chevron turns in 160 ms. Argue's press is 140 ms `scale(0.97)`.
- Reduced motion creates no animations and shows the end state.
- Film check: the last frame matches the still apart from 7 anti-aliased pixels.

## Gaps (listed here, not drawn on screen)

1. **The block's exact time.** The receipt's sandbox HOME was deleted by `scripts/demo_block.sh`.
   - The verifier line shows "log committed 2026-11-01 13:09:04 −05:00", the commit time of `bench/demo_block.log`.
   - Its tooltip says the block's own time was not kept.
   - Fix: keep the sandbox `verdicts.jsonl` on the next demo run.
2. **The receipt id** comes from the log's Console link, not from a live `verdicts.jsonl` row (unchanged from round 4).
3. **Confirmer.** The root has `confirmed_by: null`. Round 4 showed this as a dashed gap; it is now off screen. The author line carries the recorded "merged by bbovenzi".
4. **"The decision" is plain-English UI copy,** your sentence, not the root's verbatim `decision`. Its names are taken from the fixture.
5. **The third sentence** ("Happy to alias instead…") is now on screen. It is verbatim from the PR body (`refs/github-75025.json`), consecutive with the first two. The root and the log do not carry it; the fixture holds it as `quote.not_recorded`.
   - The headline says "chose removal over aliasing", not "rejected", which matches it.
6. **Hunk trimmed to fit 720.** Context rows 131–133 and 139–142 are not shown, so the diff starts at the removed line 134 and ends at 138. "1 line removed, 6 added" still counts the whole hunk.
7. **The toggle shows #75025's change once,** captioned "public/dags.py line 132 and ui/dags.py line 139, the same line in both". The code only merges the two files when their lines are identical; otherwise it lists both.
8. **The edit is a recorded edit replay** (real hook, no model calls) of run 3's recorded diff. **Argue goes nowhere** in this frame (unchanged from round 4).

## Captures, `shots/r5/final/`

- `block-1080p.png`: 1920×1080, toggle closed
- `block-720p.png`: 1280×720, toggle closed
- `block-open-1080p.png`, `block-open-720p.png`: the toggle open, the second frame
- `block-reduced-1080p.png`: reduced motion (matches the still)
- `block-arrival-5s.mp4`: 5.0 s, 1920×1080, H.264, 30 fps, 8 Mbps target, frame-stepped and encoded with `fixtures/encode.swift`
- `frames/`: the 150 source frames

Earlier builds are in `shots/r5/b1`–`b5`; Taste's inspector shots are in `fixtures/taste/r5/`. To reproduce:

```
PLAYWRIGHT=<playwright/index.mjs> CHROME=<chromium> node mockups/fixtures/capture_block.mjs stills --out shots/r5/final
PLAYWRIGHT=… CHROME=… node mockups/fixtures/capture_block.mjs film --out shots/r5/final
swift mockups/fixtures/encode.swift mockups/shots/r5/final/frames mockups/shots/r5/final/block-arrival-5s.mp4 30 8000000
```
