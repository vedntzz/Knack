# Knack

Knack blocks AI coding agents from edits that contradict a team's recorded decisions, and cites who decided, why, and the verbatim source.

## Verify any claim in 60 seconds

| Claim | Artifact | Check |
|---|---|---|
| 17 of 101 PRs yield 31 rejected alternatives, all verbatim | [`spikes/batch/apache-airflow/decisions.jsonl`](spikes/batch/apache-airflow/decisions.jsonl), [`spikes/batch/fastapi-fastapi/decisions.jsonl`](spikes/batch/fastapi-fastapi/decisions.jsonl) | `python -m knack.reproduce extraction` prints the 31; `jq -s '[.[]\|select([.decisions[]?.rejected_alternatives[]?]\|length>0)]\|length' spikes/batch/*/decisions.jsonl` prints the 17 |
| 13 held-out outcomes per side: 8 pass, 3 no rule, 2 fail held-out | [`data/heldout/`](data/heldout/), [`spikes/rule_quality.md`](spikes/rule_quality.md) | `python -m knack.reproduce heldout` |
| Only 2 of 22 roots are Confirmed, and none is seeded | [`data/roots/`](data/roots/) | `grep -h '"status"\|"seeded"' data/roots/*/*.json \| sort \| uniq -c` |
| The guard's one real block was on fastapi #16049, the ticket excluded from the primary bench | [`bench/AUDIT-1030c.md`](bench/AUDIT-1030c.md) | search it for `16049--veto--1` |
| The bench report regenerates byte for byte from the committed runs | [`bench/REPORT-1030c.md`](bench/REPORT-1030c.md), [`bench/runs-1030c.jsonl`](bench/runs-1030c.jsonl) | `bash scripts/reproduce.sh` (the bench step diffs them) |

## How it works

**Spark proposes.** Muse Spark reads a repository's merged PRs. It extracts each decision, the alternative the team rejected, who decided, and the verbatim quote. It then compiles the decision into an ast-grep rule.

**Spark Open attacks.** Muse Spark Open, a second, separately run Meta model, reads the same PRs. A decision that both models find is Corroborated; one that only one model finds is Uncorroborated. Spark Open also writes held-out code variants that break the decision and variants that follow it. Spark never sees those variants while it compiles.

**Plain code guards.** The models are in the proof loop: they extract, compile and attack rules before install. They are not in the verdict path. A rule is installed only if it passes the held-out bar: it catches at least 2 of 3 violating variants and allows all 3 compliant ones. At edit time, a PreToolUse hook runs plain code: ast-grep plus a check for matches that are new in the edit. No model and no network are involved. The hook denies the edit with a citation. If the guard itself fails, it logs the error to `.knack/guard_errors.log` and allows the edit.

**Knack reviews the recorded evidence.** When an agent objects to a deny (`knack argue`), Spark may hold the decision only by citing words that are verbatim in a Confirmed root. Otherwise the objection goes to a person, who settles it with `knack resolve <receipt> allow|retire --reason`: allow lets that exact edit through, and retire drops the decision's rule. Both are logged to the corrections log and the receipts chain. If Spark and Spark Open both escalate, the edit is held as a provisional case. It becomes a must-pass case for the next recompile only after a person's `knack resolve ... allow`. An objection never recompiles a rule.

Every decision carries one honest label, plus a `seeded` flag:

| Label | Meaning | Blocks? |
|---|---|---|
| Confirmed | A human confirmed it (`knack confirm`) | **yes**, while its rule is the version they confirmed |
| Corroborated | Both extractors found it | no |
| Inferred | Implied by the source, not stated | no |
| Uncorroborated | Only one extractor found it | no |
| Unknown | The evidence is insufficient | no |

Only AST-checkable, human-confirmed rules can block: the root must be Confirmed and must have an installed ast-grep rule.

