# Knack design rules
Purpose: one remembered moment. The block is the peak; the corrected edit passing is the end. Everything else is quiet.

## The tool is dark; the human is paper.
The console, the agent's code and every figure Knack measured sit on a cool near-black ground. The only light surfaces are paper: the human's words, set as a note between the agent's forbidden lines and its correct lines, and the fix, the second piece of paper. A light surface always means "a person wrote or must act on this"; nothing the tool says is ever paper.

## Principles (each with its test)
- Ma — empty space is content. Test: does filling it improve understanding? If not, leave it.
- Kanso — remove until it breaks. One message and one primary action per state. Test: remove it; can a stranger still say what stopped, why, who said no, what to do? If yes, it stays out.
- Shibui — subtle, not loud. No glow, gradient, glass, grain or planes. Test: at 50% video scale it still reads; if not, fix size and contrast, never add effects.
- Seijaku — stillness. One move per beat, then dead still; nothing loops. Test: any frozen frame makes sense.
- Wabi-sabi — real, not perfect. Real data, real times with seconds. Test: a judge can run the shown command and get the same output.
- Yugen — suggest, don't explain. Quote plus link carry the decision; no explainer panels.
- Material honesty — remove any effect; if the product still works, the effect was decoration.
- Squint test — only "Blocked", the note, the fix and the gold thread stand out.

## Rule book
Refactoring UI (hierarchy by weight and shade first, space between groups larger than within, depth from lightness, fewer borders) and the 8-point grid (4, 8, 12, 16, 24, 32, 48, 64). Sentence case. No monospace except code, hashes and commands. No eyebrows, no tracked capitals, no hairline rules, no shadows at rest, no icons in tinted squares.

## Palette
Every colour is a token in `knack/console/static/console.css`; nothing else is allowed.

| Token | Hex | Role |
|---|---|---|
| `--ground` | #0B0C0E | the page |
| `--panel` | #131418 | the agent's code, one step up |
| `--raised` | #1C1E23 | key caps and the pressed state, one more step |
| `--text` | #E6E7EA | all running text on dark |
| `--muted` | #9A9EA6 | secondary text on dark: line numbers, labels, the verifier line |
| `--paper` | #F6F6F4 | the human's note and the fix |
| `--paper-raised` | #E9E9E6 | the command well on paper |
| `--ink` | #0A0A0B | text on paper |
| `--ink-muted` | #4D4F55 | secondary text on paper |
| `--red` | #FF5A47 | the stop seal and the word "Blocked" only |
| `--gold` | #D8C08A | the quote-to-code link on dark only |
| `--gold-paper` | #7A5E00 | the same link where it crosses paper |

Red and gold never share a meaning, and no other hue exists. No gradients, glass, glow or planes.
All text WCAG AA, measured (see `knack/console/NOTES.md`).

## Type
IBM Plex, self-hosted under the OFL (`knack/console/static/fonts/OFL.txt`).
- Plex Serif — the human's words, and only those.
- Plex Sans — everything the tool says.
- Plex Mono — code, hashes and commands.

The page is a 16:9 composition sized in rem; 1 rem = min(100vw / 80, 100vh / 45), so 16 px at 1280×720 and 24 px at 1920×1080. Sizes (at 720p, ×1.5 at 1080p): 12, 14, 16, 20, 28, 40. Three weights: 400, 500, 600. Minimum 12 px at 720p, so 18 px at 1080p.

## Boards
- Bar — wordmark, the repo, branch and file as plain text, the receipt's short hash and time on the right. No chrome.
- Verdict head — the red seal reading "Blocked", then one sentence naming the PR that rejected this, then where it stopped.
- Code board — the agent's proposed lines on `--panel`, numbered. The matched lines carry a gold gutter and gold tokens. The note hangs inside the board directly under the last forbidden line, so the correct lines continue beneath it.
- Note (paper) — the full verbatim quote in Plex Serif, the rejected phrase underlined in gold, then who wrote it, who merged it, when, and the PR; then what was offered and not taken.
- Fix (paper) — the instruction as the heading, the lines that are already right, and the argue command with a copy button.
- Figures — three measured numbers in a column, each with its label: checks passed, false alarms, time to decide.
- Verifier line — the full receipt hash, the rule, the root with its honest label (Confirmed / Inferred / Unknown) and seeded flag, and the time.
- Gap — a missing field is its label plus "not recorded" in `--muted`, never an invented value.

## Motion
One move per beat, then dead still: the seal lands, the note arrives, the gold thread draws, the fix arrives, the figures count up once. Nothing loops. `prefers-reduced-motion` shows the final frame. Timings and easing are justified in `knack/console/NOTES.md`.
