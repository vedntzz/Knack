# Knack

Knack is a guardrail for AI coding agents that blocks edits contradicting your team's past decisions.

## What it does

Muse Spark reads a repository's PR history and extracts the decisions the team made and the alternatives it rejected.
Knack compiles those decisions into rules and verifies each rule against that same history before trusting it.
A deterministic guard then blocks any agent edit that breaks a rule, citing who decided, why, and the verbatim source.

## Setup

```sh
uv venv && uv pip install --python .venv/bin/python -e ".[dev]"
```

Both hooks read one registry from `KNACK_REGISTRY`: the repo it guards (`owner/name`),
its `roots_dir`, and `rules` entries of `rule` plus `root_ids` (see `data/registry/airflow.json`).
They stay silent unless the session's `git remote get-url origin` is that repo.
The walk index is cached at `~/.knack/cache/<owner-name>/<HEAD>.json`.

## Status

Current results:

- **Extraction gate:** 3/3 passing.
- **Compile gate:** passes, with a repair loop.
- **Guard:** a real agent edit was blocked, with its citation, in 8.8 ms.

Spike notes and raw results are in [`spikes/`](spikes/).

## Built during the hackathon (Oct 26 – Nov 4, 2026)

Everything in this repository: the contracts, the guard and its replay of a real agent edit,
the repository indexer (file walker, function and call extraction), and the test suite.

## Prior research (disclosed)

Done before the event:

- The product requirements document (PRD).
- The demo-chain analysis of apache/airflow PR #75025.
- A prototype ast-grep rule.
- The Oct 25 unscripted agent test (`run_neutral_3.diff`).
- The Muse Code hook-contract test.

All prior research was rebuilt from scratch in this repository during the event.

## Honest labels

Every decision carries one of three labels:

- **Confirmed:** the decision is stated explicitly in the source.
- **Inferred:** the decision is implied but not stated.
- **Unknown:** the evidence is insufficient.

Only Confirmed decisions block. Inferred and Unknown decisions never block an edit.

## Attribution

The Airflow fixtures are excerpts from [apache/airflow](https://github.com/apache/airflow)
PRs [#75025](https://github.com/apache/airflow/pull/75025) and
[#44345](https://github.com/apache/airflow/pull/44345), licensed under the
[Apache License 2.0](http://www.apache.org/licenses/LICENSE-2.0).

## License

MIT. See [LICENSE](LICENSE).