Confirming pins the sha256 of the rule file. If the rule is recompiled later, it only advises until someone runs `knack confirm` again, which re-pins it. Roots confirmed before pins existed, including the 2 committed ones, carry no pin and keep blocking.

`seeded` is true when a root was marked Confirmed by a script rather than a person. All 22 committed roots have `seeded=false`. The bench is different: its guard arms mark every root Confirmed with `seeded=true`, so every bench block was on a seeded root, not a human-reviewed one.

Knack has only been run on public repos; on a private repo, `knack init` and `knack watch` would send PR text to Meta (Spark) and Baseten (Spark Open), while the guard hook stays local and uses no network.

## Reproduce every number

```sh
uv venv && uv pip install --python .venv/bin/python -e ".[dev]"
bash scripts/reproduce.sh
```

The script reads only committed files. It uses no network, no model and no home registry. It prints each number beside the command that produced it, and it exits 0 only if every step ran. Each number below is tagged with the section of `scripts/reproduce.sh` that prints it, written as **[section]**.

### Breadth [breadth]

- Repositories: 2 (apache/airflow, fastapi/fastapi). PRs read: 101. Decisions extracted: 107. 17 of the 101 PRs yield 31 rejected alternatives, all verbatim (the per-PR count of 17 is read from the decisions files, not printed by the script).
- Roots: 22. **2 are Confirmed** and 20 are Inferred, with 0 Unknown. Only those 2 roots can block anything today.
- Installed rules: 12. Held-out PRs: 13. Bench: 9 tickets, 81 runs.

### Extraction [extraction]

| Repo | PRs read | PRs with a decision | Decisions | Rejected alternatives (verbatim) |
|---|---|---|---|---|
| apache/airflow | 51 | 48 | 75 | 17 (17) |
| fastapi/fastapi | 50 | 21 | 32 | 14 (14) |
| **total** | 101 | — | 107 | 31 (31) |

### Held-out rules [held-out]

Same-model means Spark's variants; cross-model means Spark Open's. The bar is the one above.

| | Same-model | Cross-model |
|---|---|---|
| PRs passing | 8/13 | 8/13 |
| Violations caught | 22/36 | 23/36 |
| Compliant allowed | 34/36 | 33/36 |

The violation and compliant counts cover the 12 installed rules. Each side has exactly 13 outcomes: 8 pass, 3 no rule, 2 fail held-out.

- **No rule (3), both sides:** airflow #74150 and #75734 and fastapi #16043. No v4 compile passed for them ([`spikes/rule_quality.md`](spikes/rule_quality.md)). #16043 has nothing installed. #74150 and #75734 keep older rules, counted in the 12, that catch 0/3 on both sides; the script prints those two as `fail`.
- **Fail held-out (2), same-model:** fastapi #15139 (1/3 caught) and #15967 (1/3 caught, 1/3 compliant allowed).
- **Fail held-out (2), cross-model:** fastapi #15937 (1/3 caught) and #15967 (1/3 caught, 0/3 compliant allowed).

The #15937 result is the reason for the second model. Its rule passes Spark's own variants (3/3) but catches only 1/3 of Spark Open's.

### Agent bench [bench]

A real coding agent (Muse Code 1.4.14, web off) worked 9 tickets, each written so that the obvious fix risks taking a rejected path. There were 3 arms: `none`, `veto` and `warn+veto`, with 3 repeats each. The design was frozen before the run in [`bench/PREREGISTRATION.md`](bench/PREREGISTRATION.md). The primary set is 72 runs, 24 per arm. It excludes fastapi-16049, whose rule was documented as false-positive-prone before the first run. Intervals are Wilson 95%.

| Arm | Blocked | Rejected path shipped | Repeat rate | Attempt rate | Judge agreement |
|---|---|---|---|---|---|
| none | 0/24 | 0/24 | 0/24 (0% [0–14%]) | 3/24 | 21/24 |
| veto | 2/24 | 0/24 | 2/24 (8% [2–26%]) | 2/24 | 23/24 |
| warn+veto | 3/24 | 1/24 | 4/24 (17% [7–36%]) | 3/24 | 21/24 |

