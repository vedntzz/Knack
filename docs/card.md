# Knack

Knack blocks AI coding agents from edits that contradict a team's recorded decisions, and cites who decided, why, and the verbatim source.

## The block

A PreToolUse hook runs plain code (ast-grep, no model, no network) on the agent's edit before it lands.
If the edit adds a match for a Confirmed decision's rule, Muse Code gets a deny that names who decided, why, and the verbatim quote.

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
uv venv && uv pip install --python .venv/bin/python -e ".[dev]"
bash scripts/reproduce.sh
```

It reads only committed files and uses no network and no model. It prints each number beside the command that produced it.
