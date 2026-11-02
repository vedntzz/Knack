# Knack block screen, round 4: notes

`final.html` is now the block screen only. It is a 1280×720 app frame that loads `fixtures/block.js` and `fixtures/fonts/`, with no network. 1080p is the same frame at device scale 1.5, and 720p is the same frame at scale 1, so 12 px meta text is still 12 px at 720p. The round 3 five-scene console and its notes are kept unchanged in `refs/before-r3/`. All values and their sources are in `SOURCES.md`.

- **Keys:** A presses Argue, Esc dismisses. Neither animates, and both ignore Cmd/Ctrl/Alt.
- **Freezing a frame:** `?film=1`, then `window.__film(ms)`.
- **Reduced motion:** renders the end state.

## The idea

The PR comment becomes an inline review thread inside the agent's diff, directly under the two lines it forbids. Pushkal Gupta's words arrive inside the edit, the way a GitHub review comment sits between lines 136 and 137.

## 1. References

The Claude-in-Chrome extension was not connected, so I took the screenshots with headless Chromium (Playwright 1.59.1) at 1920×1080. URLs are in `SOURCES.md`.

- **GitHub #75025:** two shots, the quote paragraph and the description header with avatar, handle and timestamp.
- **Graphite:** graphite.dev returned "Page not found".
- **lazyweb:** returned only landing-page growth scores, no product screens.
- **Sentry:** the issue page needs a login, so I used Sentry's documented issue-details screenshot.
- **Linear:** the only review/issue screen reachable was its docs image. It is weak: small, dark, and its comment is not above code.

**Structural reference chosen: Sentry issue details.** Its anatomy matches this frame's job one for one:
- a header that names what failed and its state;
- one workflow action;
- a stack frame with file:line and the guilty line highlighted;
- a narrow right rail of metadata.

The baseline anatomy for the human's words is the GitHub comment (avatar, name, handle, date, body, code context). Sentry gives "what stopped", GitHub gives "who said no".

## 2. ui-ux-pro-max brief

- **`--design-system` (variance 4, motion 2, density 8):** proposed Dark Mode (OLED) with glow, a FAQ-landing pattern, and JetBrains Mono / IBM Plex Sans. Dark by default and glow are banned, so both are overridden.
- **Style (`--domain style`):** Minimalism & Swiss (light, high contrast, grid-based, no shadows or gradients), with the Data-Dense rules (8–12 px padding, dense but readable).
- **Font pairings (`--domain typography`), none on the banned list:**
  - **IBM Plex Sans + JetBrains Mono ("Developer Mono")** — chosen;
  - Fira Sans + Fira Code ("Dashboard Data").
- **UX guidelines (`--domain ux`):**
  - contrast at least 4.5:1, with no grey on grey;
  - body line height 1.5–1.75;
  - 65–75 characters per line;
  - never colour alone for meaning;
  - visible hover and press feedback.

## 3. Taste (design-taste-frontend)

App-screen run (`references/app-screens.md`), `draw.mjs --app --kind devtools --screens detail --theme light`.
- **Dealt:** `framed-sheet` and `achromatic-ledger`.
- **Chosen:** **achromatic-ledger, seed 1662991229.** It is the only style with zero hue in the chrome, which is what "red only for the stop, one accent once" needs.

