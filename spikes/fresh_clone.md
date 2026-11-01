# Fresh-clone reproduce, as a stranger

Date: 2026-11-01, 10:59:41 EST. Machine: macOS (Darwin 27.0.0, arm64), uv 0.12.23, system python3 3.12.3, jq present, no ast-grep on PATH.
Clone: `git clone https://github.com/vedntzz/Knack.git` into a scratch temp dir, HEAD `b2b2abd` (Merge PR #84).
Followed only README.md. Nothing was fixed in place.

## Result

**No green run. Hard failure in the `e2e` section: `FAIL real HOME untouched` (25/26). `reproduce.sh` exited 1.**

| Phase | Wall clock |
|---|---|
| clone | ~16 s |
| `uv venv && uv pip install -e ".[dev]"` | ~1 s (uv cache was warm; a cold cache will be slower) |
| `bash scripts/reproduce.sh` | 86 s, exit 1 |
| clone start → script exit | **114 s** |

The proof grid section itself printed in full in that 114 s window: 12 rules, 0 NOT RUN, `bench/PROOF-GRID.md` rewritten byte-identically (`git status` clean). Every section other than e2e printed the numbers the README cites. The bench report matched `bench/REPORT-1030c.md` (`yes`). But the script as a whole was not green.

## Hard failure: `e2e: real HOME untouched`

- The check (`scripts/e2e.sh` `real_state`) fingerprints **every file** under the real `~/.knack` and `~/.config/muse` before and after the run.
- During the run, the real `~/.knack/guard_errors.log` changed (mtime 11:01, inside the run window). Its newest entries are `RuntimeError: boom` and `ValidationError: 1 validation error for list[RegistryEntry]`.
- e2e's own fail-open step does not raise `boom`; it writes a `{nonsense: 1}` rule. `boom` is used in `tests/hooks/test_pretool.py`, `tests/dispute/test_argue.py`, `tests/pipeline/test_heldout.py`, `tests/pipeline/test_watch_run.py` and `tests/bench/test_proof_grid.py`.
- At 11:00:08, a separate `pytest -q -x` started in `~/Documents/knack` (another session) and overlapped the e2e run. Most likely cause: that pytest run wrote to the real `~/.knack/guard_errors.log`, not this clone.
- Not proven: I stopped at the first hard failure and did not rerun in isolation.

What this exposes, even if the leak came from another process:
1. Some tests write to the real `~/.knack/guard_errors.log`. `home_error_log()` in `knack/hooks/scope.py` uses `Path.home()`, and those tests don't isolate HOME.
2. The "untouched" check fails whenever anything else on the machine uses Knack at the same time. A stranger with no `~/.knack` would not hit this, but any contributor who has used Knack can.

## Snags (in the order hit)

1. **No prerequisites listed.** README never says you need `git`, `uv`, or `jq`. `jq` is needed for the 17-PR check in "Verify any claim". There is no clone command either; a stranger has to infer it.
2. **uv quietly chose a different Python.** `uv venv` made the venv with Python 3.11.17, a uv-managed build, even though the system has 3.12.3. That's fine (`requires-python >=3.11`), but a machine without a uv-managed 3.11 may need to download one, which needs network. README doesn't say.
3. **Venv activation not stated.** The "Verify any claim" table runs bare `python -m knack.reproduce ...`. Without `source .venv/bin/activate`, that uses system python and fails to import `knack`. `reproduce.sh` itself is fine: it defaults to `.venv/bin/python`.
4. **ast-grep source unstated.** It isn't on PATH. It comes from the pip dependency `ast-grep-cli==0.51.0`, and that worked, but README never says so.
5. **`reproduce.sh` writes a tracked file.** It overwrites `bench/PROOF-GRID.md` in place. It was identical this time, but if it ever drifts, a stranger's clone gets dirty without warning.
6. **"Green" is undefined.** The proof grid is meant to print FAIL cells: held-out 7 PASS / 5 FAIL, variants 10/2, rename 11/1. README never says which grid cells must pass for the reproduce to count as green. Only the exit code decides.
7. **The failure is easy to miss.** The script has no final summary line. The one `FAIL` sits at the very bottom of 152 lines, under the e2e step list, and the exit code is the only overall signal.
8. **e2e is not isolated from the machine.** See the hard failure above.

## To confirm the cause (not done)

Rerun `bash scripts/reproduce.sh` with no other Knack/pytest process running. Or diff the fingerprint of `~/.knack` before and after `pytest -q` alone, to see which tests write to the real HOME.
