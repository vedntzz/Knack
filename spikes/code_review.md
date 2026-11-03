# Code review: engine changes merged 2026-11-01/02 (KN-98 … KN-116)

Read-only review of every engine change in PRs #91–#120 (`git diff 81c4132^1 1c2af20 -- knack`),
plus the data they ship. Nothing below is fixed in this review. Severity:
**P0** wrong block/allow or key leak · **P1** wrong data shown or claim unproven · **P2** quality.

"Proven" means reproduced with a scratch script or test (dummy keys, scratch `KNACK_HOME`);
"read" means grounded in the code but not run.

Fixed on this branch already (tests/test_break.py, freeze exception for the jsonl readers):
torn UTF-8 crashed `chain._lines`, `rulings.load_rulings`, `events._lines` (console 500s, verify
codec error); `_last_hash` now chains from the last whole receipt, starts a fresh line after a
torn tail, and reads the whole file when one receipt outgrows the 64 KiB tail (before, one
module-wide match over 64 KiB stopped every later receipt for good).

## P0

### P0-1 · KN-113 · a multi-line key file leaks the key to stderr, guard_errors.log and self_checks.jsonl
- `knack/watch/credentials.py:36` (`.strip()` only trims the ends); same for env values in `knack/pipeline/clients.py:34-38`.
- Why: a newline inside the key reaches the Authorization header; http.client raises
  `ValueError: Invalid header value b'<scheme> <key>'` before connecting. `watch/hook.py:_report`
  logs and prints `str(error)`; `miss/selfcheck.py` stores it as Spark Open's "answer" in
  `self_checks.jsonl`, which for `data/registry/*.json` sits in the repo and is not gitignored.
  The hook test fakes every client, so the real header is never built.
- Proven: two dummy lines in `$KNACK_HOME/github_token` →
  `knack watch error: ValueError: Invalid header value b'<scheme> <line 1>\n<line 2>'` with both dummy lines in full on stderr and in `guard_errors.log`.
- Fix: refuse any key with whitespace or a non-printable character (`RefusedCredentials`, naming the path only); never print `str(error)` for HTTP-layer errors in `_report` / `_error_text`.

### P0-2 · KN-97 · the committed must-pass case is denied by the committed, Confirmed, pinned rule
- `data/registry/cases/airflow-75025/must-pass-6633cbc47011.json` vs `data/rules/airflow/75025.yml` (sha `ecf207d0e1ef`, root `airflow-75025-1` Confirmed, pinned to it).
- Why: the v2 install and re-pin happened only in the sandbox; `mockups/fixtures/self_repair/rule/v2.yml` (`865e1a983ffe`) allows compliant_3, the shipped rule does not. `tests/pipeline/test_self_repair_live.py` checks only the frozen mockups copies. The recovery page says the edit passes; the real guard blocks it.
- Proven: `data/rules/airflow/75025.yml ecf207d0e1ef denies must-pass: True`; `rule/v2.yml 865e1a983ffe denies must-pass: False`.
- Fix: commit v2 and re-pin with `knack confirm` (a person), or drop the case from the registry; add a test that every committed registry case holds against its installed rule.

### P0-3 · KN-106/KN-107 · the blocked agent is handed the command that allows its own edit
- `knack/dispute/latest.py:23,73` (`RESOLVE_HINT` printed by `knack argue`), `knack/cli.py:357-371` (`_resolve_command`), `knack/hooks/pretool_guard.py:33` (`DISPUTE_LINE` tells the agent to argue).
- Why: the deny tells the agent to run `knack argue`; an ESCALATE prints `knack resolve <hash> allow|retire|uphold --reason`. `resolve` (and `confirm`) has no tty or human check and `--by` defaults to git `user.name`, so an agent with a shell can allow its own edit, recorded as allowed by the user, and promote the case to must-pass. `test_injected_allow.py` proves no *model output* allows; it cannot tell a person from an agent, so "only a person" is unproven.
- Read, not run.
- Fix: refuse `resolve`/`confirm` when stdin is not a tty (or require typing the hash back); move `RESOLVE_HINT` out of argue's stdout to the held page.

## P1

### P1-1 · KN-106 · "is this deny settled" is read three ways, and the check is not under the lock
- `knack/roots/resolve.py:47-54`, `knack/miss/sources.py:86-96` (`_refuse_human_allow`), `knack/dispute/latest.py:101-104` (`_denied_here`).
- Why: `resolve` uses `resolution_of` over the chain; `sources` only looks at the receipt's own `resolution`; `latest_deny` does not check. So:
  - `knack false-block <deny>` after `knack resolve <deny> uphold` is accepted as must-pass and loosens the rule the person just upheld. Proven: `false-block on upheld deny accepted: [('must-pass', 'widgets-3')]`.
  - `knack argue` re-disputes a settled deny and can create a held case that can never close (read).
  - Two concurrent `resolve`s both pass the check: proven `[('allow', 'maria'), ('uphold', 'bob')]` recorded for one deny; `human_allow` lets the edit through while the console shows the first.
