# KN-80: the block screen as a console page

Served at `/verdict/<hash>`, the URL the deny already prints. The page is built from the verdict JSON, the root it cites, the rule's stored proof and the receipt's edit snapshot. A browser asking for HTML gets the page; any other client gets the same JSON as before. `/` waits on `GET /events` and switches to a new deny when one lands. `KNACK_CONSOLE_RECEIPTS` points the console at kept receipts, such as `bench/demo_block.receipts.jsonl`.

Live demo:
```
KNACK_CONSOLE_RECEIPTS=$PWD/bench/demo_block.receipts.jsonl KNACK_REGISTRY=$PWD/data/registry/airflow.json knack console
bash scripts/demo_block.sh    # with http://127.0.0.1:7655/ open
```

## What changed from the draft (mockups/final.html, round 5), and why
The brief's draft, `mockups/refs/knack-board-preview.html`, does not exist in the repo or its history. On Vedant's call, round 5's `final.html` served as the draft.

| Draft | Shipped | Why |
|---|---|---|
| Warm sumi ground #1f1e1c, kuchiba gold #c9a04a, shu #e35941 | Cool #0B0C0E / #131418 / #1C1E23, gold #D8C08A and #7A5E00, red #FF5A47 | These are the brief's locks. |
| The comment was a dark band inside the diff | A paper note hung between line 136 and line 137 | "The tool is dark; the human is paper": the human's words are the only light thing next to the code. |
| "To fix it" was a label above a raised panel | The instruction itself is the heading of a paper card | Removes the eyebrow. The fix is the second piece of paper. |
| A fixed 1280×720 frame scaled with a transform | A rem-based 16:9 composition: 1rem = min(1.25vw, 2.22vh), stacked below 760 px | A real page that is exactly 1.5× at 1080p and still reflows on a phone. |
| Every value bound from a frozen `block.json` | Every value derived on the server from the verdict JSON, root, proof and snapshot; a missing field renders "X not recorded" | A real console, not a fixture. Tests cover each gap. |
| Gold edge down the comment | One SVG thread: under the gold gutter of lines 135–136, down the margin, into the note, meeting the underline of `DagRun.state` | The link is literal: the quote's code spans are the same identifiers the matched code spells. |
| 212 ms round trip as the headline figure | The receipt's own `latency_ms` (e.g. 15.3 ms) | See Gaps. |
| Argue and Dismiss buttons with keys | The `knack argue` command with a Copy button | The page can't argue or dismiss for you; the command is the real action. |
| JetBrains Mono, Plex Sans | Plex Serif (the human), Plex Sans (the tool), Plex Mono (code, hashes, commands), self-hosted with the OFL | The brief's font locks. |

## Motion (`static/motion.js`)
One move per beat, then still. Nothing loops, and it only runs on a deny.

| Beat (ms from load) | Move | Easing, duration | Why |
|---|---|---|---|
| 120 | The "Blocked" seal goes from scale 1.35 and opacity 0 to rest | `cubic-bezier(0.5,0,0.75,0)`, 200 ms | A stamp accelerates into the paper and stops dead. This is an impact, not a UI response, so it is the one deliberate ease-in. It is short enough to read as a hit. |
| 520 | The note rises 0.75 rem and fades in | `cubic-bezier(0.23,1,0.32,1)`, 420 ms | A strong ease-out arrives fast and settles slowly. It is long enough to see on muted video and lands before the thread starts. |
| 1000 | The gold thread draws | linear, 520 ms over both segments, split by length | A constant-speed pen stroke. Easing a two-colour path would make its speed jump at the paper edge. |
| 1560 | The figures fade in (160 ms) and count up once over 700 ms (ease-out cubic, tabular figures) | | The proof counts in after the link is made. |
| 2160 | The fix card rises | same as the note | The last beat is the instruction, so the frame you remember is what to do, not a number. |

The thread is measured before any start frame applies; measuring while the note sat 0.75 rem low made it miss the underline by 12 px (critique P0, fixed). Measured after the fix: 0 px off at 720p and at 1080p. Under `prefers-reduced-motion` nothing animates and the thread is drawn at once. With no script, all content is present and only the thread is missing.

