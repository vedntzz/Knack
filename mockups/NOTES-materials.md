# Three materials: notes

All three files have the same DOM, copy, type, glass, timeline and keys. Only the ground under the glass changes. Each file lints clean with sloplint (`--genre atmospheric --scope app`): 0 FAIL, 0 REFLEX, 0 WARN. I used the static tier only; the render tier and Hallmark's two reviewer passes did not run.

## Where every word comes from

- **C2, the interruption.** All of it comes from `bench/demo_block.log` as committed in b8c3032 (the file is gitignored on this branch, so I read it from git). That covers the quote, decided_by, PR link, matched lines 135–136, the 18.7 ms verdict, the 212 ms round trip and receipt `80b311c1`. The hunk is `tests/guard/fixtures/replay/run_neutral_3.diff`. `merged_at` 2026-10-19T21:36:02Z is from `data/roots/airflow/75025.json`.
- **C1, the day.** `mockups/fixtures/day.json`. I made it by rerunning `scripts/demo_block.sh` in a sandbox HOME and then running `knack day --json` in that clone, with no GitHub token. That is why it has one commit, one block and `pulls_error`. The seats are the registry's two Confirmed roots. The dashed seat is the 7 Inferred airflow roots, counted from `data/roots/airflow/`.
- **The miss.** `bench/misses/16062-none-2.bar2.log`, with the refused candidate from `run2.log` and the edit from `16062-none-2.edit.json`. The page says plainly that the edit was rebuilt from the audit, not taken from the agent's bytes.

## Where I pushed back on the brief inside the build

1. **"The block next time" would overclaim.** Every fastapi root is Inferred, and the guard blocks only on Confirmed. The miss sheet says "denied in replay; live, an Inferred root warns; it blocks once a person confirms it." There is no Confirmed root with a recorded miss to use instead.
2. **The two runs don't match.** C2 shows the committed log (18.7 ms, receipt `80b311c1`). The day fixture comes from my rerun, which measured 22.3 ms and 321 ms and wrote receipt `4be4607b`; the receipt chains its timestamp. Before this goes in front of judges, save the log and `day --json` from one run.
3. **The miss is cross-repo.** It's fastapi, on an airflow console, because the only recorded misses are fastapi ones. The real console should only show this repo's misses.
4. **There is no gradflow type called "magma".** `?type=magma` points at the *magma preset*, which is the `eclipse` type. I vendored `eclipseGradient`.
5. **Vendored GLSL edits.** Silk is verbatim. I added an `u_exposure` multiply to both shaders, and a `u_center` uniform to eclipse so the disc sits right of the reading column. I also added one derived token, `--oxblood-glow` (48% L, same hue family), because oxblood at 34% L does not show as a corona at all.
6. **The glass trips Hallmark F24.** That gate flags a hairline border under a wide shadow. The recipe is your decision, so I waived F24 on the record in the stamp.

## Frame time at 1080p

I measured rAF intervals at 1920×1080, DPR 1, in Chrome headless with a real GPU (ANGLE Metal, Apple M5 Pro, 120 Hz). I measured 5 s with the page at rest and 3.5 s across the arrival. rAF is vsync-capped, so these numbers prove headroom, not the cost of each frame. Chrome does not expose GPU timer queries, so I couldn't measure that cost directly.

| | at rest p50 / p95 | arrival p50 / p95 / max | frames > 20 ms |
|---|---|---|---|
| A, silk (half-res canvas) | 8.3 / 8.8 ms | 8.3 / 8.9 / 9.4 ms | 0 |
| B, magma (0.75 res) | 8.3 / 9.0 ms | 8.3 / 8.8 / 9.4 ms | 0 |
| C, still | 8.0 / 10.9 ms | 8.3 / 9.1 / 10.7 ms | 4 at rest (rAF jitter with nothing drawing; not cost) |

On software GL (SwiftShader), the stand-in for a weak laptop GPU, all three held the 60 Hz cap at p95. Cost doesn't separate them.

## A, silk

- **Readability of the quote.** Ivory text measures 11.1:1 behind the quote and 11.2:1 behind the diff (worst 5% of background pixels, sampled from the screenshot). The blur turns the folds into slow light, and nothing competes with the 46px Gambetta.
- **Would anyone guess a model made this?** It passes, narrowly. At noise near zero, half resolution and 0.62 exposure, it reads as lit fabric, not a shader demo. The risk is the colour: teal mixed with sand gives olive, and olive goes muddy on some panels.
- **If it wins:**
  - Take sand out of the ground (ink, teal and a deeper teal) so sand only appears on the seat fill and button hover.
  - Pick a seed whose brightest fold falls outside the reading column.
  - Hold the ground still during the day (see the last section).
  - Drop the postmark's ring text. At 6px it's texture, not words.

## B, magma

- **Readability of the quote.** The numbers are the best of the three: 13.6:1 and 15.3:1, because most of the frame is black. The disc drifts, though, and the rim periodically crosses behind the diff.
- **Warm next to the red word: premium or alarming?** Alarming. The corona sits in the same hue family as "Blocked" (oxblood 15°, red 27°), so the red word loses its monopoly. The screen is already hot before the block lands. At rest it's an eclipse: an omen, sitting in your console all day.
- **Would anyone guess a model made this?** It fails. A glowing ring on black is the most-seen hero on 21st.dev and every AI landing page this year. Judges will clock it in a second.
- **If it wins:** shrink the disc until only a sliver of rim shows at the right edge, and make the corona sand rather than oxblood so red stays exclusive. Honestly, I would not ship it.

## C, still

- **Readability of the quote.** The quote itself is fine at 11.7:1 over ink and teal. The sand plane is the problem: behind the diff, the decision text and Accept, ivory falls to **3.9:1**, and the muted decision text goes lower still. That fails AA. The glass does turn hard edges into soft light beautifully; that part of the brief's bet works.
- **Would anyone guess a model made this?** On the AI test, it passes: no model generates flat Bauhaus planes for a developer tool. On the quiet test, it fails. At rest it's a poster, and it's the loudest of the three when nothing is happening.
- **If it wins:**
  - Recompose so no plane crosses behind text, with sand only as a sliver at the screen edge.
  - Add a fourth plane of ink on top of the teal so the empty day reads as night, not a flag.

## A fourth material

I didn't build one. The best fourth option is A with sand removed and the ground still outside the arrival. That's two parameters, not a new material, and it's in A's change list above.

## Recommendation

Choose **A, silk**, with the changes listed under it. It is the only ground that is premium and quiet at rest, and it reads like fabric under frosted glass, not like rendering. That's the closest of the three to "opening an iPhone box". B tells the user something is wrong before anything is. C is the right control: it proves the glass carries most of the effect. It also proves a material can fail contrast.

## The one thing in the brief I disagree with

**The ground should not move all day.** The brief says the arrival is the only moment the page may assert itself. Then it gives the page a ground that drifts for eight hours and stops only when the block lands, which is the inverse. Render the ground once and leave it still through the silence. Let it move only during the arrival, freeze on "Blocked", and settle back to still on accept. Motion becomes the signal, the way a phone screen waking up is. It also costs nothing at rest.