- Fix: one `is_settled(chain, hash)` used by resolve, sources and latest; re-check it inside `append_receipt`'s lock (an `append_resolution`).

### P1-2 · KN-106 · resolve applies the correction before the receipt, and a receipt failure is a traceback
- `knack/roots/resolve.py:51-54`, `knack/cli.py:362`.
- Why: `_apply` (retire drops the rule, correction logged) runs before `append_receipt`; if the append raises, the registry has changed with no receipt, `human_allow` never sees an allow, and a retry duplicates the correction. `cli` catches `ResolveError, RootStoreError, ValidationError, OSError` but not `ValueError` (`NO_WHOLE_RECEIPT`). Proven before the 64 KiB fix on this branch (`resolve raised ValueError`, `corrections added: 1`); still reachable on a chain with no whole receipt.
- Fix: append the receipt first, then apply; catch `ValueError` in `_resolve_command`.

### P1-3 · KN-101/KN-112 · live rule and registry files are rewritten in place while the guard reads them
- `knack/miss/loop.py:393-395` (`_install`), `knack/pipeline/stages.py:361-367` (`_write_registry`), `knack/roots/store.py:29-31`, `knack/miss/cases.py:63`, `knack/roots/gate.py:144`.
- Why: `write_text` truncates then writes. A hook reading a truncated rule gets `allowed=True, reason='no rule matched'` (not even guard-error); a torn registry fails validation and `scoped_quietly` allows silently. A crash between leaves it permanent.
- Proven (outcome, race not timed): real root `airflow-75774-1` (Confirmed, no pin): `empty (just truncated): allowed=True reason='no rule matched'`; half a registry → `hook output: None` + ValidationError logged.
- Fix: temp file in the same folder + `os.replace`, everywhere these files are written.