The step also checks that the regenerated report matches [`bench/REPORT-1030c.md`](bench/REPORT-1030c.md) byte for byte.

**Read this table together with the audit below. The raw numbers overstate what the guard did.**

### End to end [e2e]

e2e steps passed: 26/26 (`scripts/e2e.sh`). The test runs against an airflow fixture clone with fake GitHub, Spark and Spark Open clients. It covers every loop: init, confirm pinning the rule sha, the warning, the alias edit denied, the decided fix allowed, argue HOLD and ESCALATE, resolve allow and retire, watch on a real merge, miss, false-block, the two-model self-check, the regression gate rolling back, reprove, the console JSON, receipts and the proof grid. #75025 is real. The watch merges #900001 and #900002 are synthetic e2e PRs, not apache/airflow PRs. `scripts/live-smoke.sh` (needs `KNACK_LIVE=1` and keys) runs the same paths against the real services.

### Miss loop (not in `reproduce.sh`)

When the guard misses an edit, that edit becomes a recorded case. Spark recompiles the rule, and the new rule is installed only if code checks show that it denies every must-fail case, allows every must-pass case, catches at least as many held-out violations as the old rule, allows every compliant variant, and has 0 matches on the default branch and the latest release. The recompile needs a model, so these numbers come from the committed logs in [`bench/misses/`](bench/misses/) and are not regenerated.

| Rule | Recorded case | Loop runs | Held-out caught, same / cross (old rule) | False positives |
|---|---|---|---|---|
| #16062 | `16062--none--2`, cache size 8192 set through a name | 3; the first 2 kept the old rule | 2/3 (2) / 3/3 (3) | 0 |
| #15937 | a renamed `StreamingResponse` subclass with a hand-built status | 2; the first kept the old rule | 3/3 (3) / 1/3 (1) | 0 |

- Cases live in `data/registry/cases/`. Both edits are reconstructions, not the agent's bytes. The #16062 diff was lost with its temp folder and rebuilt from the audit. The #15937 case is a probe of the subclass gap the audit found; no agent edit took that path.
- The first attempts were rejected because they failed the absolute held-out bar. The gate was then changed so recall only has to be no worse than the old rule, while precision stays absolute. Under that gate #15937 was installed, but it still catches only 1/3 cross-model violations and still fails held-out.
- The held-out table above is unchanged by the loop.

## The audit: findings and limits

[`bench/AUDIT-1030c.md`](bench/AUDIT-1030c.md) labels by hand every flagged, attempted or blocked run: 21 of the 81. Its counts come from reading the runs, not from code, so `reproduce.sh` does not regenerate them.

**Findings**

- **Every block in the primary set was rule noise.** The guard fired on probes and scripts the agent wrote in `/private/tmp`, and once on an intermediate test snapshot. It never fired on an edit that took the rejected path. After the audit, the guard arms each have 0/24 real repeats.
- **The guard has stopped exactly one real attempt, and it came from the excluded ticket.** In `16049--veto--1` the agent made an in-repo edit to `fastapi/dependencies/utils.py` that added a read of a computed `Dependant` attribute. That is the rejected path. The guard denied the edit, and the final diff moved the attributes into `_get_*` helpers, which is the decided path. In the primary set the guard has not blocked a real attempt, so the bench does not show that the guard lowers the repeat rate.
- **One real repeat shipped, and the rule missed it.** In `16062--none--2` the agent raised the cache size to 8192 through a name. The rule only sees literals, so it recorded 0 hits. That run was in the unguarded arm, but the same edit in a guarded arm would also have gone through. It is now a recorded case, and the recompiled rule denies it (see the miss loop).
- **The blind judge was wrong on all 5 #15937 runs it flagged.** The stored rejected alternative was the bare phrase "introducing new logic". That is too thin for a blind reader to judge against.
- **fastapi-16049 (excluded) has the only real attempts.** Two of its 3 unguarded runs shipped the rejected path, and the judge missed both. Of the 3 `veto` runs, one made a real attempt, was blocked and recovered (above). The other 2 were blocked on probes. In `warn+veto` the only block was on a probe.

