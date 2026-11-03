# Knack

Knack blocks AI coding agents from edits that contradict a team's recorded decisions, and cites who decided, why, and the verbatim source.

## The block

A PreToolUse hook runs plain code (ast-grep, no model, no network) on the agent's edit before it lands.
If the edit adds a match for a Confirmed decision's rule, Muse Code gets a deny that names who decided, why, and the verbatim quote.
In this run (2026-11-02; recorded edit replay, real hook, real model calls in the argue steps): 171 ms hook round trip; 17.3 ms rule evaluation. Across today's three runs, the spike quotes 16.3–18.4 ms for rule evaluation and 163–256 ms for the round trip; the two earlier runs' outputs are not in the repo, so no command regenerates those ranges ([spikes/one_story_live.md](../spikes/one_story_live.md)).

## Models

- **Muse Spark** (Meta) extracts decisions from merged PRs and compiles each into an ast-grep rule.
- **Muse Spark Open**, a second, separately run Meta model, extracts the same PRs again and writes held-out variants that Spark never sees.
- Neither model is in the verdict path. Only AST-checkable rules on a Confirmed root can block.
- No model output can allow a block. The guard denies an agent's direct and quoted `knack resolve` and `knack confirm`, but an agent running as you can still get around it (a variable, a script, `python -c`); the CI knack-guard checks every pinned Confirmed root (5 rules, 7 roots) and reads no local receipts, so a local exception cannot satisfy it.

## The numbers

- **101** merged PRs read, across apache/airflow and fastapi/fastapi. 101 PRs → 107 decisions → 22 roots → 12 installed rules → 5 that block.
- **17 of 101 PRs** yield **31 rejected alternatives**, all verbatim.
- **13 outcomes** per side on held-out rules: 8 pass, 3 no rule, 2 fail held-out. 8 of 13 PRs pass each held-out evaluation (same-model and cross-model); 7 pass both. The sets are generated variants, not production regressions.

## Verify

```sh
uv sync --frozen --extra dev --python 3.11
source .venv/bin/activate
bash scripts/reproduce.sh
```

It reads only committed files and uses no network and no model. It prints each number beside the command that produced it.