## Impeccable critique (dual-agent: A design review, B detector)
- **Verdict:** specific, not generic. The paper note inside the diff, the gold thread and the paper fix belong only to this product. Heuristics scored 25/40, held down by an Operate-mode tool with one action.
- **Detector (B):** templates gave 0 findings. Live page via CDP: 0 findings at 1280×720 and 1920×1080. At 390×844 there were 2 findings: the board path overflowed by 78 px.
- **Lints:** taste's `[mono]` fired on the Plex Mono token and hallmark's stamp, reduced-motion, focus and overflow checks fired on the templates read without their stylesheet. All are false positives for this brief.

Fixed after the critique:
1. **P0:** the thread landed 12 px below the underline. It is now measured before the arrival starts (0 px).
2. **P1:** the attribution line was 14 px. It is now 16 px with the name at 600, so who decided reads in 5 s at 720p.
3. **P2:** the figures out-weighed the fix. They are now 28 px/500, with the fix as the last beat.
4. **P2:** the path appeared three times. The head subline now says "Lines 135–136. Stopped before it was written."
5. The h1 was the same size as the fix heading. It is now 40 px.
6. The mobile path overflowed. It now wraps with `overflow-wrap: anywhere`.
7. The Copy confirmation now has `aria-live`.

Not changed, with reasons:
- **Gold on `DagRun.state` rather than the `"state"` keys.** Gold means quote-to-code only, and `DagRun.state` is what the quote names.
- **No keyboard shortcut for copy.** The page is a viewer.
- **`impeccable detect <url>` times out.** The page holds an open EventSource (by design); the scan ran over CDP instead.

## Contrast (measured in the browser at 1280×720 after the arrival)
61 text nodes and both thread strokes; all pass AA. The lowest pairs:

| Pair | Ratio | Needs |
|---|---|---|
| Thread #7A5E00 on paper #F6F6F4 | 5.66 | 3.0 |
| "Blocked" #0A0A0B on red #FF5A47 (28 px/600) | 6.41 | 3.0 |
| Muted #9A9EA6 on panel #131418 (line numbers, context code) | 6.85 | 4.5 |
| Muted #9A9EA6 on ground #0B0C0E (bar, subline, labels) | 7.28 | 4.5 |
| Ink-muted #4D4F55 on paper (attribution) | 7.57 | 4.5 |
| Gold #D8C08A on panel (marked code, thread) | 10.37 | 3.0 / 4.5 |

0 console errors, 0 non-loopback requests, and no overflow at 720p or 1080p.

## Gaps (honest)
- **"212 ms"** is the hook round trip `demo_block.sh` prints (176–212 ms across runs). No receipt records it. The page shows the receipt's guard `latency_ms`, labelled "to decide, no AI model in the check".
- **"aliasing was offered, not taken"** is in no field. The note shows the root's `rejected_alternative` verbatim after "Offered, not taken:".
- **"Lines 137–138 already use the right names"** is derived from the edit snapshot: lines within 8 of the match that quote a snake_case name the decision uses and the match lacks. Without a snapshot it is a gap.
- **The tool name** (`edit_file`) is not on the receipt, so the page doesn't claim it.
- **The draft file named in the brief** was missing; `final.html` stood in.
- **`ufmt check .`** reports 76 files: 72 committed `data/variants` fixtures this branch doesn't touch, and 4 in the untracked `.agents/`. `ufmt check knack tests` is clean.
- **Captures:** `mockups/shots/kn80/verdict-1080p.png`, `verdict-720p.png` and `arrival-720p-5s.webm` (VP9, from a real `demo_block.sh` run with the console open). The live run receipts in `bench/` are from the 720p capture run.
- `bench/edits/` gains one snapshot per demo run, because the sandbox path is part of the snapshot. I pruned it by hand to the one the kept receipts cite. The script never deletes in `bench/edits/`, because the same copy step would be unsafe if pointed at a real knack home.

## Follow-up: verify row, headline, full comment
- **Headline:** now "This edit brings back what #75025 removed."
- **Footer:** replaced by a "Verify it" row at body size. It holds:
  - "Receipt" with the first 8 characters of the hash and a Copy button that copies the full hash;
  - `knack receipts verify --path <the receipts file the console reads>` with a Copy button;
  - "Rule airflow-75025 · decision confirmed".

  "root" and "not seeded" are no longer on screen. A seeded root still says ", seeded", so the honest seeded flag never disappears when it is true.