### P1-4 · KN-114 · a false-block repair on a rule whose top level is `all` drops the whole Confirmed rule
- `knack/miss/coverage.py:90-95` (`rule_branches`), `knack/miss/repair.py:11-12`.
- Why: only a top-level `any` is split into branches. 6 of 13 committed rules are top-level `all`. A must-pass that contradicts one nested alternative drops the whole old rule and installs Spark's; the no-coverage-loss gate passes because the whole rule counts as one exercised branch.
- Proven on `data/rules/airflow/75774.yml`: `whole rule dropped: ['all']`, `candidate == spark rule: True`, `coverage losses: []`, `old denies TimeDelta form: {'timedelta'} candidate denies: set()`. (75774's held-out set would likely catch this one; a rule whose inputs miss a nested alternative would not be caught.)
- Fix: if the old rule is not a top-level `any`, refuse the drop (unrepairable, old rule stays) or descend into the nested `any`.

### P1-5 · KN-114 · a branch dropped on purpose is reported as coverage loss
- `knack/miss/coverage.py:42-43, 86-89` (`_unexercised_dropped`).
- Why: a contradicted branch no input exercises is counted as "dropped a v1 branch no input exercises", so that false block can never be repaired, and the gate blames the wrong thing.
- Proven: old `any:[foo,bar]`, must-pass `bar(2)` → `losses: ['dropped a v1 branch no input exercises: {"pattern": "bar($$$)"}']`.
- Fix: pass the contradicted branches in and exclude them from `_unexercised_dropped`.

### P1-6 · KN-101 · named registries in one folder share watch state, locks and rule files
- `knack/pipeline/stages.py:340-344` (`_rule_path`), `knack/watch/run.py:48,79-83`, `knack/watch/state.py:21-32`, `knack/pipeline/merged.py:23`.
- Why: `out = registry_path.parent`, so `data/registry/airflow.json` and `fastapi.json` share `watch.json`, `watch.lock`, `rules/<N>.yml`, `work/`, `self_checks.jsonl`. The same PR number in two repos overwrites one rule file with the other repo's rule under the first registry's (possibly Confirmed) roots; one repo's `seen_head` makes the other stop watching silently.
- Proven: `rule paths … same file: True`; `airflow watch sees seen_head: head-of-widgets`.
- Fix: key state and rules per registry stem (`<stem>.watch.json`, `rules/<stem>/<N>.yml`).

### P1-7 · KN-94 · the home page 500s when kept receipts have no sibling self_repair folder
- `knack/console/pages/recovery.py:85` (`cases[0]`), `:70` (`load_repair` misses `IndexError`), `knack/console/app.py:148` (`console_repairs`).
- Why: `KNACK_CONSOLE_RECEIPTS=~/demo/r.jsonl` derives `~/self_repair`; no cases → `IndexError` → `GET /` (via `repaired_roots`) and `/recovery/x` are 500. `KNACK_CONSOLE_RECEIPTS=/receipts.jsonl` crashes `serve()` (`Path('/').with_name`).
- Proven: `load_repair(<missing or empty folder>)` raises `IndexError`.
- Fix: `if not cases: return None` (or catch `IndexError`); derive repairs only when the folder exists.

### P1-8 · KN-94 · the recovery page states outcomes the run does not back
- `knack/console/pages/recovery.py` `gated()` :293-296, `receipt()`, `passes()`, `confirm_line()`, `reconfirmed()`, `recompiled()`; `knack/console/repair_facts.py:14,254` (`PASS.findall`).
- Why: only PASS gate lines are kept, so a FAIL is dropped and the step still says "Every gate passed."; "Allowed/Denied/both pass" ignore `Edit.decision`; attempt ordinals are fixed strings; "A person re-confirmed it" shows with no confirm. Tests assert only on the one frozen fixture, so none of these can fail.
- Proven (reviewer script): `gate FAIL -> 'Every gate passed.' shown: True | FAIL line shown: False`; `allowed.decision=deny -> still says both pass: True`.
- Fix: collect FAIL lines and title from them; derive words from `decision`; number by position; neutral title when `confirmed_by` is None.

### P1-9 · console · a person's resolution is shown as a guard block, or not shown
- `knack/console/facts.py:82` (`blocked = outcome == "deny"`), `knack/console/facts.py:257` (`held = rulings[-1].decision == "escalate"`), `knack/console/pages/argue.py:186`.
- Why: an uphold receipt has decision `deny`, so `/verdict/<uphold>` says "Blocked … 0.0 ms to decide … argue it". After `resolve allow`, argue still says "stay blocked" and the verdict page never renders `view.resolution`. Escalate-then-hold hides the held link while `/held` is 200.
- Proven (reviewer script): `uphold page: ['Blocked', 'Stopped before it was written', '0.0 ms to decide', 'argue it']`; `argue links held? False | held page: 200`.
- Fix: `blocked` false for resolution receipts; render the resolution; `held = any(... == "escalate")`.

### P1-10 · KN-93 · day squares and the decisions list disagree on a root's day; out-of-span roots counted as "not recorded"
- `knack/console/facts.py:383` (`by_day`, local zone) vs `:91,:475` (`day_of`, stamp's zone); `knack/console/pages/day.py:156`.
- Proven (reviewer script, clock −05:00): list `merged Oct 20 2026`, cell `Oct 19 2026 · 1 decision`; a 2023 root shows as `1 merge date not recorded`.
- Fix: one zone for both; count undated from `merged_at is None` only.

### P1-11 · KN-98/KN-107 · Ctrl-C during the second opinion loses the ruling
- `knack/cli.py:619-622, 636-642`.
- Why: the ruling is written only after Spark Open returns (up to 60 s); ESCALATE is already printed. Proven by scratch pytest: `rulings file exists: False`.
- Fix: write the ruling first and the models after, or `try/finally`.

### P1-12 · KN-104a · rulings record a constant model name; roots record the model the response named
- `knack/dispute/argue.py:52-64` (`SPARK_MODEL`), `knack/dispute/second.py:76`, `knack/dispute/rulings.py:52-54`. The test's fake has a different class attribute, so it cannot fail for the live client. Read.
- Fix: keep `last_model` from the response in `SparkRuling`; use `last_model or model`.

### P1-13 · KN-105 · a root only Spark Open found is Uncorroborated but its model is recorded as "corroborated"
- `knack/pipeline/corroborate.py:30,57-60`. Proven: `widgets-9-2 Uncorroborated [('spark-open', 'corroborated')]`.
- Fix: `found_by(other.call, "extracted")` for those pairs.

### P1-14 · KN-102 · a hold can cite one letter and pass the verbatim check
- `knack/dispute/argue.py:124-126` (`_is_verbatim`: any non-blank substring). Proven: `hold ['a'] | Maria said aliases are forbidden forever …` printed as HOLD and shown on the console. Never allows an edit, but shows invented words as the decider's.
- Fix: require whole-word citations of at least `MIN_QUOTE_WORDS` (4).

### P1-15 · KN-107 · "Spark Open gets 60 s" is a per-read socket timeout, not a cap
- `knack/pipeline/http.py:35-40`, `knack/pipeline/clients.py:55-58`. Proven: timeout 0.3 s, a trickling server, call took 5.8 s, nothing in `timed_out`. README states the 60 s limit.
- Fix: a whole-call deadline (thread + `join(60)`), or say "60 s per read".

### P1-16 · self-checks reader still crashes on torn UTF-8
- `knack/miss/selfcheck.py:105` (`load_checks`), read by `knack/console/pages/held.py:64`. Outside this branch's freeze exception. Proven: `UnicodeDecodeError … unexpected end of data`.
- Fix: `errors="replace"`, as the other readers.

## P2

- **Crash before any rule runs leaves no receipt** · `knack/hooks/pretool_guard.py:71-76` · the outer `except` allows and logs (tested in test_break) but writes no guard-error receipt, so the console shows nothing. Fix: append a guard-error receipt from `decide`'s handler, quietly.
- **append_ruling glues onto a torn tail** · `knack/dispute/rulings.py:62-66` · no fresh-line check, so the next ruling after a torn write is lost too. Fix: the `_fresh_line` used by `append_receipt`.
- **required_env names no key file** · `knack/pipeline/clients.py:37` · consistent (only watch reads files), but `knack init/argue` say only "X is not set". Fix: say "export X" explicitly.
- **every-branch-contradicted returns Spark's rule unfiltered** · `knack/miss/repair.py:11-12` · Spark can re-add the dropped branch; `test_every_branch_contradicted_leaves_sparks_rule` locks this in. Proven. Fix: filter `gone` before the early return.
- **Spark's top-level constraints/utils dropped on merge** · `knack/miss/repair.py:22-24` · over-blocks or invalidates the merged rule (gates catch it). Proven. Fix: refuse the merge when the new rule has other top-level keys.
- **rerun_deny takes the first prefix match and skips human allows** · `knack/hooks/pretool_guard.py:201-217` · `""` matches the oldest receipt; comment says "as knack resolve accepts", but resolve needs the full hash. Fix: exactly one match, ≥12 chars, apply `_unless_human_allowed`.
- **Missing escapes** · `render.py:33` (`watching`), `argue.py:198`, `verdict.py:212`, `held.py:85,117`, `day.py:226`, recovery hash slices · a crafted kept receipts file injects markup (proven: `<img onerror>` reaches `/argue` and `/held`). Fix: `escape()` each.
- **No Host check on the loopback console** · `knack/console/app.py:_bare_app` · DNS rebinding can read `/day`, `/graph`, `/verdict/*` (proven: `Host: evil.example` → 200). Fix: `TrustedHostMiddleware(["127.0.0.1", "localhost"])`.
- **events: no repo filter, unbounded `seen`, whole-file re-parse every 0.25 s, a deny between render and connect is never sent** · `knack/console/events.py` · read. Fix: tail by byte offset; send repo.
- **/day and / disagree** · `knack/day/receipts.py:39` labels uphold/retire "learn"; the day page's Today drops rulings and warns. Fix: one kind per action.
- **"not recorded" model printed as a model name** · `knack/console/pages/argue.py:157,234` · compare to `NOT_RECORDED`.
- **re-ask failure drops Spark's first trace** · `knack/dispute/argue.py:57-64,103-109` · one `ModelCall` per call.
- **gate log says "re-read twice"; the PR is read twice in total** · `knack/roots/gate.py:112`.
- **case paths not confined** · `knack/miss/loop.py:253-258` · `folder/"before"/case.file` with an absolute or `../` file writes outside the work dir (hand-made JSON only). Fix: `is_relative_to(folder)`.
- **secret scan's `$(...)` exemption too broad** · `tests/test_no_secrets.py:55` · `Bearer $(:)<key>` passes. Fix: `\$\([^()]*\)`.
- **README.md:78** still says `allow|retire`; line 80 and the CLI have `uphold`.

## Checked and sound
- Guard blocks only on a Confirmed root; a receipt-write failure keeps the deny (test_break).
- No model text can satisfy the KN-115 gate (`verbatim` checked against thread text); a read failure counts as a miss.
- Coverage, `prove._edit_row` and the guard share one "denies" test (`scan_file_with_rule` + `only_new`).
- Model output cannot create must-pass cases; only `false-block` or a person's promote can.
- Env key wins over file; empty env falls back; symlinked key files are mode-checked on the target.
- Unknown and malformed hashes are 404 on every console route (test_break).

## Top 5 to fix tonight
1. **P0-1 key leak:** refuse keys with whitespace in `credentials._key_from_file` and `required_env`; stop echoing HTTP error text in `watch/hook._report` and `selfcheck`.
2. **P0-2 shipped rule denies its own must-pass case:** decide v1 vs v2 for `data/rules/airflow/75025.yml` (person re-pins), and add the "every registry case holds against its installed rule" test.
3. **P0-3 agent can resolve its own block:** tty check on `knack resolve`/`knack confirm`; drop `RESOLVE_HINT` from argue's stdout.
4. **P1-3 non-atomic rule/registry writes:** `os.replace` from a same-folder temp file in `loop._install`, `stages._write_registry`, `roots.store`, `cases.save_case`, `gate._roll_back`.
5. **P1-1 + P1-2 settled-deny consistency:** one `is_settled` under the chain lock, used by resolve, false-block and argue; append the resolution receipt before applying the correction.