**Dials** (Taste v2's `draw.mjs` has no dial flags; I applied these by hand and passed them to ui-ux-pro-max):
- design variance 4/10: asymmetric 1fr + 336 px rail, no bold layout tricks;
- motion intensity 2/10: three moves, all under 300 ms;
- visual density 7/10: 13 px code on a 20 px pitch, 12–17 px text.

**What Taste decided:**
- open-plane shell with no sidebar;
- one ground (#f3f5f8) and a white sheet;
- near-black primary;
- the sheet's one hue (#1d5fbf) moved onto the link from the words to the code;
- tight radii (6/4);
- one sans plus mono for code and IDs only;
- tabular figures;
- the face: the GitHub-comment anatomy inside a diff;
- the signature element: the matched rows linked to the underlined phrase.

**Overrides:** Geist (dealt) → IBM Plex Sans, because Geist is banned.

**Gate:** `lint.mjs --app` gives 0 FAIL, 7 WARN, all monospace on code, paths, the receipt hash and kbd keys, which app rules allow. `inspect.mjs --app` gives 0 FAIL, 0 WARN. Working files are in `fixtures/taste/`.

## 4. Impeccable: critique and audit of the static frame

Dual-agent run: Assessment A (design review) and Assessment B (detector and browser evidence) as two isolated sub-agents. B used a Playwright fallback because there was no browser extension. The snapshot was not persisted, because `.impeccable/critique/` is outside the paths this brief lets me edit. B's live server created an empty `.impeccable/live/`, which I deleted.

**First run on build 2:**
- **Nielsen 23/40** (Acceptable); **audit 14/20** (Good). Detector CLI: 0 findings. In-page overlay: `nested-cards` ×1 and `cramped-padding` ×2. The cramped-padding hits are a false positive: diff rows run full-bleed by convention.
- **P1s:**
  - "who said no" was the weakest answer: the H1 named a PR number, not a person, and the bold name was the handle;
  - "−7 +12" over a hunk that shows −1 +6;
  - three nested bordered boxes;
  - Dismiss had no focus ring (`all: unset` beat `:focus-visible`).
- **P2s:**
  - the rail repeated the top bar;
  - the `✓` glyph used as an icon;
  - the blue link had no key;
  - the A and Esc keys did nothing;
  - a JBMono 500 weight was synthesised.
- **All fixed:**
  - the H1 names Pushkal Gupta;
  - the counts are computed from the rows shown;
  - there is one bordered box, the thread is a ruled band, and #75025's code sits on a tint;
  - the focus ring is fixed;
  - the rail is cut to rule, root, confirmer and times;
  - "8 of 8 gates pass" with the names;
  - "matched airflow-75025" labels the hit rows and the 3 px coloured left bar is gone;
  - the keys act.

**Re-critique on build 4** (fresh Assessment A): **28/40 (Good), verdict PASS WITH P2s.** Its P2s were fixed in builds 5–6:
- Argue now shows its outcome, `knack argue "<your reason>"`;
- a "To comply" line was added;
- the context well is gone;
- strike-through is gone and code is 13 px;
- "Blocked" is 18 px;
- the name shows once with the handle;
- "matched" appears once;
- "Confirmed" is in 600 weight;
- timezone written as "−05:00".

**Impeccable's final verdict: PASS WITH P2s, 28/40, with those P2s since fixed. The fixed version was not re-scored.** Detector on the final file: `[]`, exit 0.

Where Impeccable overruled the others:
- the coloured left bar (Taste and GitHub convention) went;
- the strike-through on deleted lines went;
- the nested well went.

## 5. Motion (emil-design-eng), after Impeccable passed

Only three things move, all transform, opacity or colour:

| What | Delay | Duration | Easing | Why |
|---|---|---|---|---|
| The code appears: the agent's 10 rows, then #75025's 4 rows | 300 ms, then 30 ms stagger | 200 ms each, 4 px rise | `cubic-bezier(0.23, 1, 0.32, 1)` | Entering, so ease-out (Emil: never ease-in). 200 ms is inside his 150–250 ms band for UI, and 30 ms is the low end of his 30–80 ms stagger. The human's words are on screen from 0 ms and the edit arrives around them: "already decided" is shown by order, not by a caption |
| The link: the phrase's underline colours in, then the matched tokens and rows tint | about 1.21 s | 240 ms (underline), 200 ms (tokens, 80 ms later) | `ease` for the colour change, the custom ease-out for the tints | Emil: colour changes take `ease`. Underline first, code second, so the eye goes from words to code. It is the only accent motion on the frame |
| The date: "Oct 19, 2026" rolls up into its clipped slot | about 1.65 s | 240 ms | `cubic-bezier(0.23, 1, 0.32, 1)` | State indication: the decision's date lands last, after the evidence. A short roll in its own clip, never from scale(0) |

- The frame is still from about 1.9 s.
- The stop, "Blocked", the title, the rail and the actions never animate. The stop is the hook's result, and Emil's rule is that keyboard-initiated and system results do not perform.
- Argue's press is 140 ms `scale(0.97)` and is feedback, not an entrance.
- `prefers-reduced-motion: reduce` creates no animations, so it shows the end state.
- Checks:
  - the film's last frame differs from the still by at most 1/255 per channel (colour-mix rounding);
  - the reduced-motion capture matches the still to the same 1/255.

## 6. Hallmark (sloplint)

`sloplint.mjs mockups/final.html --genre modern-minimal --scope app`: **1 FAIL, 0 REFLEX, 0 WARN.**
- **The FAIL is F20, "no Hallmark stamp on the first line of the CSS".** The brief forbids writing a stamp to pass lint, and no design change can satisfy that rule, so it stays failed.
- **Fixed by changing the design:**
  - 12 off-4 px spacings;
  - no `:disabled` state;
  - no `text-wrap: balance` on headings;
  - no meta description;
  - a mono "label voice" (the Argue command is now real `<code>`).
- **Render tier:** not run (no puppeteer-core on this machine).
- **Conflict with Floor 10 (no middle-dot meta strings):** the fixed proof string "212 ms round trip (18.7 ms verdict) · ast-grep · 0 model calls in this hook" has middle dots. The brief says never change it, so it stays. The linter did not flag it.

## Gaps (shown as gaps, or left out, never filled)

1. **The block's exact time.** The receipt `80b311c17a39…` was written to a sandbox HOME that `scripts/demo_block.sh` deletes on exit, and the log does not print its `time` field.
   - The frame shows "Blocked at: exact time not kept" as a dashed gap.
   - Next to it is the only real timestamp on record, "Log written 2026-11-01 13:09:04 −05:00", which is the commit time of `bench/demo_block.log`.
   - Fix: keep the sandbox's `verdicts.jsonl` (or print the receipt's `time` in the log) on the next demo run.
2. **"The live receipt id from verdicts.jsonl."** The id shown comes from the log's Console link, because the sandbox `verdicts.jsonl` is gone. `~/.knack/verdicts.jsonl` holds only live-smoke denies at line 28 with other edits, so using one of them would mismatch lines 135–136 and the 18.7 ms latency.
3. **Confirmer.** Root `airflow-75025-1` has no `confirmed_by`. The rail shows "Confirmer: not recorded in this root". The confirmer line the root does record, "Pushkal Gupta (author); approved and merged by bbovenzi", is shown verbatim in the thread header.
4. **Rule id.** The brief says "rule airflow-75025-1". That is the root's id; the ast-grep rule is `airflow-75025` (`data/rules/airflow/75025.yml`, and `rule_id` in every receipt). The frame shows both, each under its own label.
5. **The third sentence (read this one).** In the PR, the two quoted sentences are followed by: "Happy to alias instead if you would rather keep the advertised names working." It is in neither the root nor the log, so it is not on the frame.
   - It softens "rejected": the author offered the alias, and bbovenzi merged the version without it.
   - Before filming "Pushkal Gupta rejected that", decide whether the root's quote should carry this sentence, or whether "rejected" should become "chose against".
6. **The edit is a replay.** It is run 3's recorded diff, sent through the real user-level hook (the log says "an agent's recorded edit (run 3)"). The frame says "This edit", never "attempted today", and does not name the agent.
7. **Argue goes nowhere here.** The press gives feedback and shows the real dispute command from the log. The argue and held scenes are in `refs/before-r3/final.html`.
8. **References.** No Graphite screen, and the Linear one is weak (see section 1).
9. **The 5-second read was judged by two review sub-agents, not by people.**

## The harshest line

The fresh Impeccable reviewer, after 5 seconds: "That's a real tool. It looks like a GitHub review pane that caught my agent red-handed. So what does Argue actually do, and why is a hook drawing a window?"

My honest answer: **real data, mockup page.**
- Every value comes from the record, and nothing on it is hand-typed.
- But no shipped Knack surface renders this page. The hook returns a deny envelope to the agent, and the log's `Console: http://127.0.0.1:7655/verdict/<hash>` is where a human would look.
- **What would make it a real tool:** serve this exact page from that Console verdict route with a live receipt, keep the sandbox receipts so "Blocked at" has its own time, and film the browser on 127.0.0.1. "Why is a hook drawing a window" then has an answer on screen: the window is the URL in the deny message.

## Captures

`shots/r4/final/`:
- `block-1080p.png` (1920×1080)
- `block-1080p-downscaled-to-720p.png` (the same PNG downscaled)
- `block-720p.png` (rendered at 1280×720)
- `block-reduced-1080p.png`
- `block-arrival-t0.png` (the first film frame)
- `block-arrival-5s.mp4`: 5.0 s, 1920×1080, H.264 30 fps, about 8 Mbps target. It is frame-stepped from `window.__film(ms)` and encoded with `fixtures/encode.swift`.
- `frames/`: the 150 source frames.

Earlier builds are in `shots/r4/build1`–`build6`. To reproduce:

```
.venv/bin/python mockups/fixtures/freeze_block.py
PLAYWRIGHT=<playwright/index.mjs> CHROME=<chromium> node mockups/fixtures/capture_block.mjs stills --out shots/r4/final
PLAYWRIGHT=… CHROME=… node mockups/fixtures/capture_block.mjs film --out shots/r4/final
swift mockups/fixtures/encode.swift mockups/shots/r4/final/frames mockups/shots/r4/final/block-arrival-5s.mp4 30 8000000
```