- **Full comment:** `data/roots/airflow/75025.json` `quote` is now Pushkal Gupta's whole paragraph, cut verbatim from the PR body in `mockups/refs/github-75025.json`. Before, it held only the first sentence. The note renders every sentence and grows; nothing clips it, and a test guards that.
  - At 720p the three-sentence note pushes lines 137–140 and the Verify row below the fold; the page is 866 px tall and scrolls. At 1080p lines 137–138 sit at the bottom edge. See `verdict-720p-fullpage.png`.
- **Receipts:** receipts made before this change hash the old one-sentence quote, so their `quote_verified` reads false. That includes `tests/fixtures/console_75025`, which is kept as a historical receipt. `bench/demo_block.receipts.jsonl` was re-run after the change.

## KN-90: structure (no behaviour or visual change)
- `app.py` holds routes only and includes `pages/verdict.py`, the block page's router. `render.py` fills `templates/base.html` (bar, fonts, tokens, verify row) around each page's template and the `partials/`.
- `facts.py` is pure: the verdict, its root, its proof and an edit snapshot in, `VerdictPage` out. The router reads the snapshot.
- `static/tokens.css` holds every colour, face, size and spacing value; `console.css` reads only tokens. `live.js` is the `/events` listener, `motion.js` the arrival beats, and `console.js` the thread and Copy. `console.js` measures the thread before `motion.js` moves anything, so it still lands on the underline.
- Four spacing values are off the 8-point scale and kept as named tokens so no pixel moves: `--space-separator` (6 px), `--space-paper` (20 px), `--space-figure-column` (20 px) and `--space-quiet` (128 px). The seal's 6 px padding and the bar's 18 px top are now on the scale, with line height carrying the difference.
- Guarded by `tests/console/test_screenshot.py`: the full 75025 page at 1920×1080 and 1280×720 under reduced motion, against baselines shot before the refactor, with at most 0.1% of pixels changed. `KNACK_SAVE_BASELINE=1` re-shoots them.

## KN-91: the argue and held pages
`GET /verdict/<hash>/argue` and `GET /verdict/<hash>/held`, each its own router (`pages/argue.py`, `pages/held.py`) over `base.html` and the partials. The facts are pure, in `facts.py`: `argue_page` and `held_page`. An unknown hash is the 404 page; a receipt with no ruling of the page's kind is the same page, reading "No ruling on that receipt."

Live, from the frozen one-story run:
```
KNACK_CONSOLE_RECEIPTS=$PWD/mockups/fixtures/one_story/receipts.jsonl KNACK_REGISTRY=$PWD/data/registry/airflow.json knack console
open http://127.0.0.1:7655/verdict/0e7ab608386631d65da47ec1bd194f45a335f49a0a8750635fc608f6559e65a9/argue
```

### Where each value comes from
| Shown | Source |
|---|---|
| The blocked lines (135–136, gold) | the deny receipt's `matched` and its edit snapshot, as on the block page |
| The note: the full quote and Pushkal Gupta · merged by bbovenzi · Oct 19 2026 · #75025 | the cited root, as on the block page, without "Offered, not taken" (the quote says it in his words) |
| "The agent, muse-spark-1.3-contributor, objected" and the objection | the ruling's `agent` and `objection`; a missing agent reads "Agent not recorded" |
| Argue: "muse-spark-1.3 ruled hold, citing #75025" and the cited slip | the latest `hold` ruling's `model`, `decision` and `cited_quotes`. Its `reply` equals the cited quote word for word, so it is read once, on the slip. |
| Argue: Hold, then "Lines 135–136 stay blocked." | the ruling's decision and the matched lines |
| "Answered by" | exactly the ruling's `models[]`, with each `host`, in the order asked: Spark alone on the hold, Spark then Spark Open on the escalate |
| "The block itself ran no model: 17.3 ms to decide." | the deny receipt's `latency_ms` |
| Argue: the fix card | the block page's fix, without the argue command |
| Held: the escalation | the latest `escalate` ruling |
| Held: Spark Open's answer | its verbatim `reply` in the latest argue self-check that names the receipt. The registry's `self_checks.jsonl`; kept receipts keep it at `traces/self_checks.jsonl`, as `one_story.py` froze it. A missing check reads "<model>'s answer not recorded". |
| Held: "A person upheld the decision." and "Upheld by Vedant Srivastava", the reason, the time, receipt ff61cef7 | the uphold receipt's `resolution` and time (`ResolutionView`) |
| Held, unresolved: the command and Copy allow / retire / uphold | `RESOLVE_HINT`, shown only here (`knack argue` points the agent at this page, never prints it); each button copies one runnable line |

