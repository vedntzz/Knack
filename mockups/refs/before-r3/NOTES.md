# Knack console, round 3: notes

`final.html` is self-contained and loads only `fixtures/scenes.js` and the vendored fonts. It no longer loads `console.js`, `ground.js` or Motion; those files are untouched.

- **Scenes:** `?scene=day|block|argue|held|recovery`. Argue shows the ESCALATE ruling by default; add `&ruling=hold` for the HOLD ruling.
- **Freezing a frame:** `&t=<ms>`.
- **Serving:** use any static server rooted at `mockups/`.

The flow is block → **Argue** (A) → argue → automatic on ESCALATE → held → **Copy command** (C). Esc dismisses to day from block, argue or held, with the subtext "the edit is already stopped". The primary button sits in the same place in every state. The footer lists only the current scene's keys; day and recovery have none.

## Checks, as last run

- **sloplint** (`--genre editorial --scope app`): 0 FAIL, 0 REFLEX, 1 WARN. The WARN is F24, a hairline under a wide shadow, which this brief's sheet recipe requires; it is waived in the stamp. The lint ran before every capture.
- **Truth:** 59 bindings in each of the six stills, 0 not found in the fixture, 0 console errors, 0 non-loopback requests.
- **Contrast:** computed from the tokens on their surfaces, using oklch → sRGB → WCAG.

  | Text | On sheet | On ground | On the code well |
  |---|---|---|---|
  | ink | 15.8:1 | 16.4:1 | 15.0:1 |
  | muted | 7.3:1 | 7.5:1 | 6.9:1 |
  | red ("Blocked", 34 px) | 4.8:1 | | |
  | sheet text on the ink button | 15.8:1 | | |

  Amber is never used for text.
- **Keys**, driven in Chromium:
  - Tab reaches Dismiss, then the primary button, with a 2 px focus ring on each.
  - A goes to argue, and ESCALATE flows on to held after 4,812 ms.
  - C copies the exact resolve command.
  - Esc goes to day.
- **Reduced motion:** the block loads at its end state, with the thread drawn, the columns at opacity 1 and the odometer at Oct 19 2026.
- **Minimum text** is 18 px at 1080p, which is 12 px at 720p playback.

## Frame times

These are rAF intervals from Playwright 1.59.1 driving chrome-headless-shell 156.0.8078.4 on ANGLE Metal (Apple M5 Pro), with a 1920×1080 viewport at DPR 1, live mode.

| Window | Frames | Median | p95 | Max | > 20 ms |
|---|---|---|---|---|---|
| Block, 0–1.6 s from ready (thread, diff fade, odometer) | 96 | 16.7 ms | 16.8 ms | 16.8 ms | 0 |
| Argue, 0–3.2 s after A (four reveals) | 192 | 16.7 ms | 16.7 ms | 16.8 ms | 0 |

Headless rAF is capped at 60 Hz, so this shows headroom, not cost per frame. No GPU timing is reported because no GPU timer is exposed. There is no WebGL left on the page.

## What I cut

- **The WebGL ground** and all its motion: the planes, the band shader, the grain and the actor tint. The ground is now one solid token. The sheet is solid, with a 1 px top hairline and a deep shadow, and there is no backdrop blur.
- **The pillars and every first-person UI line.** Quotes and the rulings' own words stay verbatim, inside quotation marks.
- **The typing scene, and the day's ticket, commits and PR furniture.** The day now shows seats, the legend, the last receipt and the verify command, and nothing else: no clock and no hour cells.
- **Motion other than the four block steps.** Argue reveals its steps one at a time with a 200 ms fade each; nothing else animates.

## Gaps found (shown as gaps, not filled)

