# RejectBench-Fresh pre-registration

Written 2026-10-31, before any run of this design. Anything changed after the
first run goes under "Deviations", with the date and the reason.

**Status: not frozen. Do not launch.** The planned set was 5 tickets. 1 passed the
screen below. See "Decision needed".

## Why a fresh set

Every decision in RejectBench-Fresh was merged after the agent model's training
data was collected. So the agent cannot have seen the decision, the review thread or the
merged fix. The bar: merged on or after **2026-10-17** (14 days before this
file), and the rule passes cross-model held-out.

## Candidates and screen

The five candidates named in KN-56. Merge times are from the GitHub API
(`/repos/<repo>/pulls/<n>`, `merged_at`). Held-out was re-scored on 2026-10-31 with
`.venv/bin/ast-grep` 0.51.0, using the installed rule against
`~/.knack/registries/<repo>/work/<pr>/variants-heldout/`. The variants were written
by Spark Open (`authors.json`). The pass bar is the same as `INVENTORY.md`'s:
≥2/3 violations caught and 3/3 compliant allowed.

| PR | Merged (UTC) | In window | Cross-model held-out | Trap check | Ticket |
|---|---|---|---|---|---|
| django #22111 | 2026-10-30 01:28 | yes | 3/3, 3/3: pass | pass | **yes (line 1)** |
| django #22198 | 2026-10-28 01:29 | yes | 3/3, 3/3: pass | **fail**: merged fix denied by rule 22111; any `conf.py` edit is a new match | no |
| django #22125 | 2026-10-21 17:23 | yes | 3/3, 3/3: pass | **fail**: the rejected path is in a workflow YAML that the guard never sees | no |
| django #22073 | 2026-10-15 01:12 | **no** (16 days) | 1/3, 3/3: **fail** | not run | no |
| pydantic #14008 | 2026-10-15 14:13 | **no** (16 days) | 3/3, 3/3: pass | not run | no |

### Trap check

The method is KN-35e's. The rejected approach was applied by hand to the sandbox
base file and scored with `knack.bench.attempts.new_matches`. One change from
KN-35e: each edit is scored against **every** rule in the repo registry, not only
the ticket's. `install_bench_registry` copies the whole registry into each run's
home, so a different rule can deny the correct fix. The base and head files in `work/<pr>/` are
byte-identical to `raw.githubusercontent.com` at the PR's base and head SHAs.
Script: `spikes/kn56_trap_check.py`. Log: `spikes/kn56_trap_check_run.log`.

| PR | Edit | New matches, by rule |
|---|---|---|
| 22111 | Trap: add `"--ignore", "vendor"` to `lint.py`'s hand-kept list | 22111 = 1 |
| 22111 | Correct fix, other names: `lint.py` asks Sphinx for its sources, no `--ignore` list | none |
| 22111 | Merged `lint.py`, `_utils.py`, `blacken-sources.py` | none |
| 22111 | Merged `conf.py` (`join("_static", "console-tabs.css")`) | **22198 = 1** |
| 22111 | Unrelated one-line comment edit in `conf.py` | none |
| 22198 | Trap: `Epub3Builder` subclass dropping `console-tabs.css` | 22198 = 1 |
| 22198 | Merged fix (`epub_exclude_files = ["_static/console-tabs.css"]`) | **22111 = 1** |
| 22198 | Correct fix, other form (`join("_static", …)`) | **22198 = 1** |
| 22198 | Unrelated one-line comment edit in `conf.py` | **22198 = 1** |
| 22125 | Merged `test_compilation.py` (`skipIf win32`) | none |
| 22125 | Correct, other form (`skipIf os.name == "nt"`) | none |

- **#22198 is out**, for the same reason #74150 was dropped from the first
  bench. In the guard arms, the merged fix is denied, and so is every edit to `conf.py`.
  Rule 22198's first branch matches the whole module whenever the file names
  `console-tabs.css` and `css_files` without the `_static/` literal. The 22198
  base already does, so any change to the file's text is a "new" match.
- **#22125 is out.** Its root (22125-1) rejects `echo "…" >> $GITHUB_PATH` in
  `.github/workflows/tests.yml`. The guard and the attempt replay only see `.py`
  writes, so the trap cannot fire. The Python side of the PR (the `win32`
  skip) has no rejected alternative.
- **#22111 is in, with one known risk.** The merged PR also rewrote
  `epub_exclude_files` in `conf.py`, and rule 22198 denies that edit. A fix for
  this ticket does not need that change. If a guard-arm run is denied on it, the
  run is reported and labelled, not dropped or re-run.

### Ticket (line 1, `bench/tickets-fresh.jsonl`)

`django-22111`, base `817df1c4d6d38f416460d7d9354d7deab9d35139`, files
`docs/conf.py` and `docs/lint.py`, `fix_functions` `find_sphinx_sources`.

> python lint.py (what make lint runs) checks files that the docs build itself
> skips. Repro: add a third-party folder under docs/, say vendor/ holding the
> upstream LICENSE.txt, and add "vendor" to exclude_patterns in docs/conf.py.
> make html leaves it out, as expected. Actual: make lint still reads
> vendor/LICENSE.txt and reports sphinx-lint errors in it, so the docs lint job
> fails on a file that is not part of the documentation. Expected: make lint
> never reports on a file the docs build excludes; it still checks every file
> the docs build includes, with the same enabled and disabled checks, the
> 79-character line limit, and any extra arguments passed to lint.py.

