# Using Knack on your repo

Moved here from README.md in the Nov 2026 rewrite; the short README links here.

## Using it on your repo

Knack keeps its per-user files in `~/.knack`, or in `$KNACK_HOME` when `KNACK_HOME` is set: the home registries, `verdicts.jsonl`, `warns.jsonl`, `rulings.jsonl`, `corrections.jsonl`, `guard_errors.log` and caches. The test suite points `HOME` and `KNACK_HOME` at a temp folder for every test.

Each repo has one home registry: `~/.knack/registries/<owner-name>/registry.json`. `knack init` and `knack watch` write it. The hooks, `walk`, `confirm` and `reject` read it. `knack import --registry data/registry/airflow.json` merges an existing registry in without overwriting reviewed roots, and `KNACK_REGISTRY` overrides the registry path. The hooks stay silent unless `git remote get-url origin` has a home registry.

No outside login is needed to clone, install, run `bash scripts/reproduce.sh` or open the console: the repo is public, `uv sync` fetches packages without an account, and those steps read no key. Keys matter only for live runs of `knack init`, `knack watch` and `knack argue`. [`.env.example`](../.env.example) lists them with placeholder values (`MODEL_API_KEY` for Spark, `BASETEN_API_KEY` for Spark Open, `GITHUB_TOKEN`, read-only); Knack does not read that file, so export them or put each in its `~/.knack` file as in [Muse Code setup](#muse-code-setup).

Every committed run is on public repos (apache/airflow, fastapi/fastapi); on a private repo, `knack init` and `knack watch` would send PR text to Meta (Spark) and Baseten (Spark Open), while the guard hook stays local and uses no network.

## Muse Code setup

Muse Code reads its hooks from the user-level `~/.config/muse/settings.json`. These are the two guard entries. `/abs/path/to/Knack/.venv/bin/python` stands for the absolute path of your clone's venv Python.

```json
{
  "schema_version": 1,
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "write_file|edit_file|bash",
        "hooks": [
          {
            "type": "command",
            "command": "sh -c '/abs/path/to/Knack/.venv/bin/python -m knack.hooks.pretool || true'"
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "sh -c '/abs/path/to/Knack/.venv/bin/python -m knack.hooks.warn || true'"
          }
        ]
      }
    ]
  }
}
```

- `PreToolUse` is the entry `scripts/demo_block.sh` writes, byte for byte apart from that path. The demo writes it into a sandbox copy of the file, because its `HOME` is a temp folder. Every `write_file`, `edit_file` or `bash` call goes through `knack.hooks.pretool`, which denies an edit that adds a match for a Confirmed rule, and a shell command that runs one of the person-only commands, spelled directly or with quoted words. It does not catch one hidden in a variable, a script or `python -c`.
- `UserPromptSubmit` is not written by `demo_block.sh`. It is the entry the bench's `warn+veto` arm writes ([`knack/bench/arms.py`](../knack/bench/arms.py)), in the same shape and with no matcher. `knack.hooks.warn` puts a Confirmed decision and its quote into the agent's context when a prompt names it. The bench adds a `KNACK_REGISTRY=<bench registry>` prefix to point it at its seeded registry. Without that prefix, the hook finds the home registry from `git remote get-url origin`.
- `|| true` makes a crashed hook exit 0 with no output, and Muse Code then allows the edit. The guard fails open.

`knack watch` adds two more hooks. It puts a `PostToolBatch` entry in the same file (`sh -c '... -m knack.watch.hook tool-batch --registry <registry> || true'`), which fires after an agent's tool batch, including a local merge made in the session; it does not fire on a GitHub merge event. It also installs a git `post-merge` hook in the clone (`.git/hooks/post-merge`, or under `core.hooksPath`). `--muse-settings` points it at a different settings file.

Put watch's keys in files, each `chmod 600`: a read-only GitHub token at `~/.knack/github_token`, the Spark key at `~/.knack/model_api_key` and the Spark Open key at `~/.knack/baseten_api_key` (under `$KNACK_HOME` if set). Hooks don't inherit your shell's environment, so watch reads each file when `GITHUB_TOKEN`, `MODEL_API_KEY` or `BASETEN_API_KEY` is not set, and refuses a file others can read.
