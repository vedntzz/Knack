# KN-95 step 2: watch's PostToolBatch hook, live inside Muse Code

**Result: the PostToolBatch hook fired, and watch neither installed nor discarded.** Muse ran knack's `PostToolBatch` hook after the agent's `git merge`. The hook started watch's background run, which stopped at once: `knack watch: GITHUB_TOKEN is not set`. No rule was compiled, so there is nothing installed or discarded to show. The merge is still pending in `watch.json`.

One run, no retries, 2026-11-02, on `feat/kn-95-live-rulings`, with real Muse Code (`muse exec`, Muse Code 1.4.14) and the real Spark key. `HOME` and `KNACK_HOME` were temporary, inside `$W`; the real `~/.knack` was not touched. `$W` = `/private/tmp/claude-501/-Users-vedant-Documents-knack/3ed37a32-9dae-44ca-9e0d-709b1515fbed/scratchpad/ptb.0LytBo`.

## Setup

- **Script:** `spikes/posttoolbatch_live.sh`, run once. It is `spikes/self_improving.md`'s #75271 fixture, with the merge moved into a Muse session.
- **Registry:** a copy of the committed `data/`, set back to before #75271 merged: its registry entry, rule, roots and held-out set were removed. The result was saved as `$W/airflow.before.json`.
- **Sandbox clone:** `$W/airflow`, with origin `https://github.com/apache/airflow.git`. It holds #75271's two files at base `70a7816`, fetched read-only from the GitHub contents API. Branch `pr-75271` holds them at head `91da700`, committed as `Live proof merge (#75271)`.
- **Hooks:** `knack watch` installed both its triggers. The Muse settings went to `$HOME/.config/muse/settings.json`, the path Muse reads under the temp HOME, as the bench's arm homes do.
- **Trigger isolated (Vedant's call):** the agent ran `git -c core.hooksPath=/dev/null merge …`. git's `post-merge` hook stayed installed but could not run, so only `PostToolBatch` could start watch.
- **Environment:** Muse ran with `META_API_KEY` set from `MODEL_API_KEY`, as the bench does. Unlike the bench, `GITHUB_TOKEN`, `MODEL_API_KEY` and `BASETEN_API_KEY` were left in Muse's environment so the hook could inherit them. `GITHUB_TOKEN` was certainly set: the script runs under `set -u`, and its curl fetches used it and succeeded.

## Commands and output (verbatim, `$W` shortened)

```text
$ knack watch --registry $W/data/registry/airflow.json --muse-settings $HOME/.config/muse/settings.json
knack watch apache/airflow
  post-merge hook: $W/airflow/.git/hooks/post-merge
  Muse Code PostToolBatch hook: added to $W/home/.config/muse/settings.json
  watching merges after eda156c
  self-check: Spark Open judges each merge when BASETEN_API_KEY is set
exit 0
```

```json
{
  "schema_version": 1,
  "hooks": {
    "PostToolBatch": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "sh -c '/usr/bin/arch -arm64 /Users/vedant/Documents/knack/.venv/bin/python -m knack.watch.hook tool-batch --registry $W/data/registry/airflow.json || true'"
          }
        ]
      }
    ]
  }
}
```

```text
main at eda156c, pr-75271 at 3aafe0b
$ muse exec --disable-web-tools --disable-request-user-input --session-id 774c0abe-8822-46df-a35b-3ae34e200611 'Run exactly this one shell command in the current directory, once, and then stop: git -c core.hooksPath=/dev/null merge --ff-only pr-75271'
muse exit 0
muse: workspace root: $W/airflow (cwd default)
muse: Agent delegation: auto unavailable: workspace is untrusted.
Fast-forward merge to pr-75271 completed (eda156c..3aafe0b).
main now at 3aafe0b
```

## Proof the PostToolBatch hook fired

These are from `muse export --session 774c0abe-8822-46df-a35b-3ae34e200611`, the export the bench reads hooks from. Here are the run events, in order, with fields trimmed but values verbatim:

```json
{"kind": "assistant_tool_calls_committed", "tool_calls": [{"name": "bash", "args": "{\"command\":\"git -c core.hooksPath=/dev/null merge --ff-only pr-75271\",\"description\":\"Merge branch with fast-forward only\"}"}]}
{"kind": "tool_result_batch_committed"}
{"kind": "hook_run_started", "hook_key": "$W/home/.config/muse/settings.json:post_tool_batch:def-155b9eaef62e562e", "event": "PostToolBatch", "display_order": 0}
{"kind": "hook_run_terminal", "hook_key": "$W/home/.config/muse/settings.json:post_tool_batch:def-155b9eaef62e562e", "event": "PostToolBatch", "display_order": 0, "status": "completed", "duration_ms": 175, "exit_code": 0, "stdout": "", "stderr": "", "error": null}
```

The hook got past both of its cheap checks:
- `ran_shell` was true: the batch held a `bash` call.
- `pending_root` found a merge after the baseline.

So it spawned the background run, which wrote `$W/data/registry/watch.log` at 11:01:16, 13 s before the export.

## What watch did

`$W/data/registry/watch.log`, the whole file:

```text
knack watch: GITHUB_TOKEN is not set
```

- **Neither installed nor discarded.** The run stopped at the credential check, before `[1/5] select`, as `_report` handles `MissingCredentials`: print, exit 0, nothing logged as a knack error.
- **No work folder:** `$W/data/registry/work/` does not exist.
- **No new rule or roots.** `diff $W/airflow.before.json $W/data/registry/airflow.json` prints nothing.
- **`watch.json` is unchanged:** `{"seen_head":"eda156c4b37dc0bd769706f90f672db85e460293"}`. The merge is still pending, so the next shell batch or merge in this clone would try again.
- The agent's turn was not affected: the hook took 175 ms and exited 0.

## Why, as far as this run shows

`GITHUB_TOKEN` was in the environment `muse exec` started with, and the hook's background process did not have it. So Muse Code 1.4.14 appears not to pass `GITHUB_TOKEN` to `PostToolBatch` hook commands.

This is not verified. Muse documents no hook-environment rule I could find, and its binary gave no hint. watch checks `GITHUB_TOKEN` first, so this run cannot say whether `MODEL_API_KEY` and `BASETEN_API_KEY` reached the hook either.

## Not done

Per the brief, the result is recorded and the run was not repeated. The obvious next step needs its own ticket and one run. That step is to make watch's credentials not depend on what Muse passes to hooks. For example, the hook command could carry the path of a credentials file outside the agent's view, rather than the secrets.

## Rerun 2026-11-02: GITHUB_TOKEN exported from ~/.github_token

**Result: the PostToolBatch hook fired again, and watch again neither installed nor discarded.** Its background run stopped at the same line, `knack watch: GITHUB_TOKEN is not set`, even though the token had been exported in the command that launched the script.

One run, no retries, same branch, same script, same Muse Code 1.4.14 (1.4.14-R7309.1). The only change was the launch command: `export GITHUB_TOKEN=$(cat ~/.github_token) && bash spikes/posttoolbatch_live.sh`. The token was not printed or saved; a grep of the run log for it found 0 matches. `$W` = `/private/tmp/claude-501/-Users-vedant-Documents-knack/3ed37a32-9dae-44ca-9e0d-709b1515fbed/scratchpad/ptb.zMaoIc`.

### Output (verbatim, `$W` shortened)

```text
$ knack watch --registry $W/data/registry/airflow.json --muse-settings $HOME/.config/muse/settings.json
knack watch apache/airflow
  post-merge hook: $W/airflow/.git/hooks/post-merge
  Muse Code PostToolBatch hook: added to $W/home/.config/muse/settings.json
  watching merges after e26e22d
  self-check: Spark Open judges each merge when BASETEN_API_KEY is set
exit 0
main at e26e22d, pr-75271 at b43d322
$ muse exec --disable-web-tools --disable-request-user-input --session-id 575d0208-e290-448c-949a-cb9aa084516d 'Run exactly this one shell command in the current directory, once, and then stop: git -c core.hooksPath=/dev/null merge --ff-only pr-75271'
muse exit 0
muse: workspace root: $W/airflow (cwd default)
muse: Agent delegation: auto unavailable: workspace is untrusted.
Fast-forwarded e26e22d..b43d322.
main now at b43d322
export exit 0
```

The settings file was the same as in the first run, apart from the `$W` path.

### Hook fired

From `muse export --session 575d0208-e290-448c-949a-cb9aa084516d`, the events in order, with fields trimmed:

```json
{"kind": "assistant_tool_calls_committed", "tool_calls": [{"name": "bash", "args": "{\"command\":\"git -c core.hooksPath=/dev/null merge --ff-only pr-75271\",\"description\":\"Merge branch fast-forward only\"}"}]}
{"kind": "tool_result_batch_committed"}
{"kind": "hook_run_started", "hook_key": "$W/home/.config/muse/settings.json:post_tool_batch:def-c3337cdf8941e585", "event": "PostToolBatch"}
{"kind": "hook_run_terminal", "hook_key": "$W/home/.config/muse/settings.json:post_tool_batch:def-c3337cdf8941e585", "event": "PostToolBatch", "status": "completed", "duration_ms": 154, "exit_code": 0, "stdout": "", "stderr": "", "error": null}
```

### What watch did

`$W/data/registry/watch.log` was written at 11:38:29, 29 s before the export. This is the whole file:

```text
knack watch: GITHUB_TOKEN is not set
```

- **Neither installed nor discarded.** The run stopped at the credential check, before `[1/5] select`, so there is no select/compile/judge trace to show.
- **No work folder:** `$W/data/registry/work/` does not exist.
- **No new rule or roots.** `diff $W/airflow.before.json $W/data/registry/airflow.json` prints nothing, and `$W/data/rules/airflow/` has no 75271 file.
- **`watch.json` is unchanged:** `{"seen_head":"e26e22d92d7df3031728de1016e5d201901be9c4"}`, so the merge is still pending.

### What this rerun settles

In both runs, `GITHUB_TOKEN` was in the environment that started `muse exec`, and it was missing in the hook's background process. In this run it was certainly exported: the script's curl fetches used it and succeeded. So the first run's failure was not a token the shell had failed to pass on. The likeliest cause is that Muse Code 1.4.14 does not pass `GITHUB_TOKEN` to `PostToolBatch` hook commands.

This is still inferred, not verified. Muse documents no rule for the hook environment. Exporting the token in the shell does not fix it, so the fix belongs in watch: the next step from "Not done" above still stands. That step is to have the hook command carry the path of a credentials file outside the agent's view, rather than depend on what Muse passes to hooks.

## Rerun 2026-11-02 (KN-113): watch's keys only in files, none exported

**Result: the PostToolBatch hook fired, watch ran past select, and it installed #75271's rule.** The proof passed every side, plus the 3.3.2 old release and Spark Open's held-out set (3/3 caught, 3/3 allowed). Its root was written as Inferred, so the guard will not block on it until someone confirms it.

One run, no retries, on `fix/kn-113-watch-token-file`, with the same Muse Code 1.4.14 (1.4.14-R7309.1). The script was `spikes/posttoolbatch_live_files.sh`. It is `posttoolbatch_live.sh` with only these changes:
- **The three keys are only in files.** It copies `~/.knack/github_token` into the sandbox's `KNACK_HOME`, and writes `model_api_key` and `baseten_api_key` there from the launching shell. All three are mode 600, and none is printed. Then it unsets `GITHUB_TOKEN`, `MODEL_API_KEY`, `BASETEN_API_KEY` and `META_API_KEY`, and prints `key vars in env: 0`.
- **The fixture fetches** read the token file.
- **Muse's own key:** Muse gets its `META_API_KEY` inline from the model key file. That variable is for Muse's own run only; watch does not read it.
- **It waits** for watch's background run to exit, then checks every file under `$W` for each key.

The real `~/.knack` was only read. `$W` = `/private/tmp/claude-501/-Users-vedant-Documents-knack/8a14c651-6e15-420d-8a70-0e98b3e44052/scratchpad/ptb.AQS2Vi`.

### Output (verbatim, `$W` shortened)

```text
--- key files
-rw------- 93 bytes $KNACK_HOME/github_token
-rw------- 48 bytes $KNACK_HOME/model_api_key
-rw------- 45 bytes $KNACK_HOME/baseten_api_key
key vars in env: 0
$ knack watch --registry $W/data/registry/airflow.json --muse-settings $HOME/.config/muse/settings.json
knack watch apache/airflow
  post-merge hook: $W/airflow/.git/hooks/post-merge
  Muse Code PostToolBatch hook: added to $W/home/.config/muse/settings.json
  watching merges after 94605fd
  self-check: Spark Open judges each merge when BASETEN_API_KEY is set
exit 0
main at 94605fd, pr-75271 at e518f6e
watch.json before muse: {"seen_head":"94605fda861069a86ca743c7af26c01065a6d362"}
$ muse exec --disable-web-tools --disable-request-user-input --session-id f15451c6-3468-471e-9bff-21d3503632e1 'Run exactly this one shell command in the current directory, once, and then stop: git -c core.hooksPath=/dev/null merge --ff-only pr-75271'
muse exit 0
muse: workspace root: $W/airflow (cwd default)
muse: Agent delegation: auto unavailable: workspace is untrusted.
Done. Fast-forwarded 94605fd..e518f6e.
main now at e518f6e
export exit 0
--- background run gone after ~320s (pgrep: 0 left)
--- watch.json after: {"seen_head":"e518f6ef896617e60ba5958cbb61fe3f893083b0"}
```

The settings file was the same as in the first run, apart from the `$W` path. The script exited 1, but only because its last `grep -v` had no lines to print. Every step above it succeeded.

### Hook fired

From `muse export --session f15451c6-3468-471e-9bff-21d3503632e1`, the events in order, with fields trimmed:

```json
{"kind": "assistant_tool_calls_committed", "tool_calls": [{"name": "bash", "args": "{\"command\":\"git -c core.hooksPath=/dev/null merge --ff-only pr-75271\",\"description\":\"Merge branch fast-forward only\"}"}]}
{"kind": "tool_result_batch_committed"}
{"kind": "hook_run_started", "hook_key": "$W/home/.config/muse/settings.json:post_tool_batch:def-1d0259cfd6dc70bd", "event": "PostToolBatch"}
{"kind": "hook_run_terminal", "hook_key": "$W/home/.config/muse/settings.json:post_tool_batch:def-1d0259cfd6dc70bd", "event": "PostToolBatch", "status": "completed", "duration_ms": 157, "exit_code": 0, "stdout": "", "stderr": "", "error": null}
```

### What watch did: installed

`$W/data/registry/watch.log`, the whole file:

```text
knack watch apache/airflow: 1 merged PR: #75271
[1/5] select   1 PRs read, 1 kept
[2/5] extract  reading 1 PRs
  #75271: 1 decision, 1 rejected alternative
  1 decisions found, 1 rejected alternatives (1 verbatim), 0 failed
[3/5] roots    1 Inferred roots written (0 Confirmed, 0 Unknown kept)
[4/5] compile  1 PRs with a verbatim rejected alternative
  adversary: meta-models/muse-spark-open-1026 writes variants, muse-spark-1.3 compiles
  #75271 old release: 3.3.2 (last release before merge 2026-10-28)
  #75271 proven on attempt 2
  #75271 held-out by meta-models/muse-spark-open-1026: 3/3 violations caught, 3/3 compliant allowed (pass)
[5/5] install  1 rules proven, 0 discarded, 5 in registry -> $W/data/registry/airflow.json
self-check airflow-75025 providers/common/compat/src/airflow/providers/common/compat/_resumable_job_mixin.py (the change takes the rejected path): muse-spark-1.3 no, meta-models/muse-spark-open-1026 no; logged only
self-check airflow-75025 providers/common/compat/tests/unit/common/compat/test__resumable_job_mixin.py (the change takes the rejected path): muse-spark-1.3 no, meta-models/muse-spark-open-1026 no; logged only
self-check airflow-75774 providers/common/compat/src/airflow/providers/common/compat/_resumable_job_mixin.py (the change takes the rejected path): muse-spark-1.3 no, meta-models/muse-spark-open-1026 no; logged only
self-check airflow-75774 providers/common/compat/tests/unit/common/compat/test__resumable_job_mixin.py (the change takes the rejected path): muse-spark-1.3 no, meta-models/muse-spark-open-1026 no; logged only
```

- **Trace:** `$W/data/registry/work/75271/writers.json` is `{"compiler": "muse-spark-1.3", "variants": "meta-models/muse-spark-open-1026", "heldout": "meta-models/muse-spark-open-1026", "adversary": "meta-models/muse-spark-open-1026"}`. So all three keys reached watch from their files: the GitHub fetches worked, Spark compiled and Spark Open wrote the variants.
- **Registry:** `diff $W/airflow.before.json $W/data/registry/airflow.json` adds one entry, `rules/75271.yml` with root `airflow-75271-1`. The rule was proven on attempt 2. Its sides: base flagged 1/2, head 0/2, rename-base 1/2, rename-head 0/2, violation variants 3/3, compliant variants 0/3. It had 0 false positives, the old release 3.3.2 gave 0 false positives, and the held-out set scored 3/3 caught, 3/3 allowed.
- **Root:** `$W/data/roots/airflow/airflow-75271-1.json` has status `Inferred` and seeded `false`.
- **Baseline:** `watch.json` moved to `e518f6e`, so the merge is no longer pending.
- **Agent's turn:** not affected. The hook took 157 ms and exited 0; the run took about 320 s in the background.
- **Keys not written out:** the script searched every file under `$W` for each key's value (`grep -rlF`), excluding the key's own file: `github_token: 0 files`, `model_api_key: 0 files`, `baseten_api_key: 0 files`. That covers the receipts, traces, work folder, logs and Muse's session export.

### What this rerun settles

The earlier runs found that the hook's process did not get the keys from the environment that started `muse exec`. With the keys in `$KNACK_HOME` files, mode 600, watch no longer depends on that environment and runs the whole pipeline from a Muse Code `PostToolBatch` hook. Whether Muse strips the environment on purpose is still not documented. With file keys, watch does not depend on the answer.
