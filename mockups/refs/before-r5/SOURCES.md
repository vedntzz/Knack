# Where every visible value comes from (round 4, block)

`fixtures/freeze_block.py` copies each field from its source into `fixtures/block.json` and `fixtures/block.js`. No value is typed by hand. To refreeze, run `.venv/bin/python mockups/fixtures/freeze_block.py`. The freeze stops if the log and the root disagree, or if the two quoted sentences are not consecutive in the PR body.

On load, `final.html` checks itself: every value it shows goes through `bound()`, which logs `truth: not in fixture` if the text is not in `block.js`. The last capture checked 79 bindings, with 0 missing, 0 console errors and 0 non-loopback requests.

The round 3 file (five scenes) and its notes are kept unchanged in `refs/before-r3/`.

| Shown | Field | Source |
|---|---|---|
| Quote, both sentences | `quote.sentences` | `bench/demo_block.log` at `b8c3032` (`git show b8c3032:bench/demo_block.log`): the `Quote:` and `Why:` lines. Both equal `data/roots/airflow/75025.json` `quote` and `why`, and they appear consecutively in the PR body (`refs/github-75025.json`) |
| Underlined phrase "aliasing them onto `DagRun.state` and `DagRun.start_date`" | `quote.rejected_phrase` | Cut from the first sentence. It is the root's `rejected_alternative` in the author's own words |
| Pushkal Gupta | `person.name` | Root `decided_by`, the text before "(author)" |
| @Pushkal-Gupta, avatar, Oct 18, 2026 | `person.handle`, `person.avatar`, `person.wrote_at` | `refs/github-75025.json` (GitHub API, fetched 2026-11-01): `user.login` and `created_at` 2026-10-18T23:19:34Z. Avatar saved as `refs/pushkal-gupta-avatar.png` from `avatars.githubusercontent.com/u/161060351` |
| "Pushkal Gupta (author); approved and merged by bbovenzi" | `root.decided_by` | Root, verbatim. bbovenzi's APPROVED review (2026-10-19T21:35:32Z) is in `refs/github-75025.json` |
| merged Oct 19, 2026 | `root.merged_at` | Root, 2026-10-19T21:36:02Z, shown as a UTC date |
| apache/airflow #75025 link | `root.source_url` | Root |
| Agent's diff, old/new line numbers 131–139 | `attempted.rows` | The first hunk of `tests/guard/fixtures/replay/run_neutral_3.diff`, numbered on both sides. This is the edit `scripts/demo_block.sh` replays through the hook |
| "1 line removed, 6 added" | computed from `attempted.rows` | Counted from the rows shown. The log's "-7 +12 lines" is the hunk's span, not a count, so it is not shown |
| Matched rows 135, 136 and the marked tokens | `attempted.matched` | The log's `Matched:` line |
| "#75025 took "state" and "start_date" out of both sort lists", with rows `public/dags.py:132` and `ui/dags.py:139` | `rejected` | `scripts/fixtures/75025/base` vs `head` for `routes/public/dags.py` and `routes/ui/dags.py`, at those line numbers |
| apache/airflow | `where.repo` | The log's `Source:` URL |
| main | `where.branch` | `scripts/demo_block.sh`, `git init -q -b main` (the clone the hook ran in) |
| public/dags.py, lines 135–136 | `where.file`, `where.lines` | The log's `edit_file` line and `Matched:` lines |
| PreToolUse hook on edit_file | `where.hook`, `where.tool` | The log's deny payload, `hookEventName` |
| Rule airflow-75025 | `where.rule` | `data/rules/airflow/75025.yml`, `id:` |
| Root airflow-75025-1, Confirmed, not seeded | `root.id`, `root.status`, `root.seeded` | Root |
| Log written 2026-11-01 13:09:04 −05:00 | `where.log_committed` | `git log -1 --format=%cI b8c3032`. This is the commit time of the log, not the moment of the block (see the gaps in NOTES.md) |
| Decision on record | `root.decision` | Root |
| "To comply, drop lines 135–136; lines 137–138 already sort by last_run_*." | computed | Line numbers from `where.lines` and the added rows that contain `last_run_`. The wording is UI copy |
| 8 of 8 gates pass, by name | `proof.grid` | `bench/PROOF-GRID.md`: the header row and the `airflow-75025-1` row |
| "0 FP on Airflow current tree and previous release, for the rules shown" | `proof.fp` | `data/registry/airflow.json`: `false_positives` 0, plus `old_release.false_positives` 0. The previous release is 3.3.2, shown only in the tooltip, to keep the fixed string verbatim |
| 212 ms round trip (18.7 ms verdict) · ast-grep | `proof.round_trip_ms`, `proof.verdict_ms`, `proof.scan` | The log's `== latency ==` lines |
| 0 model calls in this hook | `proof.no_model` | The log's first line: "No model, no network." |
| Receipt 80b311c17a39 | `proof.receipt` | The log's `Console: …/verdict/<hash>` line. The full hash is in the tooltip |
| `knack argue "<your reason>"` under Argue | `where.dispute` | The log's `To dispute:` line |

## References

| File | What | Source |
|---|---|---|
| `refs/github-75025-quote.png` | GitHub PR, scrolled to the quote paragraph, 1920×1080 | https://github.com/apache/airflow/pull/75025 |
| `refs/github-75025-header.png` | The same PR description's header: avatar, handle, timestamp | same |
| `refs/github-75025-files.png` | Files changed | https://github.com/apache/airflow/pull/75025/files |
| `refs/sentry-docs-issue.png` | Sentry issue details (annotated product screenshot) | https://docs.sentry.io/product/issues/issue-details/ |
| `refs/linear-docs-comment.png` | Linear comment on an issue | https://linear.app/docs/comment-on-issues |
| `refs/github-75025.json` | API snapshot: author, created_at, body, reviews | api.github.com, 2026-11-01 |
| `refs/pushkal-gupta-avatar.png` | GitHub avatar, 160 px | avatars.githubusercontent.com |

## Fonts

`fixtures/fonts/`: IBM Plex Sans 400/500/600/700 and JetBrains Mono 400/600 (latin woff2 from the @fontsource packages on jsDelivr), both under the SIL Open Font License; the licence texts sit beside them.