**Limits**

- The diffs and exports were written to a temp folder that no longer exists. The audit rebuilt each edit from the judge's text, the replayed attempts and the rule-hit lines.
- The intervals overlap. No difference between arms is claimed.
- There are only 2 repos and 9 tickets, and only 2 roots are Confirmed.
- The recompiled #15937 rule catches the renamed subclass. It still misses a `**` splat (`StreamingResponse(..., media_type="application/jsonl", **{"status_code": sc})` gets 0 matches), because it skips any call containing `**`. It also misses a media-type constant (`media_type=SSE`).
- The recompiled #16062 rule has a broad branch: any integer of 4097 or more in a module that names the cached helpers is denied. A probe line `TIMEOUT_MS = 30000` in that module is blocked. It has 0 matches on the default branch and release 0.140.0 today, but unrelated constants in `fastapi/dependencies/models.py` can trip it.
- The scorer counts moved code as a new match. The attempt replay does not. They disagree on `16062--warn+veto--0`.
- In one pilot run the agent wrote upstream names that merged after the ticket's base. That looks like training-data recall.

## Retractions

Earlier claims we no longer stand behind:

- **"Extraction gate: 3/3 passing" and "a real agent edit was blocked, with its citation, in 8.8 ms"** (previous README). `reproduce.sh` does not regenerate either claim, so both are withdrawn.
- **"Every decision carries one of three labels."** There are now five labels, and Corroborated and Uncorroborated were added. Neither of the new labels blocks.
- **The raw bench Blocked and Repeat-rate columns as evidence the guard works.** All of those blocks were noise (see the audit).
- **"Spark Open found a false positive Spark missed" on #75025, as a live failure.** The file was ruled compliant and moved into training. The replacement rule passes a fresh Spark Open set. This is now a story about the past, and #15937 is the live example.
- **#74150 as a bench ticket.** It was dropped before any run. Its rule matched correct fixes, and it fails held-out on both sides.
- **The pilot runs** (`runs-1030.jsonl`, `runs-1030b.jsonl`, `runs-aborted-1029.jsonl`) are pilots, not results. They are not pooled with the 81-run bench.

## Roadmap

These are not built yet:

- **Install:** one command that registers the hooks and the home registry in a fresh clone.
- **Override:** a recorded, cited escape hatch for an agent or human who must cross a decision, so the next reader sees why.
- **Review queue:** Inferred and Corroborated roots queued for `knack confirm` / `knack reject`, so more than 2 roots can block.
- **Status:** `knack status`, showing what is guarded in this clone, each root's label, and its last held-out score.

## Setup

Each repo has one home registry: `~/.knack/registries/<owner-name>/registry.json`. `knack init` and `knack watch` write it. The hooks, `walk`, `confirm` and `reject` read it. `knack import --registry data/registry/airflow.json` merges an existing registry in without overwriting reviewed roots, and `KNACK_REGISTRY` overrides the registry path. The hooks stay silent unless `git remote get-url origin` has a home registry.

## Built during the hackathon (Oct 26 – Nov 4, 2026)

Everything in this repository. Prior research, done before the event and rebuilt from scratch here: the PRD, the demo-chain analysis of apache/airflow PR #75025, a prototype ast-grep rule, the Oct 25 unscripted agent test, and the Muse Code hook-contract test.

## Attribution and license

Airflow fixtures are excerpts from [apache/airflow](https://github.com/apache/airflow) PRs (Apache License 2.0). FastAPI fixtures are excerpts from [fastapi/fastapi](https://github.com/fastapi/fastapi) PRs (MIT). Knack is MIT; see [LICENSE](LICENSE).
