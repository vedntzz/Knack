# Landing (reference mockup): notes

This is a reference mockup only. Nothing is under `knack/`, and nothing is committed. It reuses `../argue/argue.css` (tokens, Plex faces, the rem frame, the bar, the paper note, the code lines and the copy button) and adds `landing.css`.

- **Page:** `mockups/landing/index.html`. `?t=<ms>` holds the hero's rise at one moment.
- **Data:** `scenes.js` (`proof`, `receipts_verify`, `readme`, `root`, `spark`, `spark_open`, `hold`, `escalate`, `miss`), `block.js`, and the block page's 1080p capture. SOURCES.md lists every value.
- **Capture:** `PLAYWRIGHT=<playwright/index.mjs> node mockups/landing/capture.mjs` → `mockups/shots/landing/`. It takes the first screen at 1080p and 720p, the full page at both, the 390 full page, reduced motion, the beats and `report.json`.

## Structure (one claim per section)

1. **Hero:** the brief's headline; one action, the reproduce command with Copy; and the real block page as the picture, large, with a caption naming its receipt.
2. **From a pull request to a stopped edit:** the three steps, each carrying its own real material, so the row is not three identical cards:
   - the person's words on paper;
   - the eight gates the rule passed;
   - the blocked lines with the red "Blocked" and "No model, no network."
3. **Meta's models:** a real table with four rows. Each row gives the model, where it runs, its job, and what the recorded traces show.
4. **Every number here has a command:** 8/8, 0 and 37, then the three commands (reproduce, receipts verify, install).
5. **The demo:** the labelled slot.
6. **The close:** the wordmark at full size.

## Where I departed from the brief, and why

| Asked | Built | Reason |
|---|---|---|
| "Muse Code hosts the hooks" | The row is there, with the job as you wrote it. Where it runs: "Host not recorded". Traces: "The block's trace records the `PreToolUse` hook on `edit_file`. The agent's name not recorded." | **Tooling / truth:** no fixture names Muse Code. The hook is recorded; the agent isn't. |
| "Muse Spark Open on Baseten corroborates and attacks rules" | The job as written, the host and model from `spark_open`, and "Spark Open run not recorded. These fixtures freeze only its client's model and host." | No trace in the fixtures shows Spark Open at work. Claiming a run would break "never claim a model ran unless its trace shows it". |
| Muse Spark's jobs | Each job is backed by a trace found at runtime: ruled hold, ruled escalate, recompiled fastapi-16062, extracted fastapi-16062-1. | **Depth:** each claim can be checked against a fixture. |
| Install command with Copy | "Install command not recorded" in an empty well. | Not in any fixture. README.md has one; freeze it as `readme.install`. |
| Repo link | "Repo link not recorded" (bar and footer). | Not in any fixture. Freeze it. |
| Real numbers "with their verify commands" | 8/8 and 0 share `bash scripts/reproduce.sh`, which regenerates the proof grid. 37 has `knack receipts verify`. 18.7 ms and 212 ms appear in the block row of the models table, not as figures. | The latency's verify command (re-running `scripts/demo_block.sh`) is not in a fixture, so it is not given a figure with a command. |
| The block capture as the hero | `shots/kn80/verdict-1080p.png`, on a `--panel` mat, captioned with its own receipt. | It is a different run from `block.js` (5e8a44648bd0 and 16.5 ms against 80b311c17a39 and 18.7 ms). The caption keeps the two apart. |
| A "How it works" heading | "From a pull request to a stopped edit" | Hallmark read "How it works" as an eyebrow (FAIL 54). A heading that says something passes. |
| Headline length | Kept verbatim (13 words). | Hallmark WARN 58 wants 7 or fewer. It's your copy, and it sets in two lines at every width. |

## Motion

| Beat | Move | Easing and duration | Why |
|---|---|---|---|
| The first time the picture is 20% in view | The hero picture rises 1.5 rem from opacity 0, once. The observer then disconnects. | `cubic-bezier(0.23,1,0.32,1)`, 600 ms | It is the one move the brief allows. It is ease-out because the picture is entering. 600 ms because a large surface needs longer than UI feedback to read as arriving rather than blinking. On a first visit it plays on load, because the picture is above the fold. |

- Under reduced motion, or with no IntersectionObserver, nothing moves. Without script, the picture is simply there: the hidden state is applied by script, never by CSS.

## Critique

**Impeccable detector** (rendered page, after fixes): 0 findings at 1280×720, 1920×1080 and 390×844. Before the fixes it found:
- a `cramped-padding` warning on the code box (fixed with right padding);
- two stragglers, "network." and "3.3.2" (fixed with no-break spans).

**Design review (mine, against the full-page screenshots):**
- **5 s test, muted, 720p:** the headline, then the red "Blocked" and the paper quote inside the picture. A judge sees the product doing its one job before reading a word of the sections. **Pass.**
- **Frame:** one pair of equal margins at every width, now matched to the bar. An earlier build capped the container at 76 rem, which left the content 32 px inside the bar's edge.
- **Weakest part:** the gaps. "Repo link not recorded" in the bar and "Install command not recorded" are the honest state of the fixtures and the two most urgent things to freeze. A landing page without them can't convert.
- **The demo slot** sat alone on the left half of the screen. The heading now holds the left column, beside it.

**Hallmark lint (lint only):**
- FAIL 20, no stamp: left alone, per your rule.
- FAIL 54, eyebrow: fixed.
- WARN 58, h1 length: kept, it's your copy.
- WARN 41: in `argue.css`, not this page.

**Measured (final):**
- 121 text nodes at 1080p and 720p, and 113 at 390, 0 failing AA. The lowest is "Blocked", ink on red, at 6.41:1.
- Min 16 px at 720p.
- 0 horizontal overflow.
- 0 console errors and 0 outside requests.

## Gaps (for the build phase)

- The repo link and the install command.
- Any trace that names **Muse Code** as the agent (for example, `hookSpecificOutput` plus the client's name in the block log).
- Any recorded **Spark Open** run: a corroboration or an attack log line naming `muse-spark-open-1026`.
- A frozen command for the latency figures.
- **One block run for both hero and text.** Re-capture the block page from the `80b311c1` run, or re-freeze `block.js` from the `5e8a4464` run, so the picture and the text share one receipt.
- The demo video itself.
