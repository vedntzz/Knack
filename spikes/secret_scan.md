# Secret scan: full git history

Date: 2026-11-02. Branch `chore/secret-scan`, HEAD `5ad229c`.

**Result: no real secret was ever committed.** No key needs rotating.

## Scope

- `git fetch origin` first, so every remote branch was local.
- Refs scanned: all 184 (`refs/heads/*`, `refs/remotes/origin/*`, `refs/tags/*`). No stash.
- Commits scanned: **256** reachable from any ref, 101 of them merges.
- Two passes over `git log -p --all --full-history --text`:
  1. normal diffs (every added line, plus every commit message);
  2. the same with `-m`, so merge commits are diffed against each parent. It found no new hit.
- Filenames ever committed were also checked for `.env`, `*.pem`, `id_rsa`,
  `credentials`, `secret`. None.

## Tool

gitleaks and trufflehog are not installed, so a Python regex scanner read the
`git log -p --all` stream. Patterns:

| Name | Regex (shape) |
|---|---|
| Meta/OpenAI-style key | `sk-(proj-\|ant-)?[A-Za-z0-9_-]{16,}` |
| Baseten key | `[A-Za-z0-9]{8}\.[A-Za-z0-9]{32}`, and `Api-Key <8+ chars>` |
| Bearer token | `Bearer <12+ token chars>` |
| Authorization header | `Authorization` followed by `:` or `=` and a value |
| GitHub token | `gh[pousr]_[A-Za-z0-9]{30,}`, `github_pat_[A-Za-z0-9_]{20,}` |
| AWS | `(AKIA\|ASIA)[0-9A-Z]{16}`, `aws_secret_access_key` followed by `:` or `=` and a value |
| Named env | any value assigned to `MODEL_API_KEY`, `BASETEN_API_KEY`, `GITHUB_TOKEN` |
| Extra | `-----BEGIN … PRIVATE KEY-----`, `hf_[A-Za-z0-9]{30,}` |

A second pass looked for raw request headers in committed traces, fixtures,
spikes and bench logs: `x-api-key`, `"headers":`, `Cookie:`, and `api_key` or
`token` set to a 16+ char quoted value. Every match was upstream FastAPI or
Airflow source quoted in a compile log (`APIKeyHeader(name="x-api-key")`,
Apache licence headers). No real header values.

## Hits

The history pass gave 47 raw hits, 16 unique (file, value) pairs. Previews are
cut short on purpose; `…[n]` is the length of the matched text.

| # | Pattern | File | First commit | Redacted preview | Class |
|---|---|---|---|---|---|
| 1 | named env | `bench/run-1030c.log` | `611b41c` | `GITHUB_TOKEN: auth…` | false positive: doctor's prose line "authenticated as vedntzz" |
| 2 | named env | `bench/run-1030c.log` | `611b41c` | `MODEL_API_KEY: muse…` | false positive: "muse-spark-1.3 answered" |
| 3 | named env | `bench/run-1030c.log` | `611b41c` | `BASETEN_API_KEY: meta…` | false positive: "meta-models/… answered" (a model name) |
| 4 | named env | `.github/workflows/knack-guard.yml` | `f57e24d` | `GITHUB_TOKEN: ${{…` | false positive: Actions secret reference |
| 5 | named env | `tests/guard/test_pr_comment.py` | `f57e24d` | `GITHUB_TOKEN: ${{…` | false positive: workflow text the test asserts on |
| 6 | named env | `tests/guard/test_pr_comment.py` | `f57e24d` | `"t0ke…[5]"` | test placeholder |
| 7 | named env | `tests/bench/test_doctor.py` | `32d46a8` | `"ghp-doct…[21]"` | test placeholder (hyphen, not a real `ghp_` shape) |
| 8 | sk / named env | `tests/bench/test_doctor.py` | `32d46a8` | `"sk-doct…[19]"` | test placeholder |
| 9 | named env | `tests/bench/test_doctor.py` | `32d46a8` | `"bt-doct…[18]"` | test placeholder |
| 10 | sk | `tests/bench/test_run.py` | `4788f9c` | `"sk-benc…[28]"` | test placeholder |
| 11 | Authorization | `tests/pipeline/test_spark_open.py` | `3725552` | `Bear… k…[3]` | test placeholder (literal `key`) |
| 12 | AWS secret | `spikes/compile_run4_airflow_74150.log` | `bb576bf` | `aws_secret_access_key="sec…` | false positive: Airflow docstring example, value is the word `secret` |
| 13 | AWS secret | same log | `bb576bf` | `aws_secret_access_key": "...` | false positive: Airflow docstring, value `...`; key shown as `AKIA...` |
| 14 | Authorization | `spikes/warn_live_run.json` | `fc4b52f` | `authority": "unk…` | false positive: `authority` label field |
| 15 | Authorization | `spikes/natural_block_run2.json` | `533b959` | `authority": "med…` | false positive: `authority` label field |
| 16 | Authorization | `spikes/natural_block_run2.json` | `533b959` | `authority": "hig…` | false positive: `authority` label field |

Real secrets: **0**. Test placeholders: 6 values in 4 files. False positives: 9.

## Keeping it clean

`tests/test_no_secrets.py` runs the same pattern set over every tracked file
(`git ls-files`) on every pytest run, so CI fails on a new leak. Changes from
the history scan, to cut the false positives above:

- `Authorization` must be followed by a scheme (`Bearer`, `Basic`, `token`, `Api-Key`).
- AWS secret must be a 40-char value.
- Named env values must be quoted, or come after `=`. Values starting with `$`
  (`${{ secrets.X }}`, `$(gh auth token)`) are references and pass. `META_API_KEY`
  was added, because `knack/bench/muse.py` reads it.
- Placeholders are allow-listed by exact value **and** file. The same fake
  value in any other file fails.
- A failure prints `path:line pattern abcd…[n chars]`, never the value.

Known gap: an unquoted YAML value (`GITHUB_TOKEN: ghp_…`) is caught only by
the format patterns, not by the named-env pattern. The format patterns cover
every real token shape listed above.