Kept receipts now bring their rulings: with `KNACK_CONSOLE_RECEIPTS` set, the console reads `rulings.jsonl` beside it, as it already read `edits/`. The block page's "argue it" becomes a link to the argue page once a ruling exists, so an unargued deny's page is unchanged; the screenshot baselines still pass.

### Motion (`static/turns.js`)
One card rises per beat (0.75 rem, opacity, `cubic-bezier(0.23,1,0.32,1)`, 420 ms, as the block page's note), then the page is still: the objection at 160 ms, the ruling at 760, the answer (argue's outcome, held's Spark Open card) at 1360, and the person's card (argue's fix, held's resolution or decision card) at 1960. The blocked lines and the note do not move, because the reader has just seen them on the block page. Under reduced motion nothing moves and the final frame shows; without the script every card is simply there. At 2500 ms `getAnimations()` is empty, so nothing loops.

### Impeccable critique (dual-agent: A design review, B detector)
- **B:** live-URL detect: 0 findings on both pages. The overlay reported "No anti-patterns found." The static scan raised one `cramped-padding` on the code board. That is a false positive: the line-number column is the inset. All text passes AA; the lowest pair is `--muted` on `--raised`, 6.21:1. No colour off the palette, 0 console errors, 0 non-loopback requests.
- **Fixed after A and B:**
  1. **P1:** held's h1 said "Held for a person." on a case already upheld. It now says what the person did ("A person upheld the decision."), and argue's link adds ", who upheld it".
  2. **P1:** argue had no action. It now ends on the fix card.
  3. **P1:** the unresolved card had three 4-line wells repeating the hash. It is now one well, the command as knack prints it, and three Copy buttons. `console.js` keeps each button's own label after "Copied".
  4. **P2:** "Back to the argument" linked to a different objection. It now reads "What the record answered" and sits on the h1's baseline.
  5. **P2:** the agent and the judge looked alike. It now reads "The agent, muse-spark-1.3-contributor, objected".
  6. The note and replies were indented on argue but not on held. Both are now full width.
  7. On phones, the Copy buttons are now 44 px and the verify row wraps (these pages only).
- **Not changed, with reasons:**
  - **The cited slip repeats two sentences of the note.** The brief asks for the cited quotes verbatim.
  - **"Answered by" stays on held.** The brief asks for every model with its host, and the rail has the room.
  - **The block page's verify-row overflow at 390** is the block page's look, which this ticket doesn't change.
- **Fit:** argue is 746 px at 720p, of which the verify row wraps 26 px because the fixture's receipts path is long. Held is 802 px at 720p (resolved) and 858 px (unresolved). Both scroll, as the block page does (898 px).
- **Shots:** `mockups/shots/kn91/`: argue and held at 1080p and 720p, both at 390 full page, and the unresolved held state at 1080p and 720p (served from a copy of the run without the uphold receipt).

## KN-95: live rulings
`GET /events` now sends three kinds of event, each once, in order:
- `deny`, whose data is the receipt hash, as before.
- `ruling`, with data `{"block", "decision"}` for each new line in `rulings.jsonl`.
- `resolution`, with data `{"block", "action"}` for each new receipt carrying a `resolution`.

Within one poll the order is the order these can happen: denies, then rulings, then resolutions. A ruling has no hash, so its whole line is its key. A torn line is skipped until it is whole.

The argue and held pages listen on `data-block`, and only for their own block. The block page still switches to any new deny. On news, `live.js` fetches the page's own URL, so the server stays the only renderer. It then swaps each `[data-live]` region (head, exchange, rail) whose served HTML differs.

### Motion
One move, then still. Only the newly arrived `[data-arrives]` node rises: the "later objection was held for a person" line on argue, or the paper "Upheld by …" card on held. It rises 0.75 rem with opacity, `cubic-bezier(0.23,1,0.32,1)`, 420 ms, the same rise as every arrival. Everything else that changed, such as held's h1, swaps silently. Under reduced motion nothing moves.

`tests/console/test_live_rulings.py` drives a real browser to check three things: the page is not reloaded, exactly one animation runs at the change, and none are left after it. Copy is now one delegated listener, so a swapped-in button still copies.

# KN-93: the day page (GET /)
When the console knows its clone (`knack console`), `/` is the repo's memory; without a clone it still waits. It listens on `/events` like before, so a new deny switches it to `/verdict/<hash>`. `GET /graph` serves the per-day counts the squares show. Facts come from `facts.day_page` and `facts.graph` (pure); reading the registry, roots and chain is in `pages/day.py`.

## Data truth
- **Headline:** every root in the registry; "confirmed to block" are the Confirmed ones, "advise only" the rest (they never block).
- **Squares:** 53 Sunday-first weeks ending today, in the clock's zone. A root lands on the day its PR merged (`merged_at`); a root without one has no square and is counted as "N merge dates not recorded".
- **Red dot:** a guard deny that day from the full chain. An uphold records a deny but is a resolution, not a block.
- **Paper dot:** a `knack resolve` receipt that day; its kind (allowed, retired, upheld) is in the cell's line and in Today. Nothing on the page says "learn".
- **Today:** commits and PRs from the day feed (`/day`); today's blocks and resolutions from the chain, labelled by kind; every time shown in the clock's zone, named once in the heading.

## What changed from the mockup (`mockups/day/`), and why
| Mockup | Shipped | Why |
|---|---|---|
| Confirmed decisions as dark rows | Short paper notes, in Plex Sans | The brief asks for paper notes: a person decided and a person confirmed. The text is Knack's restatement, not verbatim words, so it is Sans; Serif stays for verbatim words only. |
| Shade 1, 2, 3+ by count | One meaning per step: advise only, one confirmed, confirmed among more | The critique (P1) found Oct 19 (1 confirmed) and Oct 27 (2 advise-only) shaded the same; now a confirmed day always reads a step above any other. The count is in each cell's line. |
| "Earlier blocks not recorded" | Blocks and resolutions from the whole chain | The brief asks for the full verdict history. |
| Cells built by script | Cells rendered by the server; script only fades, shows the line and moves focus | Without script the record is still there. |

## Motion
Each week's column fades in (opacity only), week n at n × 7 ms for 220 ms, ease-out `cubic-bezier(0.23,1,0.32,1)`: the last ends at 584 ms, measured. Once, on load; reduced motion shows the final frame. The tooltip never animates (it follows keyboard focus). On a phone the record opens scrolled to today.

## Impeccable critique (dual-agent)
- **A, design review:** 23/32 (two heuristics n/a, read-only page). Fixed: P1 shade ambiguity; P1 phone graph opened on the empty past; P2 the bar read "Blocked" on the quiet page (now "Last receipt: blocked"); P2 counts repeated the headline (now "In 53 weeks: 1 block, 0 resolved by a person."); ArrowUp/Down no longer wrap across weeks; "Nov" no longer pokes past the frame; narrower time column.
- **Not changed:** P3 asked for Serif or no paper on the decisions (see the table). Copy buttons are 32 px on a phone: shared with the block page, out of scope. The advise-only step (`--ink-muted`) is 2.4:1 against the ground, under 3:1; it is the quietest real grey in the palette, and advise-only decisions are the quiet ones. Each cell's line carries the fact.
- **B, detector:** URL scans time out on the open EventSource (as on KN-80); over CDP, 0 findings at 1280×720, 1920×1080 and 390×844; templates 0. Exactly one screen at 720p and 1080p, 0 overflow, 0 contrast failures, 0 console errors, 0 non-loopback requests.
- **Hallmark lint:** the stamp FAIL is left by rule. Focus, overflow and `:active` FAILs are the served HTML read without `console.css`. The middle-dot FAIL on the counts line is fixed; the attribution line keeps " · " like the block page's note.

## Captures
`mockups/shots/kn93/`: `day-1080p.png`, `day-720p.png`, `-hover` of each (Oct 19), and `day-720p-fade-150ms.png` (mid-fade). Served from a clone with origin apache/airflow, `bench/demo_block.receipts.jsonl` and `data/registry/airflow.json`; no GitHub token, so PRs read as not recorded.
`day-1080p.png` and `day-720p.png` were shot again on fix/day-said-leak, after the note fix, from the test world in `test_day_page.py` (the 75025 fixture receipts, clock frozen Nov 2 12:00 UTC). The hover and fade shots are still the originals.

## KN-94: the recovery page (`/recovery/airflow-75025`)

`pages/recovery.py` reads the kept self-repair run (`mockups/fixtures/self_repair/`, KN-97) per request; `repair_facts.recovery_page` turns it into the page's facts and reads no file. The console finds the run beside its kept receipts: `KNACK_CONSOLE_RECEIPTS=…/fixtures/one_story/receipts.jsonl` serves `…/fixtures/self_repair`. Without kept receipts, or for any other rule, the route is 404.

### Where each value comes from
- Step 1 and 6: the rule's receipts, told apart by the edit snapshot each names (`traces/receipt_edits/`): the must-fail case, the must-pass case, `edits/corrected.after.py`. The evasion's line number comes from the later deny's match (line 89).
- Step 2: the must-pass case's line 6, from the deny's own match. The name `compliant_3.py` is the file the driver replayed (`driver/*/steps.py`).
- Step 3: kept, dropped and added are v1's and v2's `rule.any` checks compared as parsed YAML; each is said by the node it matches, a pattern as written. Attempts and the compile calls are from the false-block log and `models.jsonl`.
- Step 4: every `PASS` line of the false-block log, verbatim, without the local cache path in parentheses on the fresh cross-model line.
- Step 5: each `knack confirm` log, its pin line, exit code and the gate's indented reason; the person is `corrections.jsonl`'s confirm.
- Step 6: chain count and state from `verify_chain` on the kept receipts.
- Rail: v1 and v2 are the roots' `rule_sha` before and after; who did the work is `models.jsonl` grouped by model and by what each prompt asked, with every trace id.

### Departures, and why
- Trace ids sit under "Who did the work", not in step 3: with them in step 3 the timeline ran 68 px past 720p. Step 3 names each model, its host and its call count.
- `compliant_3.py` is on paper, as the brief asks, though DESIGN.md keeps paper for the human: it is the correct code, the same role as the fix.
- Red appears once, on "Blocked" in step 6: the evasion was denied live by the hook.
- The verify command ends in an ellipsis in the rail at 720p and 1080p; its full text is in its title and the Copy button copies it. Wrapping it ran the rail 44 px past 720p.

### Motion (`static/recovery.js`)
The track fills top to bottom once: `scaleY` 0→1, 1680 ms after a 240 ms wait, `cubic-bezier(0.77, 0, 0.175, 1)` (on-screen movement, so a strong ease-in-out; about 280 ms a step, done well inside a 5 s look). `fill: backwards` holds the empty track through the wait; after, the CSS frame is the final one. Without script, or under `prefers-reduced-motion`, the track is drawn full.

### Impeccable critique (dual-agent: A design review, B detector)
- A: the peak was buried (14 px "Blocked" mid-line) and the end was a hash run-on. Fixed: step 6's title and "Blocked" are one step up (20 px, same 24 px leading); the end says "The correct file and the corrected edit both pass." before its receipts. Also fixed: Copy before the command so it is never clipped, muted trace ids, receipts that never break mid-way, the proof line's full text in its title, backticked spans in the gate's reason as code. Not taken: a two-column gate grid (the held-out lines wrap at half width and add rows).
- B: 88 text nodes at each size, 0 below AA (lowest 6.34:1, "Blocked" on the ground); smallest text 12.25 px at 720p; no overflow, no console errors, no outside requests. Detector: `cramped-padding` on the code line (a false positive: the number gutter is the padding) and `line-length` on step 5's first attempt (left: it is the gate's verbatim message).

### Gaps (honest)
- The run is one frozen run; the page names no other repair.
- The day page's decision notes rendered `.said` as console.css's argue card (dark on paper). Fixed on fix/day-said-leak: the note's text is `.words`, ink on paper.

### Captures
`mockups/shots/kn94/`: 720p, 1080p, 720p reduced motion, 390 full page, four fill beats at 720p, and the day page with its "rule repaired" link.