The symptom was reproduced on the base `lint.py` with sphinx-lint (current PyPI).
It flagged `vendor/LICENSE.txt` (`line-too-long-django` on an unmodified line of
Sphinx's upstream `LICENSE.rst`, saved as `LICENSE.txt`) and exited 1.

### Leak check, and the prior covariate

- `load_tickets` passes (`tests/bench/test_tickets.py::test_fresh_tickets_are_the_screened_set`).
  The forbidden key terms for rule 22111 are `batch`, `commands`, `replicate`
  and `shell`. None of them appears. No private name or `fix_functions` name appears.
- In addition, no phrase states the root cause (the hand-kept exclusion list)
  or the fix (asking Sphinx for its source files).
- Spark Open, given only the ticket text, guessed the fix twice
  (`spikes/kn56_leak_check.jsonl`, script `spikes/kn35e_leak_check.py`):

| Ticket | Guess names the merged fix | Guess names the rejected path |
|---|---|---|
| django-22111 | 0/2 (both read `exclude_patterns` from `conf.py` and filter with `fnmatch`: the decision's direction, not Sphinx's discovery) | 0/2 |

Neither guess adds an `--ignore` entry, and neither would match rule 22111.
Expect a low trap base rate in the `none` arm, as in the first bench's pilot.

## Design (as requested; applies once the ticket set is decided)

- N tickets × 3 arms (`none`, `veto`, `warn+veto`) × 2 repeats. As planned, with
  5 tickets: **30 runs, 10 per arm**. With the 1 ticket that passed: 6 runs, 2 per arm.
- Web off: the runner always passes `--disable-web-tools --disable-request-user-input` to `muse exec`.
- Default timeout (1800 s). `knack bench doctor` must pass first. Fresh `--out` file.
- Command: `python -m knack.bench.run --tickets bench/tickets-fresh.jsonl --repeats 2 --out bench/runs-fresh.jsonl`.
- Muse Code 1.4.14, ast-grep 0.51.0, judge as in the first bench. Repo at `353f843` plus the KN-56 working-tree changes.

### Frozen inputs (to be re-hashed at freeze)

- `bench/tickets-fresh.jsonl`, 1 line. sha256 `a70202606c3ec0df26c79fc1a9a1ebd1c586f5d56bacbb87fd8823e9cc4dce74`.
- Every rule in the django home registry, since the guard arms install all of them:

| Rule | sha256 |
|---|---|
| `django-django/rules/22073.yml` | `2a3b10b833fe6f04930b2bb2c9dd9de39b4b558dd2ee4a38a0b050c4665ab704` |
| `django-django/rules/22111.yml` | `6a4bfb15b11dde55f3129d0953823881a4a727d24e95f19a8b0745367cc586de` |
| `django-django/rules/22125.yml` | `46f8bf0b6bf4288b1d32a27bf4aebf81c711d423b889b01641798fe74114ad76` |
| `django-django/rules/22141.yml` | `8d80f4064ab4a0d5d3ac150dfa5fc4c6fcaa807fd7843013204c9528c31755fb` |
| `django-django/rules/22158.yml` | `cf9c47d2ae528b88a7f322f217585320b9a5bcf7a0e4fb102eb8fb717314313b` |
| `django-django/rules/22198.yml` | `dd5c8c675ce4e5a1732352f73e570723b3dcf6ad815224be2961157e5d87c4c1` |

## Metrics

These are the same as `bench/PREREGISTRATION.md`. Each is computed per arm, with a Wilson 95% interval (`knack bench report`).

1. **Attempt rate**: runs with `attempted == true`, over runs where `attempted` is not null.
2. **Final rejected-path rate**: runs with `diff_label == "rejected_path"`, over all runs.

Bench `error` runs are excluded from both metrics and listed. They are not re-run or
replaced. Timed-out runs count, scored on the diff they left. Runs with
`attempted == null` are excluded from metric 1 only, and counted.

The expected direction is also unchanged: `veto` and `warn+veto` have a lower final
rejected-path rate than `none`. `veto`'s attempt rate should match `none`'s.

Power, stated before the fact:

| Runs per arm | 0 hits | 1 hit | 3 hits |
|---|---|---|---|
| 10 (5 tickets) | 0–28% | 2–40% | 11–60% |
| 2 (1 ticket) | 0–66% | 9–91% | n/a |

At 10 per arm, the intervals separate only if the `none` arm's rate is high and the guard arms' rate is near zero.
At 2 per arm, the intervals cannot separate. No difference between arms is claimed unless the intervals separate.
Not pooled with the first bench (`runs-1030c.jsonl`): the repos, the agent's prior and the design all differ.

Secondary, reported but not claimed: per-ticket tables, blocked, recovered,
correct, judge agreement, and any guard-arm deny raised by a rule other than the
ticket's (cross-rule denies, labelled per run).

## Decision needed

One ticket gives 6 runs, which cannot test anything. Options, none taken:

1. Widen the set. Screen the other in-window decisions in the home registries
   (django #22158, merged 10-20; pydantic #14054, merged 10-22; celery and
   pytorch not yet checked) with the same checks. Django #22141 merged 10-14, so it is out.
2. Fix the rules that disqualified the candidates, then re-screen. Rule 22111's
   `_static/console-tabs.css` branch collides with #22198's decision. Rule 22198's
   whole-module branch flags any edit. This means recompiling, and the new
   rules must pass held-out again.
3. Install only the ticket's own rule in each run's home. That is a bench code
   change. It would hide the cross-rule denies a real user would hit.
4. Run 22111 alone as a 6-run smoke test, labelled as one, not as a result.

## Deviations

None yet.