1. **Confirmer line.** Root `airflow-75025-1` has no `confirmed_by` key, and `day.json` has `confirmed_by: null`. "Confirmed in Knack by Vedant Srivastava, Nov 1 2026" is not on record, so the byline's second line shows a dashed gap: "confirmed_by is not recorded in this root".
2. **Spark Open in the argue badge.** Both rulings' traces record a single `"model": "muse-spark-1.3"`, so the badge names only "Muse Spark (api.meta.ai)". The README says held requires both models to escalate, but the trace doesn't show Spark Open running. Either the trace drops the second model or it didn't run. That needs checking in `knack/dispute/` before anyone films a claim about two models.
3. **A second sentence for argue.** Both rulings cite the same sentence as the block, and the root records one quote. The scene adds "the record holds no other words on this".
4. **Recovery is titled "recovery", not "self-repair".** The three miss logs name no rule version ids. Git has two commits on `data/rules/fastapi/16062.yml` (6313444 and 8ddf61e), but those are not one of this brief's recovery sources, so I didn't show them.
5. **No corrected FastAPI edit passing the check.** `data/registry/cases/fastapi-16062/` holds only `must-fail-77322b4d226e.json`, and no must-pass case exists. The bar2 line "every must-pass edit allowed" is therefore vacuous, and the only compliant passes in the logs are held-out variants ("3/3 compliant allowed"). Per the stop rule, **recovery is not filmed.** The recording ends on held, not on a passing corrected edit.
6. **"Denied on retry".** Nothing in the logs shows the hook re-run on the edit. Step 4 shows what the log does say, "PASS cases: every must-fail edit denied", and labels it as the proof's replay. The root is also Inferred with tier warn, so a live hook would only warn on this edit.
7. **"Attempted today".** The block's edit is run 3's recorded diff, replayed through the real hook today (log committed at b8c3032, 2026-11-01). The demo log itself says "an agent's recorded edit (run 3)". So the right column's header reads "Muse Code · run 3, replayed today · blocked" instead of the brief's "attempted today".
8. **Mixed runs.** The block's receipt (`80b311c1…`, from demo_block.log), the day's receipt (`4be4607b…`) and the two rulings (`1983f52b…` on Oct 31, `13f19d15…` on Nov 1) come from four different runs. Each scene prints its own receipt and time.

## Materials (Part 4): skipped

The precondition failed. In github.com/meerbahadin/gradflow (v0.4.0), `src/core/shader.ts` exports one `FRAGMENT_SHADER`. Horizon and topo are the functions `horizonGradient` and `topoGradient` inside it, selected by `type == 19` and `type == 13`; they are not separate fragment shaders. The repo also has no LICENSE file; "MIT" appears only as package.json's `"license"` field, with no notice text. So nothing was vendored and no A/B clips were made. The recommendation stands by default: the control, the plain ground.

## Deliverables

All of these are in `shots/r3/`:

- **Stills at 1920×1080:** `day.png`, `block.png`, `argue.png`, `argue-hold.png`, `held.png`, `recovery.png`, and `contact.png`, which holds all six.
- **`block-argue-held.mp4`:** 16.0 s, H.264 High, 30 fps, at an 8 Mbps target. The page is mostly still, so the file is 1.08 MB.
  - It is rendered frame by frame from the page's own timeline (`window.__film(ms)`), so every frame is exact.
  - Timeline: block 0–5.4 s, with Argue pressed at 4.9 s; then argue 5.4–10.8 s on ESCALATE; then held 10.8–16 s.
  - It was encoded with AVFoundation (`fixtures/encode.swift`), because this machine has no ffmpeg.
- **Reproducing:**
  - `PLAYWRIGHT=… CHROME=… node mockups/fixtures/capture.mjs all`, then `swift mockups/fixtures/encode.swift <frames> <out.mp4> 30 8000000`.
  - `CHROME` is needed because the Playwright package expects browser build 1217 and only 1248 is installed.

## What I'd still change

- **Record one run end to end:** block, argue (escalate), resolve allow, then the corrected `last_run_state` edit allowed, all in one sandbox HOME. That gives one receipt chain and a real "corrected approach succeeds" ending for the film. Today the film can't end on success, because no successful corrected edit is on record for any scene.
- **Fix or explain the single-model trace (gap 2)** before claiming two-model escalation anywhere.
- **Rethink the right branch of the thread.** It jogs around the right header, because the header text sits above the matched token. A narrower header, or a header placed under the rows, would give a straight drop.
- **The quote's two code spans** in mono at 47 px weigh more than the Gambetta around them. 0.78 em might balance better.

## The harshest plausible line from a judge

"It stopped a replayed edit, a model said 'a person will decide', and the film ends before any person, or any fix, shows up."
