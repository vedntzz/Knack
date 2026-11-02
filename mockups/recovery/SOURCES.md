# Recovery: where every visible value comes from

`M` is `window.KNACK.miss` and `K` is `window.KNACK`, both from `mockups/fixtures/scenes.js`. `block.js` is not loaded. Nothing else is read. I audited this file against `shots/recovery/recovery-720p.png`, `-1080p.png` and `-390-fullpage.png` on the final build.

`bar2_log` is `M.bar2_log`: the run that installed the rule.

| On the page | Fixture path | Note |
|---|---|---|
| fastapi/fastapi | `M.root.source_url`, the owner/repo part | |
| Branch not recorded | none | Gap |
| dependencies/models.py | `M.edit_file`, last two segments | |
| Receipt not recorded (bar and verify row) | none | Gap: the miss loop's fixture holds no receipt |
| Oct 31 2026, 17:15:04 UTC | `bar2_log`, the timestamp in `candidate-20261031T171504Z-43479c.yml` | The time the candidate rule was written, the only time recorded for this run |
| Line 18, `_CALLABLE_CACHE_SIZE = 8192` | `M.edit_after`, line 18 (the first line containing `_CALLABLE_CACHE_SIZE`) | |
| "Rebuilt, not the agent's bytes: the run's diff.patch was deleted with its temp work folder." | `M.edit_note`, first sentence | Verbatim |
| Recompiled by Muse Spark, `muse-spark-1.3` | `bar2_log`: "recompiling with muse-spark-1.3"; the name comes from `K.spark.model` matching it | |
| at api.meta.ai | `K.spark.host` | |
| case 77322b4d226e | `bar2_log`: "guard edit … [77322b4d226e]" | |
| "Two earlier runs kept the old rule: held-out same, then held-out cross failed." | `M.run1_log` "FAIL held-out same", `M.run2_log` "FAIL held-out cross", and both logs' "kept the old fastapi-16062" | The sentence is UI copy over those values |
| Proven by four gates: proof, held-out same, held-out cross, fresh cross-model, each "passed" with its result | `bar2_log`, every `PASS <gate>: <result>` line except `cases` | Verbatim. The fresh cross-model line's local cache path in parentheses is dropped |
| "cases passed: every must-fail edit denied, every must-pass edit allowed." | `bar2_log`, the `PASS cases:` line | Verbatim |
| Installed after 2 attempts | `bar2_log`: "installed fastapi-16062 -> … (2 attempt(s))" | |
| Tier warn | `M.tier` | |
| Decision Inferred | `M.root.status` | |
| "A corrected edit passing: not recorded" | none | Gap; the brief's fifth step |
| "I'll wait to see if anyone requests an even larger bump, for now this should work." | `M.root.quote` | Verbatim and complete |
| Gold underline on "an even larger bump" | `M.root.rejected_alternative`, found inside the quote | |
| tiangolo | `M.root.decided_by` | |
| merged Jul 27 2026 | `M.root.merged_at` | |
| #16062 and its link | `M.root.source_url` | |
| Inferred | `M.root.status`, `M.root.seeded` = false | |
| The rule before: "Found no new match in this edit, which sets 8192 through a module-level constant." | `bar2_log` "adds no new match"; `M.edit_note` "This edit sets 8192 through a module-level constant." | Plain sentence over the two |
| The rule after: "Denies this edit, its one must-fail case, and allows every must-pass edit and 3/3 compliant edits in each held-out set." | `bar2_log` cases line; `M.cases` (one file); each held-out and fresh line's "3/3 compliant allowed" | Plain sentence over those values |
| Who did the work: Muse Spark `muse-spark-1.3` at api.meta.ai, recompiled the rule | as above | |
| The fresh cross-model gate's model not recorded | `bar2_log` names the gate, not a model | Gap |
| `cat data/rules/fastapi/16062.yml` and its Copy | `bar2_log`: "installed fastapi-16062 -> data/registry/../rules/fastapi/16062.yml", with `data/registry/..` normalised | Run from the repo root on 2026-11-01, it prints the rule |
| Rule fastapi-16062 | the same install line | |
| decision inferred, not seeded · tier warn | `M.root.status`, `M.root.seeded`, `M.tier` | |

Fixed copy (the brief's or the page's words, not data): "One edit slipped past a rule. The rule learned.", "Slipped: the rule found no new match", "Recompiled by", "Proven by four gates", "Denied when replayed", "A proof run, not a live retry. Live, the tier is … and the decision …", "The rule before", "The rule after", "Who did the work", "Verify it".
