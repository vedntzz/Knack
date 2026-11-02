# Knack

Knack blocks AI coding agents from edits that contradict a team's recorded decisions, and cites who decided, why, and the verbatim source.

## The block

A PreToolUse hook runs plain code (ast-grep, no model, no network) on the agent's edit before it lands.
If the edit adds a match for a Confirmed decision's rule, Muse Code gets a deny that names who decided, why, and the verbatim quote.
In this run (live, 2026-11-02) the verdict took 17.3 ms and the hook round trip 171 ms. Across today's three live runs, the spike quotes 16.3–18.4 ms and 163–256 ms; the two earlier runs' outputs are not in the repo, so no command regenerates those ranges ([spikes/one_story_live.md](../spikes/one_story_live.md)).

## Models

- **Muse Spark** (Meta) extracts decisions from merged PRs and compiles each into an ast-grep rule.
- **Muse Spark Open**, a second, separately run Meta model, extracts the same PRs again and writes held-out variants that Spark never sees.
- Neither model is in the verdict path. Only AST-checkable, human-confirmed rules can block.

## The numbers

- **101** merged PRs read, across apache/airflow and fastapi/fastapi.
- **17 of 101 PRs** yield **31 rejected alternatives**, all verbatim.
- **13 outcomes** per side on held-out rules: 8 pass, 3 no rule, 2 fail held-out.

## Verify

```sh
uv sync --frozen --extra dev --python 3.11
source .venv/bin/activate
bash scripts/reproduce.sh
```

It reads only committed files and uses no network and no model. It prints each number beside the command that produced it.
