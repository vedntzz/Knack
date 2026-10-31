# Knack

Knack blocks AI coding agents from edits that contradict a team's recorded decisions, and cites who decided, why, and the verbatim source.

## How it works

**Spark proposes.** Muse Spark reads a repository's merged PRs. It extracts each decision, the alternative the team rejected, who decided, and the verbatim quote. It then compiles the decision into an ast-grep rule.

**Spark Open attacks.** A second model, Muse Spark Open, reads the same PRs independently. A decision that both models find is Corroborated; one that only one model finds is Uncorroborated. Spark Open also writes held-out code variants that break the decision and variants that follow it. Spark never sees those variants while it compiles.

**Code decides.** A rule is installed only if it passes the held-out bar: it catches at least 2 of 3 violating variants and allows all 3 compliant ones. At edit time, a PreToolUse hook runs plain code: ast-grep plus a check for matches that are new in the edit. No model and no network are involved. The hook denies the edit with a citation. If the guard itself fails, it logs the error to `.knack/guard_errors.log` and allows the edit.

Every decision carries one honest label, plus a `seeded` flag:

| Label | Meaning | Blocks? |
|---|---|---|
| Confirmed | A human confirmed it (`knack confirm`) | **yes** |
| Corroborated | Both extractors found it | no |
| Inferred | Implied by the source, not stated | no |
| Uncorroborated | Only one extractor found it | no |
| Unknown | The evidence is insufficient | no |

Only Confirmed decisions block.

## Reproduce every number

```sh
uv venv && uv pip install --python .venv/bin/python -e ".[dev]"
bash scripts/reproduce.sh
```

The script reads only committed files. It uses no network, no model and no home registry. It prints each number beside the command that produced it, and it exits 0 only if every step ran. Each number below is tagged with the section of `scripts/reproduce.sh` that prints it, written as **[section]**.

### Breadth [breadth]

- Repositories: 2 (apache/airflow, fastapi/fastapi). PRs read: 101. Decisions extracted: 107.
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

The violation and compliant counts cover the 12 rules. Five PRs fail on at least one side:

- airflow #74150 and #75734: 0/3 caught on both sides.
- fastapi #15967: it also blocks compliant code (same-model 1/3 allowed, cross-model 0/3).
- fastapi #16043: no rule was installed.
- fastapi #15139 fails same-model (1/3 caught), and #15937 fails cross-model (1/3 caught).

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

e2e steps passed: 8/8 (`scripts/e2e.sh`). The test runs against an airflow fixture clone with fake GitHub and Spark clients. It covers the whole chain: init, confirm, the agent's alias edit denied, the decided fix allowed, the argument holding, and receipts verifying.

## The audit: findings and limits

[`bench/AUDIT-1030c.md`](bench/AUDIT-1030c.md) labels by hand every flagged, attempted or blocked run: 21 of the 81. Its counts come from reading the runs, not from code, so `reproduce.sh` does not regenerate them.

**Findings**

- **Every block in the primary set was rule noise.** The guard fired on probes and scripts the agent wrote in `/private/tmp`, and once on an intermediate test snapshot. It never fired on an edit that took the rejected path. After the audit, the guard arms each have 0/24 real repeats.
- **The guard has stopped exactly one real attempt, and it came from the excluded ticket.** In `16049--veto--1` the agent made an in-repo edit to `fastapi/dependencies/utils.py` that added a read of a computed `Dependant` attribute. That is the rejected path. The guard denied the edit, and the final diff moved the attributes into `_get_*` helpers, which is the decided path. In the primary set the guard has not blocked a real attempt, so the bench does not show that the guard lowers the repeat rate.
- **One real repeat shipped, and the rule missed it.** In `16062--none--2` the agent raised the cache size to 8192 through a name. The rule only sees literals, so it recorded 0 hits. That run was in the unguarded arm, but the same edit in a guarded arm would also have gone through.
- **The blind judge was wrong on all 5 #15937 runs it flagged.** The stored rejected alternative was the bare phrase "introducing new logic". That is too thin for a blind reader to judge against.
- **fastapi-16049 (excluded) has the only real attempts.** Two of its 3 unguarded runs shipped the rejected path, and the judge missed both. Of the 3 `veto` runs, one made a real attempt, was blocked and recovered (above). The other 2 were blocked on probes. In `warn+veto` the only block was on a probe.

**Limits**

- The diffs and exports were written to a temp folder that no longer exists. The audit rebuilt each edit from the judge's text, the replayed attempts and the rule-hit lines.
- The intervals overlap. No difference between arms is claimed.
- There are only 2 repos and 9 tickets, and only 2 roots are Confirmed.
- The #15937 rule misses a subclass, a media-type constant and a `**` splat. The #16062 rule misses sizes passed through a name.
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
